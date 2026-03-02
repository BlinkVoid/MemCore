from typing import List, Dict, Any, Optional
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.utils.equations import (
    calculate_importance_score, calculate_recency_score, TokenBudget, estimate_tokens
)
from datetime import datetime

class TieredContextManager:
    def __init__(self, vector_store: VectorStore, graph_store: Optional[GraphStore] = None):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.default_token_budget = 4000  # Default max tokens for context

    async def get_l0_context(self, query_vector: List[float], quadrants: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Returns L0 (Index/Summary) - high level map of available memories."""
        results = self.vector_store.search_memories(query_vector, limit=10, filter_quadrants=quadrants)
        l0_list = []
        for res in results:
            l0_list.append({
                "id": res.id,
                "summary": res.payload.get("summary"),
                "quadrants": res.payload.get("quadrants"),
                "score": res.score,
                "type": res.payload.get("type", "raw"),
                "importance": res.payload.get("importance", 0.5),
                "last_accessed": res.payload.get("last_accessed")
            })
        return l0_list

    async def get_l1_context(self, memory_ids: List[str]) -> List[Dict[str, Any]]:
        """Returns L1 (Snippet/Overview) - brief summaries of relevant memory clusters."""
        l1_list = []
        for mid in memory_ids:
            res = self.vector_store.get_memory_by_id(mid)
            if res:
                payload = res[0].payload
                l1_list.append({
                    "id": mid,
                    "overview": payload.get("overview"),
                    "importance": payload.get("importance", 0.5)
                })
        return l1_list

    async def get_l2_context(self, memory_id: str) -> Dict[str, Any]:
        """Returns L2 (Full Detail) - revealed only when explicitly requested."""
        res = self.vector_store.get_memory_by_id(memory_id)
        if res:
            return res[0].payload.get("content", {})
        return {}

    def score_memories(self, l0_results: List[Dict[str, Any]], relevance_weight: float = 1.0,
                       request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Applies the Importance Equation to rank retrieved memories.

        Includes dynamic relevancy boost from graph edge weights when graph_store
        is available. Positive feedback on a memory increases its score.
        """
        scored_results = []

        # Get dynamic weights from graph if available
        dynamic_weights = {}
        if self.graph_store and l0_results:
            memory_ids = [item["id"] for item in l0_results]
            dynamic_weights = self.graph_store.get_memory_weights(memory_ids, request_id)

        for item in l0_results:
            last_accessed_str = item.get("last_accessed")
            if last_accessed_str:
                last_accessed = datetime.fromisoformat(last_accessed_str)
            else:
                last_accessed = datetime.now()

            recency = calculate_recency_score(last_accessed)
            importance = item.get("importance", 0.5)

            # Calculate base score using Importance Equation
            base_score = calculate_importance_score(
                relevance=item["score"],
                recency=recency,
                importance=importance,
                w_rel=relevance_weight
            )

            # Apply dynamic weight multiplier from graph feedback
            weight_multiplier = dynamic_weights.get(item["id"], 1.0)
            final_score = base_score * weight_multiplier

            item["final_score"] = final_score
            item["dynamic_boost"] = weight_multiplier  # Track for debugging
            scored_results.append(item)

        return sorted(scored_results, key=lambda x: x["final_score"], reverse=True)

    async def get_progressive_context(
        self,
        query_vector: List[float],
        quadrants: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        min_confidence: float = 0.5,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Progressive tiered retrieval with token budgeting.

        Strategy:
        1. Retrieve L0 (Index) results
        2. Score and rank memories
        3. Auto-promote high-confidence L0 -> L1 (content preview)
        4. Include L1 content up to token budget
        5. Track remaining budget for explicit L2 fetches

        Args:
            query_vector: Embedding of the query
            quadrants: Optional quadrant filter
            max_tokens: Token budget (defaults to self.default_token_budget)
            min_confidence: Minimum score threshold for inclusion
            request_id: Optional request ID for dynamic scoring

        Returns:
            Dict with context tiers and budget info
        """
        budget = TokenBudget(max_tokens or self.default_token_budget)

        # 1. Get and score L0 results
        l0_results = await self.get_l0_context(query_vector, quadrants=quadrants)
        scored_memories = self.score_memories(l0_results, request_id=request_id)

        # Filter by confidence threshold
        qualified_memories = [m for m in scored_memories if m["final_score"] >= min_confidence]

        # 2. Progressive disclosure: L0 -> L1
        l0_included = []
        l1_included = []

        # Always include top 3 at L0 level (minimal tokens)
        for mem in qualified_memories[:3]:
            summary = f"[{mem['id']}] {mem['summary']}"
            if budget.add(mem["id"], summary, "L0"):
                l0_included.append({
                    "id": mem["id"],
                    "summary": mem["summary"],
                    "score": mem["final_score"],
                    "quadrants": mem.get("quadrants", []),
                    "type": mem.get("type", "raw"),
                    "boost": mem.get("dynamic_boost", 1.0)
                })

        # 3. Auto-promote high-confidence memories to L1 (add content preview)
        high_confidence = [m for m in qualified_memories if m["final_score"] >= 0.8][:5]

        for mem in high_confidence:
            # Fetch L1 (overview/content preview)
            l1_data = await self.get_l1_context([mem["id"]])
            if l1_data and l1_data[0].get("overview"):
                overview = l1_data[0]["overview"]
            else:
                # Generate simple overview from full content
                full = await self.get_l2_context(mem["id"])
                content = full if isinstance(full, str) else str(full)
                overview = content[:200] + "..." if len(content) > 200 else content

            l1_content = f"[{mem['id']}] {mem['summary']}\n  Preview: {overview}"

            if budget.add(mem["id"], l1_content, "L1"):
                l1_included.append({
                    "id": mem["id"],
                    "summary": mem["summary"],
                    "overview": overview,
                    "score": mem["final_score"],
                    "quadrants": mem.get("quadrants", [])
                })

        # 4. Build response
        budget_summary = budget.get_summary()

        # Create formatted context string
        context_parts = []

        # Add L1 items first (more detailed)
        if l1_included:
            context_parts.append("=== Detailed Context (L1) ===")
            for item in l1_included:
                boost_str = f" [boost: {item['boost']:.2f}]" if item.get('boost', 1.0) != 1.0 else ""
                context_parts.append(f"• [{item['id']}] {item['summary']}{boost_str}")
                context_parts.append(f"  {item.get('overview', '')}")
                context_parts.append("")

        # Add remaining L0 items
        remaining_l0 = [m for m in l0_included if m["id"] not in {x["id"] for x in l1_included}]
        if remaining_l0:
            context_parts.append("=== Related Memories (L0) ===")
            for item in remaining_l0:
                boost_str = f" [boost: {item['boost']:.2f}]" if item.get('boost', 1.0) != 1.0 else ""
                context_parts.append(f"• [{item['id']}] {item['summary']}{boost_str}")
            context_parts.append("")

        # Add token budget info
        context_parts.append(f"=== Context Budget: {budget_summary['used_tokens']}/{budget_summary['max_tokens']} tokens ===")

        return {
            "l0_items": l0_included,
            "l1_items": l1_included,
            "budget": budget_summary,
            "context_string": "\n".join(context_parts),
            "l2_candidates": [m["id"] for m in qualified_memories[:5]]  # Suggest for explicit fetch
        }
