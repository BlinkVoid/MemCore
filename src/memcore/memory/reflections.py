"""
Fact Synthesis and Reflection Generation

Reflections are higher-level insights synthesized from multiple related facts.
For example, detecting a pattern across multiple interactions:
- Fact 1: "User asked for Python script to process CSV"
- Fact 2: "User requested Python solution for data cleaning"
- Fact 3: "User preferred pandas over numpy for data task"
- Reflection: "User consistently chooses Python for data processing tasks"
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid


class ReflectionGenerator:
    """
    Generates synthetic reflections from groups of related memories.

    A reflection captures patterns, trends, or insights that emerge from
    multiple individual memories but aren't explicitly stated in any single one.
    """

    def __init__(self, llm):
        self.llm = llm
        self.min_memories_for_reflection = 3  # Need at least 3 to form a pattern
        self.similarity_threshold = 0.75  # Memories must be reasonably related

    async def generate_reflections(
        self,
        memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate reflections from a batch of memories.

        Args:
            memories: List of memory dicts with id, content, summary, quadrants

        Returns:
            List of reflection objects
        """
        if len(memories) < self.min_memories_for_reflection:
            return []

        # Group memories by quadrant and semantic similarity
        groups = await self._group_related_memories(memories)

        reflections = []
        for group in groups:
            if len(group) >= self.min_memories_for_reflection:
                reflection = await self._synthesize_reflection(group)
                if reflection:
                    reflections.append(reflection)

        return reflections

    async def _group_related_memories(
        self,
        memories: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Group memories by semantic similarity.

        Uses embeddings to find clusters of related memories.
        """
        if not memories:
            return []

        # Simple clustering: group by shared quadrant first
        by_quadrant: Dict[str, List[Dict]] = {}
        for mem in memories:
            quad = mem.get("quadrants", ["general"])[0]
            by_quadrant.setdefault(quad, []).append(mem)

        # Further refine by content similarity using LLM
        groups = []
        for quadrant, quad_memories in by_quadrant.items():
            if len(quad_memories) < self.min_memories_for_reflection:
                continue

            # Use LLM to identify clusters
            groups.extend(await self._cluster_by_similarity(quad_memories))

        return groups

    async def _cluster_by_similarity(
        self,
        memories: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Cluster memories by semantic similarity using LLM."""

        # Prepare memory summaries for LLM
        memory_list = "\n".join([
            f"{i}. [{m['id']}] {m['summary']}: {m['content'][:100]}..."
            for i, m in enumerate(memories)
        ])

        prompt = f"""
        Analyze these memories and group them by topic/theme.

        Memories:
        {memory_list}

        Group memories that are about the SAME topic or pattern.
        For example, if multiple memories mention "Python" and "data processing",
        they should be in one group.

        Return JSON:
        {{
            "groups": [
                {{
                    "theme": "brief theme name",
                    "memory_indices": [0, 2, 3],
                    "reasoning": "why these belong together"
                }}
            ]
        }}

        Only create groups with 3+ memories. Return empty groups if no clear patterns.
        """

        try:
            response = await self.llm.completion(
                messages=[
                    {"role": "system", "content": "You are an expert at pattern recognition and thematic analysis."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                tier="strong"
            )

            data = json.loads(response)
            groups = []

            for group in data.get("groups", []):
                indices = group.get("memory_indices", [])
                if len(indices) >= self.min_memories_for_reflection:
                    group_memories = [memories[i] for i in indices if i < len(memories)]
                    if group_memories:
                        groups.append(group_memories)

            return groups

        except Exception as e:
            print(f"[ReflectionGenerator] Clustering failed: {e}")
            return []

    async def _synthesize_reflection(
        self,
        group: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesize a reflection from a group of related memories.

        Creates a higher-level insight that captures the pattern across memories.
        """
        # Prepare context
        memories_context = "\n\n".join([
            f"Memory {i+1}:\nSummary: {m['summary']}\nContent: {m['content'][:200]}"
            for i, m in enumerate(group)
        ])

        prompt = f"""
        Synthesize a REFLECTION from these related memories.

        A reflection is a higher-level insight or pattern that emerges from
        multiple individual memories. It captures what these memories TELL US
        about the user when viewed together.

        Memories:
        {memories_context}

        Generate:
        1. A concise reflection statement (1-2 sentences)
        2. The confidence level (high/medium/low)
        3. The pattern type (preference, behavior, capability, interest)
        4. Evidence summary (which memories support this)

        Example reflection:
        "User consistently prefers Python for data processing tasks, favoring
        pandas over other libraries. This suggests strong pandas proficiency."

        Return JSON:
        {{
            "reflection": "the synthesized insight",
            "summary": "brief title for this reflection",
            "confidence": "high|medium|low",
            "pattern_type": "preference|behavior|capability|interest",
            "supporting_evidence": "brief summary of supporting memories",
            "memory_count": {len(group)}
        }}
        """

        try:
            response = await self.llm.completion(
                messages=[
                    {"role": "system", "content": "You are an expert at pattern recognition and insight synthesis."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                tier="strong"
            )

            data = json.loads(response)

            # Add metadata
            reflection = {
                "id": str(uuid.uuid4()),
                "type": "reflection",
                "reflection": data.get("reflection", ""),
                "summary": data.get("summary", "Untitled Reflection"),
                "confidence": data.get("confidence", "low"),
                "pattern_type": data.get("pattern_type", "preference"),
                "supporting_evidence": data.get("supporting_evidence", ""),
                "memory_count": len(group),
                "source_memory_ids": [m["id"] for m in group],
                "created_at": datetime.now().isoformat()
            }

            return reflection

        except Exception as e:
            print(f"[ReflectionGenerator] Synthesis failed: {e}")
            return None

    async def find_duplicate_reflections(
        self,
        new_reflection: Dict[str, Any],
        existing_reflections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check if a new reflection duplicates or refines an existing one.

        Returns list of existing reflections that are similar.
        """
        if not existing_reflections:
            return []

        new_text = new_reflection.get("reflection", "")

        # Check for substantial overlap in supporting evidence
        new_sources = set(new_reflection.get("source_memory_ids", []))

        duplicates = []
        for existing in existing_reflections:
            existing_sources = set(existing.get("source_memory_ids", []))

            # If they share 50%+ of source memories, they're likely duplicates
            if new_sources and existing_sources:
                overlap = len(new_sources & existing_sources)
                total = len(new_sources | existing_sources)

                if total > 0 and overlap / total > 0.5:
                    duplicates.append(existing)

        return duplicates


class DeduplicationEngine:
    """
    LLM-driven deduplication of facts and memories.

    Detects semantic duplicates (same meaning, different wording) and
    near-duplicates that should be merged.
    """

    def __init__(self, llm):
        self.llm = llm

    async def check_duplicate(
        self,
        new_fact: str,
        existing_facts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check if a new fact duplicates or refines existing facts.

        Returns:
            {
                "is_duplicate": bool,
                "duplicate_of": id or None,
                "merge_suggestion": str or None,
                "confidence": float
            }
        """
        if not existing_facts:
            return {"is_duplicate": False, "duplicate_of": None, "merge_suggestion": None, "confidence": 1.0}

        existing_context = "\n".join([
            f"ID {e['id']}: {e['content'][:150]}"
            for e in existing_facts
        ])

        prompt = f"""
        Compare the NEW fact with EXISTING facts and determine if it's a duplicate.

        NEW FACT:
        {new_fact}

        EXISTING FACTS:
        {existing_context}

        Analyze:
        1. Is the new fact semantically equivalent to any existing fact? (same meaning, different words)
        2. Does it add new information that should be merged?
        3. Is it completely new?

        Return JSON:
        {{
            "is_duplicate": true/false,
            "duplicate_of": "ID of existing fact if duplicate, else null",
            "relationship": "identical|semantic_duplicate|refinement|superset|subset|new",
            "merge_suggestion": "If refinement, suggest merged text, else null",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm.completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                tier="fast"  # Fast tier is sufficient here
            )

            result = json.loads(response)
            return {
                "is_duplicate": result.get("is_duplicate", False),
                "duplicate_of": result.get("duplicate_of"),
                "relationship": result.get("relationship", "new"),
                "merge_suggestion": result.get("merge_suggestion"),
                "confidence": result.get("confidence", 0.5)
            }

        except Exception as e:
            print(f"[DeduplicationEngine] Check failed: {e}")
            return {"is_duplicate": False, "duplicate_of": None, "merge_suggestion": None, "confidence": 0.0}

    async def merge_facts(
        self,
        facts: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Merge multiple related facts into a single comprehensive fact.

        Returns the merged fact text, or None if merging isn't appropriate.
        """
        if len(facts) < 2:
            return None

        facts_context = "\n".join([
            f"- {f['content']}"
            for f in facts
        ])

        prompt = f"""
        Merge these related facts into a single comprehensive statement.

        Facts:
        {facts_context}

        Create a merged fact that:
        - Captures all key information
        - Removes redundancy
        - Is concise but complete

        Return only the merged fact text, nothing else.
        """

        try:
            response = await self.llm.completion(
                messages=[{"role": "user", "content": prompt}],
                tier="strong"
            )

            return response.strip()

        except Exception as e:
            print(f"[DeduplicationEngine] Merge failed: {e}")
            return None
