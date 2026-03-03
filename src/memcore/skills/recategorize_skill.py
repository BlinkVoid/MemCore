"""
Recategorize Skill - Move memories between quadrants.

Usage: /recategorize <memory_id> <new_quadrant>
"""
from typing import Dict, Any, Optional, List


class RecategorizeSkill:
    """
    Skill for moving memories between quadrants.

    Usage:
      /recategorize abc123 coding
      /recategorize def456 personal
    """

    VALID_QUADRANTS = ["coding", "personal", "research", "ai_instructions", "general"]

    def __init__(self, vector_store, graph_store):
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def execute(
        self,
        memory_id: str,
        new_quadrant: str,
        add_to_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Move a memory to a different quadrant.

        Args:
            memory_id: The memory to recategorize
            new_quadrant: Target quadrant
            add_to_existing: If True, add quadrant; if False, replace
        """
        try:
            # Validate quadrant
            if new_quadrant not in self.VALID_QUADRANTS:
                return {
                    "success": False,
                    "error": f"Invalid quadrant '{new_quadrant}'. Valid: {', '.join(self.VALID_QUADRANTS)}"
                }

            # Get memory
            memory_data = self.vector_store.get_memory_by_id(memory_id)
            if not memory_data:
                return {
                    "success": False,
                    "error": f"Memory not found: {memory_id}"
                }

            memory = memory_data[0]
            old_quadrants = memory.payload.get("quadrants", ["general"])

            # Determine new quadrants
            if add_to_existing:
                new_quadrants = list(set(old_quadrants + [new_quadrant]))
            else:
                new_quadrants = [new_quadrant]

            # Update vector store
            self.vector_store.update_memory_quadrants(memory_id, new_quadrants)

            # Update graph
            for old_q in old_quadrants:
                if old_q != new_quadrant and not add_to_existing:
                    self.graph_store.remove_quadrant_tag(memory_id, old_q)

            for q in new_quadrants:
                self.graph_store.add_quadrant_tag(memory_id, q)

            # Add recategorization edge
            self.graph_store.add_edge(
                memory_id,
                f"quadrant:{new_quadrant}",
                edge_type="RECATEGORIZED_TO",
                metadata={"old_quadrants": old_quadrants}
            )

            return {
                "success": True,
                "memory_id": memory_id,
                "old_quadrants": old_quadrants,
                "new_quadrants": new_quadrants,
                "action": "added" if add_to_existing else "moved",
                "message": f"Memory {memory_id} {'added to' if add_to_existing else 'moved to'} {new_quadrant}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_help(self) -> str:
        return """
/recategorize <memory_id> <quadrant> [--add]

Move a memory to a different quadrant.

Quadrants: coding, personal, research, ai_instructions, general

Options:
  --add    Add quadrant instead of replacing

Examples:
  /recategorize abc123 coding
  /recategorize def456 personal --add
"""
