import math
from datetime import datetime
from typing import Optional, List, Dict, Any

def calculate_recency_score(last_accessed: datetime, strength: float = 1.0) -> float:
    """
    Calculates recency score based on the Ebbinghaus Forgetting Curve.
    Score = e^(-delta_t / strength)
    """
    delta_t = (datetime.now() - last_accessed).total_seconds() / 3600.0  # Time in hours
    return math.exp(-delta_t / strength)

def calculate_importance_score(
    relevance: float,
    recency: float,
    importance: float,
    w_rel: float = 1.0,
    w_rec: float = 1.0,
    w_imp: float = 1.0
) -> float:
    """
    Calculates the final memory score.
    Score = (W_rel * Relevance) + (W_rec * Recency) + (W_imp * Importance)
    """
    return (w_rel * relevance) + (w_rec * recency) + (w_imp * importance)

def calculate_importance_score_dynamic(
    relevance: float,
    recency: float,
    importance: float,
    w_rel: float = 0.5,
    w_rec: float = 0.3,
    w_imp: float = 0.2
) -> float:
    """
    Calculates memory score with normalized dynamic weights.

    Default weights (sum to 1.0):
    - W_rel = 0.5 (relevance weight)
    - W_rec = 0.3 (recency weight)
    - W_imp = 0.2 (importance weight)

    These weights can be auto-tuned via feedback optimization.
    """
    # Ensure weights sum to 1.0 for normalization
    total = w_rel + w_rec + w_imp
    if total != 1.0:
        w_rel /= total
        w_rec /= total
        w_imp /= total

    return (w_rel * relevance) + (w_rec * recency) + (w_imp * importance)

def estimate_tokens(text: str) -> int:
    """
    Rough token estimation for text.
    Uses a simple heuristic: ~4 characters per token for English/Chinese mixed text.
    """
    if not text:
        return 0
    # Mixed language heuristic: Chinese chars count as ~1.5 tokens, English ~0.25
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.25)

class TokenBudget:
    """Manages token budget for tiered context retrieval."""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.items_included = []

    def can_add(self, estimated_tokens: int) -> bool:
        """Check if adding this item would exceed budget."""
        return self.used_tokens + estimated_tokens <= self.max_tokens

    def add(self, item_id: str, content: str, tier: str) -> bool:
        """
        Add an item to the budget if it fits.
        Returns True if added, False if over budget.
        """
        tokens = estimate_tokens(content)
        if self.can_add(tokens):
            self.used_tokens += tokens
            self.items_included.append({
                "id": item_id,
                "tier": tier,
                "tokens": tokens
            })
            return True
        return False

    def remaining(self) -> int:
        """Return remaining token budget."""
        return self.max_tokens - self.used_tokens

    def get_summary(self) -> Dict[str, Any]:
        """Get budget usage summary."""
        by_tier = {}
        for item in self.items_included:
            tier = item["tier"]
            by_tier[tier] = by_tier.get(tier, 0) + 1

        return {
            "max_tokens": self.max_tokens,
            "used_tokens": self.used_tokens,
            "remaining": self.remaining(),
            "total_items": len(self.items_included),
            "by_tier": by_tier
        }
