from typing import List, Dict, Any, Optional
from src.memcore.storage.vector import VectorStore
from src.memcore.utils.equations import calculate_importance_score, calculate_recency_score
from datetime import datetime

class TieredContextManager:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

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

    def score_memories(self, l0_results: List[Dict[str, Any]], relevance_weight: float = 1.0) -> List[Dict[str, Any]]:
        """Applies the Importance Equation to rank retrieved memories."""
        scored_results = []
        for item in l0_results:
            last_accessed_str = item.get("last_accessed")
            if last_accessed_str:
                last_accessed = datetime.fromisoformat(last_accessed_str)
            else:
                last_accessed = datetime.now()
                
            recency = calculate_recency_score(last_accessed)
            importance = item.get("importance", 0.5)
            
            final_score = calculate_importance_score(
                relevance=item["score"],
                recency=recency,
                importance=importance,
                w_rel=relevance_weight
            )
            item["final_score"] = final_score
            scored_results.append(item)
        
        return sorted(scored_results, key=lambda x: x["final_score"], reverse=True)
