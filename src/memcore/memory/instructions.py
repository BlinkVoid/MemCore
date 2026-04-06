"""
Specialized Instruction Extraction and Management Pipeline

Instructions (SOPs, coding preferences, behavior guidelines) are treated differently
from facts - they have versioning, override semantics, and strict validation.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json
import re


class InstructionType(str, Enum):
    """Types of instructions that can be extracted."""
    CODING_STANDARD = "coding_standard"      # Code style, naming conventions
    BEHAVIOR = "behavior"                     # How the AI should behave/respond
    WORKFLOW = "workflow"                     # Process steps, procedures
    PREFERENCE = "preference"                 # User preferences (not strict rules)
    CONSTRAINT = "constraint"                 # Hard limits, must not violate


class InstructionValidator:
    """Validates instruction structure and content."""

    # Patterns that indicate a valid instruction
    ACTION_PATTERNS = [
        r"^(Always|Never|Use|Prefer|Avoid|Ensure|Do not|Must|Should)",
        r"(should|must|always|never)\s+be",
        r"(use|prefer|avoid)\s+\w+",
    ]

    REQUIRED_FIELDS = ["summary", "content", "instruction_type"]

    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.ACTION_PATTERNS]

    def validate(self, instruction: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate an instruction entry.

        Returns: (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in instruction or not instruction[field]:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Check if it looks like an instruction (action-oriented)
        content = instruction.get("content", "")
        looks_like_instruction = any(p.search(content) for p in self.patterns)

        if not looks_like_instruction:
            errors.append("Content doesn't appear to be an actionable instruction")

        # Validate instruction type
        try:
            InstructionType(instruction.get("instruction_type", ""))
        except ValueError:
            valid_types = [t.value for t in InstructionType]
            errors.append(f"Invalid instruction_type. Must be one of: {valid_types}")

        return len(errors) == 0, errors

    def classify_instruction(self, content: str) -> InstructionType:
        """Classify the type of instruction based on content."""
        content_lower = content.lower()

        # Coding standards
        if any(word in content_lower for word in ["code", "naming", "function", "class", "file", "variable"]):
            return InstructionType.CODING_STANDARD

        # Constraints (strong prohibitions)
        if any(word in content_lower for word in ["never", "must not", "don't", "do not", "prohibited"]):
            return InstructionType.CONSTRAINT

        # Workflow
        if any(word in content_lower for word in ["first", "then", "next", "step", "process", "procedure"]):
            return InstructionType.WORKFLOW

        # Behavior
        if any(word in content_lower for word in ["respond", "reply", "ask", "tell", "explain", "help"]):
            return InstructionType.BEHAVIOR

        # Default
        return InstructionType.PREFERENCE


class InstructionExtractor:
    """
    Specialized extractor for AI instructions.

    Unlike facts, instructions need:
    - Action-oriented validation
    - Type classification
    - Override semantics (newer instructions can override older ones)
    - Priority scoring (constraints > standards > preferences)
    """

    PRIORITY_WEIGHTS = {
        InstructionType.CONSTRAINT: 1.0,
        InstructionType.CODING_STANDARD: 0.9,
        InstructionType.WORKFLOW: 0.85,
        InstructionType.BEHAVIOR: 0.8,
        InstructionType.PREFERENCE: 0.6,
    }

    def __init__(self, llm):
        self.llm = llm
        self.validator = InstructionValidator()

    async def extract(self, raw_content: str, context: str = "") -> List[Dict[str, Any]]:
        """
        Extract structured instructions from raw content.

        Returns list of validated instruction objects.
        """
        prompt = f"""
        Extract ALL actionable instructions from the following content.

        Content:
        {raw_content[:3000]}

        Context: {context}

        Instructions are statements that tell an AI how to behave, code, or respond:
        - "Always use snake_case for file names"
        - "Never share API keys"
        - "When user asks X, do Y first"
        - "Prefer TypeScript over JavaScript"

        For each instruction, identify:
        1. A clear, actionable summary (5-8 words)
        2. The full instruction text
        3. Type: coding_standard, behavior, workflow, preference, or constraint
        4. Scope: when does this apply? (e.g., "when coding", "always", "in Python projects")
        5. Priority: high/medium/low based on importance

        Return JSON:
        {{
            "instructions": [
                {{
                    "summary": "brief action-oriented title",
                    "content": "full instruction text",
                    "instruction_type": "coding_standard|behavior|workflow|preference|constraint",
                    "scope": "when this applies",
                    "priority": "high|medium|low",
                    "quadrants": ["ai_instructions"]
                }}
            ]
        }}

        If no clear instructions are found, return empty instructions array.
        """

        response = await self.llm.completion(
            messages=[
                {"role": "system", "content": "You are an expert at identifying actionable instructions and SOPs from text."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            tier="strong"
        )

        try:
            data = json.loads(response)
            instructions = data.get("instructions", [])
        except (json.JSONDecodeError, KeyError):
            return []

        # Validate and enrich each instruction
        validated = []
        for instr in instructions:
            is_valid, errors = self.validator.validate(instr)
            if is_valid:
                # Add metadata
                instr["_validated"] = True
                instr["_priority_score"] = self._calculate_priority(instr)
                instr["_extracted_at"] = datetime.now().isoformat()
                validated.append(instr)
            else:
                # Log validation failures for debugging
                print(f"[InstructionExtractor] Rejected instruction: {instr.get('summary', 'unknown')} - {errors}")

        return validated

    def _calculate_priority(self, instruction: Dict[str, Any]) -> float:
        """Calculate priority score based on type and explicit priority."""
        # Base priority from instruction type
        instr_type = instruction.get("instruction_type", "preference")
        try:
            base_priority = self.PRIORITY_WEIGHTS.get(InstructionType(instr_type), 0.5)
        except ValueError:
            base_priority = 0.5

        # Modifier from explicit priority
        explicit = instruction.get("priority", "medium").lower()
        modifiers = {"high": 1.2, "medium": 1.0, "low": 0.8}
        modifier = modifiers.get(explicit, 1.0)

        return base_priority * modifier

    def compare_instructions(
        self,
        existing: Dict[str, Any],
        new: Dict[str, Any]
    ) -> str:
        """
        Compare two instructions and determine relationship.

        Returns: "identical", "override", "conflict", or "distinct"
        """
        # Simple content similarity check
        existing_content = existing.get("content", "").lower().strip()
        new_content = new.get("content", "").lower().strip()

        if existing_content == new_content:
            return "identical"

        # Check if they're about the same topic
        existing_summary = existing.get("summary", "").lower()
        new_summary = new.get("summary", "").lower()

        # Simple word overlap check
        existing_words = set(existing_summary.split())
        new_words = set(new_summary.split())
        overlap = len(existing_words & new_words)
        total = len(existing_words | new_words)

        if total > 0 and overlap / total > 0.5:
            # Same topic - check if one overrides the other
            if new.get("_priority_score", 0) > existing.get("_priority_score", 0):
                return "override"
            return "conflict"

        return "distinct"


class InstructionStore:
    """
    Specialized storage for instructions with versioning and override tracking.
    """

    def __init__(self, vector_store, graph_store):
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def store_instruction(
        self,
        instruction: Dict[str, Any],
        vector: List[float],
        source_uri: Optional[str] = None
    ) -> str:
        """
        Store an instruction with special handling for overrides.
        """
        from src.memcore.storage.graph import GraphStore

        instruction_id = str(uuid.uuid4())

        # Enrich payload with instruction metadata
        payload = {
            "content": instruction["content"],
            "summary": instruction["summary"],
            "quadrants": ["ai_instructions"],
            "instruction_type": instruction.get("instruction_type", "preference"),
            "scope": instruction.get("scope", "general"),
            "priority": instruction.get("priority", "medium"),
            "importance": instruction.get("_priority_score", 0.8),
            "source_uri": source_uri,
            "type": "instruction",  # Special type for filtering
            "created_at": datetime.now().isoformat()
        }

        # Store in vector DB
        self.vector_store.upsert_memory(instruction_id, vector, payload)

        # Add to graph as instruction node
        self.graph_store.add_node(
            instruction_id,
            "instruction",
            {
                "summary": instruction["summary"],
                "instruction_type": instruction["instruction_type"],
                "priority": instruction.get("priority", "medium")
            },
            source_uri=source_uri
        )

        return instruction_id

    def find_overridden_instructions(
        self,
        new_instruction: Dict[str, Any],
        vector: List[float]
    ) -> List[Dict[str, Any]]:
        """
        Find existing instructions that might be overridden by a new one.

        Returns list of potentially overridden instruction IDs.
        """
        # Search for similar instructions
        results = self.vector_store.search_memories(
            vector,
            limit=5,
            filter_quadrants=["ai_instructions"]
        )

        extractor = InstructionExtractor(None)  # No LLM needed for comparison
        overridden = []

        for result in results:
            if result.score < 0.7:  # Only consider highly similar
                continue

            existing = {
                "summary": result.payload.get("summary", ""),
                "content": result.payload.get("content", ""),
                "instruction_type": result.payload.get("instruction_type", "preference"),
                "_priority_score": result.payload.get("importance", 0.5)
            }

            relationship = extractor.compare_instructions(existing, new_instruction)
            if relationship in ["override", "conflict"]:
                overridden.append({
                    "id": result.id,
                    "relationship": relationship,
                    "existing": existing
                })

        return overridden
