"""
Hierarchy-Based Conflict Resolution System

Resolves contradictory memories using a priority hierarchy:
1. CONSTRAINTS (1.0) - Hard limits that must not be violated
2. EXPLICIT_CORRECTIONS (0.95) - User-corrected information
3. VERIFIED_FACTS (0.9) - Cross-referenced, confirmed facts
4. RECENT_FACTS (0.8) - Newer information (with temporal decay)
5. GENERAL_FACTS (0.7) - Standard facts
6. PREFERENCES (0.6) - Soft preferences

When conflicts occur, the higher-priority item wins.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import json


class ConflictResolution(Enum):
    """Possible outcomes of conflict resolution."""
    KEEP_EXISTING = "keep_existing"  # Existing memory wins
    REPLACE_WITH_NEW = "replace_with_new"  # New memory wins
    KEEP_BOTH_MARKED = "keep_both_marked"  # Both valid but conflicting
    MERGE = "merge"  # Create merged version
    DEFER_TO_USER = "defer_to_user"  # Can't decide automatically


class MemoryPriority(Enum):
    """Priority levels for memory types."""
    CONSTRAINT = 1.0
    EXPLICIT_CORRECTION = 0.95
    VERIFIED_FACT = 0.9
    RECENT_FACT = 0.8
    GENERAL_FACT = 0.7
    PREFERENCE = 0.6
    UNCERTAIN = 0.4


class ConflictResolver:
    """
    Resolves conflicts between contradictory memories.

    Uses a hierarchy-based approach where certain types of information
    inherently override others (e.g., constraints override preferences).
    """

    def __init__(self, llm=None):
        self.llm = llm
        # How long until a fact is considered "old" (days)
        self.fact_freshness_threshold = 30

    def get_priority(self, memory: Dict[str, Any]) -> float:
        """
        Determine the priority score of a memory.

        Priority is based on:
        - Memory type (constraint vs preference)
        - Verification status
        - Temporal authority (when it was learned)
        - User confirmation status
        """
        # Base priority from type
        mem_type = memory.get("type", "general")
        quadrant = memory.get("quadrants", ["general"])

        if mem_type == "constraint" or "constraint" in memory.get("tags", []):
            base_priority = MemoryPriority.CONSTRAINT.value
        elif memory.get("explicitly_corrected"):
            base_priority = MemoryPriority.EXPLICIT_CORRECTION.value
        elif memory.get("verified"):
            base_priority = MemoryPriority.VERIFIED_FACT.value
        elif "ai_instructions" in quadrant:
            # Instructions get higher priority than general facts
            instr_type = memory.get("instruction_type", "preference")
            priority_map = {
                "constraint": MemoryPriority.CONSTRAINT.value,
                "coding_standard": 0.85,
                "workflow": 0.82,
                "behavior": 0.8,
                "preference": MemoryPriority.PREFERENCE.value
            }
            base_priority = priority_map.get(instr_type, MemoryPriority.GENERAL_FACT.value)
        else:
            base_priority = MemoryPriority.GENERAL_FACT.value

        # Temporal modifier
        created_at = memory.get("created_at")
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_dt = created_at

                age_days = (datetime.now() - created_dt.replace(tzinfo=None)).days

                # Very recent facts get a small boost
                if age_days < 7:
                    temporal_modifier = 1.1
                # Old facts decay slightly
                elif age_days > self.fact_freshness_threshold:
                    temporal_modifier = 0.9
                else:
                    temporal_modifier = 1.0
            except:
                temporal_modifier = 1.0
        else:
            temporal_modifier = 1.0

        # Confidence modifier
        confidence = memory.get("confidence", "medium")
        confidence_modifiers = {"high": 1.1, "medium": 1.0, "low": 0.9}
        confidence_modifier = confidence_modifiers.get(confidence, 1.0)

        # Importance override
        importance = memory.get("importance", 0.5)
        if importance >= 0.95:
            importance_modifier = 1.2
        elif importance >= 0.8:
            importance_modifier = 1.1
        else:
            importance_modifier = 1.0

        final_priority = base_priority * temporal_modifier * confidence_modifier * importance_modifier

        # Cap at 1.0
        return min(final_priority, 1.0)

    async def resolve_conflict(
        self,
        new_memory: Dict[str, Any],
        existing_memory: Dict[str, Any],
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Resolve a conflict between two memories.

        Returns resolution decision with reasoning.
        """
        new_priority = self.get_priority(new_memory)
        existing_priority = self.get_priority(existing_memory)

        priority_diff = abs(new_priority - existing_priority)

        # Clear priority difference - higher priority wins
        if priority_diff > 0.15:
            if new_priority > existing_priority:
                return {
                    "resolution": ConflictResolution.REPLACE_WITH_NEW,
                    "winner": "new",
                    "reason": f"New memory has higher priority ({new_priority:.2f} vs {existing_priority:.2f})",
                    "action": "replace",
                    "new_priority": new_priority,
                    "existing_priority": existing_priority
                }
            else:
                return {
                    "resolution": ConflictResolution.KEEP_EXISTING,
                    "winner": "existing",
                    "reason": f"Existing memory has higher priority ({existing_priority:.2f} vs {new_priority:.2f})",
                    "action": "reject_new",
                    "new_priority": new_priority,
                    "existing_priority": existing_priority
                }

        # Similar priorities - need semantic analysis
        if self.llm:
            semantic_resolution = await self._semantic_conflict_resolution(
                new_memory, existing_memory, context
            )
            return semantic_resolution

        # No LLM available - keep both as conflicting
        return {
            "resolution": ConflictResolution.KEEP_BOTH_MARKED,
            "winner": None,
            "reason": "Similar priority levels, keeping both as potential conflict",
            "action": "mark_conflict",
            "new_priority": new_priority,
            "existing_priority": existing_priority
        }

    async def _semantic_conflict_resolution(
        self,
        new_memory: Dict[str, Any],
        existing_memory: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Use LLM to determine how to resolve a semantic conflict.
        """
        prompt = f"""
        Analyze this conflict between two pieces of information.

        CONTEXT: {context if context else "No additional context provided"}

        NEW INFORMATION:
        Summary: {new_memory.get('summary', 'N/A')}
        Content: {new_memory.get('content', 'N/A')}
        Type: {new_memory.get('type', 'general')}
        Created: {new_memory.get('created_at', 'unknown')}

        EXISTING INFORMATION:
        Summary: {existing_memory.get('summary', 'N/A')}
        Content: {existing_memory.get('content', 'N/A')}
        Type: {existing_memory.get('type', 'general')}
        Created: {existing_memory.get('created_at', 'unknown')}

        Analyze:
        1. Are these truly contradictory or just different perspectives?
        2. If contradictory, which is more likely to be correct?
        3. Should one replace the other, or should both be kept?

        Return JSON:
        {{
            "truly_conflicting": true/false,
            "explanation": "brief reasoning",
            "recommendation": "keep_existing|replace_with_new|keep_both|merge|defer",
            "confidence": "high|medium|low"
        }}
        """

        try:
            response = await self.llm.completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                tier="strong"
            )

            result = json.loads(response)
            recommendation = result.get("recommendation", "keep_both")

            resolution_map = {
                "keep_existing": ConflictResolution.KEEP_EXISTING,
                "replace_with_new": ConflictResolution.REPLACE_WITH_NEW,
                "keep_both": ConflictResolution.KEEP_BOTH_MARKED,
                "merge": ConflictResolution.MERGE,
                "defer": ConflictResolution.DEFER_TO_USER
            }

            return {
                "resolution": resolution_map.get(recommendation, ConflictResolution.KEEP_BOTH_MARKED),
                "winner": "existing" if recommendation == "keep_existing" else (
                    "new" if recommendation == "replace_with_new" else None
                ),
                "reason": result.get("explanation", "Semantic analysis completed"),
                "action": recommendation.replace("_", " "),
                "truly_conflicting": result.get("truly_conflicting", True),
                "confidence": result.get("confidence", "medium")
            }

        except Exception as e:
            print(f"[ConflictResolver] Semantic resolution failed: {e}")
            return {
                "resolution": ConflictResolution.KEEP_BOTH_MARKED,
                "winner": None,
                "reason": "Semantic analysis failed, keeping both",
                "action": "mark_conflict",
                "truly_conflicting": True,
                "confidence": "low"
            }

    def should_override_temporal(
        self,
        new_memory: Dict[str, Any],
        existing_memory: Dict[str, Any]
    ) -> bool:
        """
        Determine if new memory should override based on temporal authority.

        Returns True if new should override, False otherwise.
        """
        # Get timestamps
        new_time = new_memory.get("created_at")
        existing_time = existing_memory.get("created_at")

        if not new_time or not existing_time:
            return True  # No timestamp = assume newer

        try:
            if isinstance(new_time, str):
                new_dt = datetime.fromisoformat(new_time.replace('Z', '+00:00'))
            else:
                new_dt = new_time

            if isinstance(existing_time, str):
                existing_dt = datetime.fromisoformat(existing_time.replace('Z', '+00:00'))
            else:
                existing_dt = existing_time

            # If new is actually older, it should NOT override
            if new_dt < existing_dt.replace(tzinfo=None):
                return False

            # Check for explicit "override until" markers
            existing_valid_until = existing_memory.get("valid_until")
            if existing_valid_until:
                try:
                    valid_dt = datetime.fromisoformat(existing_valid_until.replace('Z', '+00:00'))
                    if datetime.now() > valid_dt.replace(tzinfo=None):
                        return True  # Existing has expired
                except:
                    pass

            return True

        except Exception as e:
            print(f"[ConflictResolver] Temporal check failed: {e}")
            return True

    async def find_all_conflicts(
        self,
        memory: Dict[str, Any],
        vector: List[float],
        vector_store,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find all potentially conflicting memories.

        Returns list of conflicts with resolution recommendations.
        """
        # Search for similar memories
        results = vector_store.search_memories(
            vector,
            limit=10,
            filter_quadrants=memory.get("quadrants", ["general"])
        )

        conflicts = []
        for result in results:
            if result.score < similarity_threshold:
                continue

            existing = {
                "id": result.id,
                "content": result.payload.get("content", ""),
                "summary": result.payload.get("summary", ""),
                "type": result.payload.get("type", "general"),
                "created_at": result.payload.get("created_at"),
                "confidence": result.payload.get("confidence", "medium"),
                "importance": result.payload.get("importance", 0.5),
                "quadrants": result.payload.get("quadrants", ["general"]),
                "tags": result.payload.get("tags", []),
                "verified": result.payload.get("verified", False),
                "explicitly_corrected": result.payload.get("explicitly_corrected", False)
            }

            # Check if they're actually conflicting
            resolution = await self.resolve_conflict(memory, existing)

            if resolution["resolution"] != ConflictResolution.KEEP_BOTH_MARKED or \
               resolution.get("truly_conflicting", True):
                conflicts.append({
                    "existing_memory": existing,
                    "similarity_score": result.score,
                    **resolution
                })

        return conflicts


class ConflictManager:
    """
    Manages conflict tracking and resolution in the graph store.
    """

    def __init__(self, graph_store):
        self.graph_store = graph_store

    def record_conflict(
        self,
        memory_a_id: str,
        memory_b_id: str,
        resolution: ConflictResolution,
        reason: str,
        winner_id: Optional[str] = None
    ):
        """
        Record a conflict relationship in the graph.
        """
        # Add CONFLICTS_WITH edge
        self.graph_store.add_edge(
            memory_a_id,
            memory_b_id,
            "CONFLICTS_WITH",
            weight=1.0,
            metadata={
                "resolution": resolution.value,
                "reason": reason,
                "winner": winner_id,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Also add reverse edge
        self.graph_store.add_edge(
            memory_b_id,
            memory_a_id,
            "CONFLICTS_WITH",
            weight=1.0,
            metadata={
                "resolution": resolution.value,
                "reason": reason,
                "winner": winner_id,
                "timestamp": datetime.now().isoformat()
            }
        )

    def record_override(
        self,
        winner_id: str,
        loser_id: str,
        reason: str
    ):
        """
        Record that one memory overrides another.
        """
        self.graph_store.add_edge(
            winner_id,
            loser_id,
            "OVERRIDES",
            weight=1.0,
            metadata={
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        )

    def get_conflicts_for_memory(
        self,
        memory_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all conflicts for a given memory.
        """
        related = self.graph_store.get_related_nodes(memory_id, "CONFLICTS_WITH")

        conflicts = []
        for node in related:
            metadata = json.loads(node.get("metadata", "{}"))
            conflicts.append({
                "conflict_with": node["target"],
                "resolution": metadata.get("resolution"),
                "reason": metadata.get("reason"),
                "winner": metadata.get("winner"),
                "timestamp": metadata.get("timestamp")
            })

        return conflicts
