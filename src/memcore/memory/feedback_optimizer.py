"""
Phase 4: Feedback-Driven Optimization System

Root Cause Analysis (RCA) expansion and Global Score Adjustment for auto-tuning
memory retrieval weights based on historical accuracy.

The system tracks feedback over time and adjusts the relative importance of:
- W_rel (Relevance weight): Semantic similarity importance
- W_rec (Recency weight): Temporal decay importance
- W_imp (Importance weight): User-defined importance
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import json


class FailureType(Enum):
    """Categories of retrieval failures identified by RCA."""
    IRRELEVANCE = "irrelevance"      # Semantic search returned unrelated info
    OBSOLESCENCE = "obsolescence"    # Info is outdated
    NOISE = "noise"                  # Too much detail, not enough gist
    WRONG_QUADRANT = "wrong_quadrant"  # Wrong quadrant classification
    RANKING_ERROR = "ranking_error"  # Correct memory exists but ranked too low
    DUPLICATE = "duplicate"          # Redundant with existing memories
    UNKNOWN = "unknown"              # Cannot determine cause


class AdjustmentType(Enum):
    """Types of weight adjustments."""
    INCREASE_RELEVANCE = "increase_relevance"
    DECREASE_RELEVANCE = "decrease_relevance"
    INCREASE_RECENCY = "increase_recency"
    DECREASE_RECENCY = "decrease_recency"
    INCREASE_IMPORTANCE = "increase_importance"
    DECREASE_IMPORTANCE = "decrease_importance"


class FeedbackRecord:
    """Record of a single feedback event."""

    def __init__(
        self,
        request_id: str,
        memory_id: str,
        rating: int,
        reason: str,
        failure_type: Optional[FailureType] = None,
        suggested_adjustment: Optional[AdjustmentType] = None,
        weights_at_time: Optional[Dict[str, float]] = None
    ):
        self.request_id = request_id
        self.memory_id = memory_id
        self.rating = rating
        self.reason = reason
        self.failure_type = failure_type
        self.suggested_adjustment = suggested_adjustment
        self.weights_at_time = weights_at_time or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "memory_id": self.memory_id,
            "rating": self.rating,
            "reason": self.reason,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "suggested_adjustment": self.suggested_adjustment.value if self.suggested_adjustment else None,
            "weights_at_time": self.weights_at_time,
            "timestamp": self.timestamp
        }


class RootCauseAnalyzer:
    """
    Performs structured Root Cause Analysis on negative feedback.

    Uses LLM to categorize failures and suggest weight adjustments.
    """

    def __init__(self, llm):
        self.llm = llm

    async def analyze(
        self,
        query: str,
        memory_summary: str,
        memory_content: str,
        reason: str,
        current_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Perform RCA on a retrieval failure.

        Returns structured analysis with failure type and adjustment suggestion.
        """
        prompt = f"""
        Perform Root Cause Analysis on this memory retrieval failure.

        QUERY: {query}

        RETRIEVED MEMORY:
        Summary: {memory_summary}
        Content: {memory_content[:500]}...

        USER FEEDBACK: {reason}

        CURRENT WEIGHTS:
        - Relevance (W_rel): {current_weights.get('W_rel', 0.5)}
        - Recency (W_rec): {current_weights.get('W_rec', 0.3)}
        - Importance (W_imp): {current_weights.get('W_imp', 0.2)}

        Analyze the failure and categorize it:

        1. FAILURE TYPE (choose one):
           - IRRELEVANCE: Memory was semantically unrelated to query
           - OBSOLESCENCE: Memory was relevant but outdated
           - NOISE: Memory had too much detail, missed the key point
           - WRONG_QUADRANT: Query was miscategorized (e.g., coding query got personal memory)
           - RANKING_ERROR: Correct memory exists but wasn't top-ranked
           - DUPLICATE: Memory was redundant with better alternatives
           - UNKNOWN: Cannot determine from available info

        2. ROOT CAUSE: Brief explanation of why this happened

        3. SUGGESTED ADJUSTMENT (choose one):
           - increase_relevance: If semantic matching failed
           - decrease_relevance: If semantic matching is over-prioritized
           - increase_recency: If old memories are ranking too high
           - decrease_recency: If new memories are ranking too high
           - increase_importance: If user preferences aren't being respected
           - decrease_importance: If importance is over-prioritized
           - none: If weights aren't the issue

        Return JSON:
        {{
            "failure_type": "irrelevance|obsolescence|noise|wrong_quadrant|ranking_error|duplicate|unknown",
            "root_cause": "explanation",
            "suggested_adjustment": "increase_relevance|decrease_relevance|increase_recency|decrease_recency|increase_importance|decrease_importance|none",
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

            # Parse failure type
            failure_type_str = result.get("failure_type", "unknown")
            try:
                failure_type = FailureType(failure_type_str)
            except ValueError:
                failure_type = FailureType.UNKNOWN

            # Parse adjustment
            adjustment_str = result.get("suggested_adjustment", "none")
            try:
                adjustment = AdjustmentType(adjustment_str) if adjustment_str != "none" else None
            except ValueError:
                adjustment = None

            return {
                "failure_type": failure_type,
                "root_cause": result.get("root_cause", "Unknown"),
                "suggested_adjustment": adjustment,
                "confidence": result.get("confidence", "medium")
            }

        except Exception as e:
            print(f"[RCA] Analysis failed: {e}")
            return {
                "failure_type": FailureType.UNKNOWN,
                "root_cause": f"Analysis error: {e}",
                "suggested_adjustment": None,
                "confidence": "low"
            }


class GlobalScoreAdjuster:
    """
    Manages global weight adjustments based on historical feedback.

    Automatically tunes W_rel, W_rec, W_imp based on accumulated feedback.
    """

    # Default weights
    DEFAULT_W_REL = 0.5
    DEFAULT_W_REC = 0.3
    DEFAULT_W_IMP = 0.2

    # Adjustment increment (how much to adjust per feedback)
    ADJUSTMENT_STEP = 0.05

    # Maximum deviation from defaults
    MAX_DEVIATION = 0.2

    def __init__(self, graph_store):
        self.graph_store = graph_store
        self._weights = None  # Cache

    def get_current_weights(self) -> Dict[str, float]:
        """Get current weights from graph store or defaults."""
        if self._weights is not None:
            return self._weights.copy()

        stored = self.graph_store.get_metadata("score_weights")
        if stored:
            try:
                if isinstance(stored, str):
                    self._weights = json.loads(stored)
                else:
                    self._weights = stored
                return self._weights.copy()
            except:
                pass

        # Return defaults
        return {
            "W_rel": self.DEFAULT_W_REL,
            "W_rec": self.DEFAULT_W_REC,
            "W_imp": self.DEFAULT_W_IMP
        }

    def _save_weights(self, weights: Dict[str, float]):
        """Save weights to graph store."""
        self.graph_store.set_metadata("score_weights", json.dumps(weights))
        self._weights = weights.copy()

    def adjust_weight(self, adjustment_type: AdjustmentType) -> Dict[str, float]:
        """
        Apply a weight adjustment.

        Returns the new weights after adjustment.
        """
        weights = self.get_current_weights()

        if adjustment_type == AdjustmentType.INCREASE_RELEVANCE:
            weights["W_rel"] = min(
                self.DEFAULT_W_REL + self.MAX_DEVIATION,
                weights["W_rel"] + self.ADJUSTMENT_STEP
            )
        elif adjustment_type == AdjustmentType.DECREASE_RELEVANCE:
            weights["W_rel"] = max(
                self.DEFAULT_W_REL - self.MAX_DEVIATION,
                weights["W_rel"] - self.ADJUSTMENT_STEP
            )
        elif adjustment_type == AdjustmentType.INCREASE_RECENCY:
            weights["W_rec"] = min(
                self.DEFAULT_W_REC + self.MAX_DEVIATION,
                weights["W_rec"] + self.ADJUSTMENT_STEP
            )
        elif adjustment_type == AdjustmentType.DECREASE_RECENCY:
            weights["W_rec"] = max(
                self.DEFAULT_W_REC - self.MAX_DEVIATION,
                weights["W_rec"] - self.ADJUSTMENT_STEP
            )
        elif adjustment_type == AdjustmentType.INCREASE_IMPORTANCE:
            weights["W_imp"] = min(
                self.DEFAULT_W_IMP + self.MAX_DEVIATION,
                weights["W_imp"] + self.ADJUSTMENT_STEP
            )
        elif adjustment_type == AdjustmentType.DECREASE_IMPORTANCE:
            weights["W_imp"] = max(
                self.DEFAULT_W_IMP - self.MAX_DEVIATION,
                weights["W_imp"] - self.ADJUSTMENT_STEP
            )

        # Normalize to ensure sum = 1.0
        total = weights["W_rel"] + weights["W_rec"] + weights["W_imp"]
        weights["W_rel"] /= total
        weights["W_rec"] /= total
        weights["W_imp"] /= total

        self._save_weights(weights)
        return weights

    def get_adjustment_summary(self, window_days: int = 7) -> Dict[str, Any]:
        """
        Get summary of recent adjustments and current accuracy.

        Returns statistics about feedback and weight adjustments.
        """
        feedback_records = self._load_feedback_history(window_days)

        if not feedback_records:
            return {
                "period_days": window_days,
                "total_feedback": 0,
                "positive_ratio": None,
                "most_common_failure": None,
                "current_weights": self.get_current_weights(),
                "adjustments_made": 0
            }

        # Calculate statistics
        positive_count = sum(1 for f in feedback_records if f.rating > 0)
        negative_count = sum(1 for f in feedback_records if f.rating < 0)
        total = len(feedback_records)

        # Most common failure type
        failure_counts = {}
        for f in feedback_records:
            if f.failure_type:
                ft = f.failure_type.value
                failure_counts[ft] = failure_counts.get(ft, 0) + 1

        most_common = max(failure_counts.items(), key=lambda x: x[1])[0] if failure_counts else None

        # Count adjustments
        adjustments = sum(1 for f in feedback_records if f.suggested_adjustment is not None)

        return {
            "period_days": window_days,
            "total_feedback": total,
            "positive_ratio": positive_count / total if total > 0 else 0,
            "negative_count": negative_count,
            "most_common_failure": most_common,
            "failure_breakdown": failure_counts,
            "current_weights": self.get_current_weights(),
            "adjustments_made": adjustments
        }

    def _load_feedback_history(self, window_days: int) -> List[FeedbackRecord]:
        """Load feedback records from graph store."""
        stored = self.graph_store.get_metadata("feedback_history")
        if not stored:
            return []

        try:
            if isinstance(stored, str):
                records_data = json.loads(stored)
            else:
                records_data = stored

            cutoff = datetime.now() - timedelta(days=window_days)

            records = []
            for data in records_data:
                try:
                    timestamp = datetime.fromisoformat(data.get("timestamp", ""))
                    if timestamp >= cutoff:
                        record = FeedbackRecord(
                            request_id=data["request_id"],
                            memory_id=data["memory_id"],
                            rating=data["rating"],
                            reason=data["reason"],
                            failure_type=FailureType(data["failure_type"]) if data.get("failure_type") else None,
                            suggested_adjustment=AdjustmentType(data["suggested_adjustment"]) if data.get("suggested_adjustment") else None,
                            weights_at_time=data.get("weights_at_time", {})
                        )
                        record.timestamp = data["timestamp"]
                        records.append(record)
                except:
                    continue

            return records
        except:
            return []

    def record_feedback(self, feedback: FeedbackRecord):
        """Record feedback to history."""
        # Load existing history
        stored = self.graph_store.get_metadata("feedback_history")
        history = []
        if stored:
            try:
                history = json.loads(stored) if isinstance(stored, str) else stored
            except:
                history = []

        # Add new record
        history.append(feedback.to_dict())

        # Keep only last 1000 records to prevent bloat
        history = history[-1000:]

        # Save back
        self.graph_store.set_metadata("feedback_history", json.dumps(history))


class FeedbackOptimizer:
    """
    Main interface for Phase 4 feedback optimization.

    Combines RCA and Global Score Adjustment into a unified system.
    """

    def __init__(self, llm, graph_store):
        self.rca = RootCauseAnalyzer(llm)
        self.adjuster = GlobalScoreAdjuster(graph_store)
        self.llm = llm
        self.graph_store = graph_store

    async def process_negative_feedback(
        self,
        request_id: str,
        memory_id: str,
        reason: str,
        query: str,
        memory_summary: str,
        memory_content: str
    ) -> Dict[str, Any]:
        """
        Process negative feedback with full RCA and weight adjustment.

        Returns analysis results and any weight changes made.
        """
        current_weights = self.adjuster.get_current_weights()

        # Perform RCA
        analysis = await self.rca.analyze(
            query=query,
            memory_summary=memory_summary,
            memory_content=memory_content,
            reason=reason,
            current_weights=current_weights
        )

        # Record feedback
        feedback = FeedbackRecord(
            request_id=request_id,
            memory_id=memory_id,
            rating=-1,
            reason=reason,
            failure_type=analysis["failure_type"],
            suggested_adjustment=analysis["suggested_adjustment"],
            weights_at_time=current_weights
        )
        self.adjuster.record_feedback(feedback)

        # Apply weight adjustment if suggested
        new_weights = None
        if analysis["suggested_adjustment"] and analysis["confidence"] in ["high", "medium"]:
            new_weights = self.adjuster.adjust_weight(analysis["suggested_adjustment"])

        return {
            "feedback_recorded": True,
            "failure_type": analysis["failure_type"].value,
            "root_cause": analysis["root_cause"],
            "confidence": analysis["confidence"],
            "previous_weights": current_weights,
            "new_weights": new_weights,
            "adjustment_applied": new_weights is not None
        }

    def get_optimization_report(self, window_days: int = 7) -> Dict[str, Any]:
        """Get comprehensive optimization report."""
        return self.adjuster.get_adjustment_summary(window_days)

    def get_current_weights(self) -> Dict[str, float]:
        """Get current scoring weights."""
        return self.adjuster.get_current_weights()
