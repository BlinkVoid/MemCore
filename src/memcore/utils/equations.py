import math
from datetime import datetime
from typing import Optional

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
