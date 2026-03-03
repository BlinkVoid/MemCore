"""
Feedback Skill - Submit feedback on memory retrieval quality.

Replaces the submit_feedback MCP tool with a richer interactive skill.
"""
from typing import Dict, Any, Optional
from datetime import datetime


class FeedbackSkill:
    """
    Skill for submitting feedback on memory quality.

    Usage: /feedback <memory_id> <rating> [reason]
    """

    def __init__(self, feedback_optimizer):
        self.optimizer = feedback_optimizer

    async def execute(
        self,
        memory_id: str,
        rating: int,  # -1 (negative) or +1 (positive)
        reason: Optional[str] = None,
        query_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit feedback on a memory retrieval.

        Args:
            memory_id: The memory that was retrieved
            rating: +1 for helpful, -1 for unhelpful
            reason: Optional explanation
            query_context: What query retrieved this memory
        """
        try:
            # Submit to feedback optimizer
            result = await self.optimizer.process_feedback(
                memory_id=memory_id,
                query=query_context or "manual_feedback",
                rating=rating,
                reason=reason
            )

            # Get current weights
            weights = self.optimizer.get_current_weights()

            return {
                "success": True,
                "memory_id": memory_id,
                "rating": rating,
                "weights_adjusted": result.get("weights_adjusted", False),
                "current_weights": weights,
                "message": "Feedback recorded. " + (
                    "Weights auto-adjusted." if result.get("weights_adjusted") else ""
                )
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_help(self) -> str:
        return """
/feedback <memory_id> <+1|-1> [reason] [--query="context"]

Submit feedback on memory retrieval quality.

Examples:
  /feedback abc123 +1 "Exactly what I needed"
  /feedback def456 -1 "Outdated information" --query="python async"
"""
