from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any, Optional
import uuid

class VectorStore:
    def __init__(self, location: str = "data/qdrant_storage", dimension: int = 1536):
        self.client = QdrantClient(path=location)
        self.collection_name = "memcore_memories"
        self.dimension = dimension
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )
        else:
            # Verify dimension matches if collection exists
            info = self.client.get_collection(self.collection_name)
            existing_dim = info.config.params.vectors.size
            if existing_dim != self.dimension:
                print(f"Warning: Collection dimension {existing_dim} != expected {self.dimension}.")

    def upsert_memory(self, id: str, vector: List[float], payload: Dict[str, Any]):
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    def search_memories(self, vector: List[float], limit: int = 5, filter_quadrants: Optional[List[str]] = None):
        search_filter = None
        if filter_quadrants:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            # Search for any of the provided quadrants
            search_filter = Filter(
                should=[
                    FieldCondition(key="quadrants", match=MatchValue(value=q))
                    for q in filter_quadrants
                ]
            )
        
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True
        )
        return result.points

    def get_raw_memories(self, limit: int = 100):
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(key="type", match=MatchValue(value="raw"))
            ]
        )
        # Scroll returns all points matching the filter
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=search_filter,
            limit=limit,
            with_payload=True
        )
        return results

    def get_memory_by_id(self, id: str):
        return self.client.retrieve(
            collection_name=self.collection_name,
            ids=[id]
        )

    def delete_memories_by_source(self, source_uri: str):
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="source_uri", match=MatchValue(value=source_uri))
                ]
            )
        )

    def delete_memory(self, memory_id: str):
        """Delete a single memory by ID."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[memory_id]
        )

    def update_memory(self, memory_id: str, payload: Dict[str, Any]):
        """Update a memory's payload."""
        self.client.set_payload(
            collection_name=self.collection_name,
            payload=payload,
            points=[memory_id]
        )

    def update_memory_access(self, memory_id: str):
        """Updates the last_accessed timestamp for a memory."""
        from datetime import datetime
        self.client.set_payload(
            collection_name=self.collection_name,
            payload={"last_accessed": datetime.now().isoformat()},
            points=[memory_id]
        )

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about the vector store."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            total_count = collection_info.points_count

            # Optimized quadrant counts using Qdrant's count API
            quadrants_count = {}
            for q in ["coding", "personal", "research", "ai_instructions"]:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                count = self.client.count(
                    collection_name=self.collection_name,
                    count_filter=Filter(
                        must=[FieldCondition(key="quadrants", match=MatchValue(value=q))]
                    )
                ).count
                if count > 0:
                    quadrants_count[q] = count

            # Type counts - sample first 100 for variety
            types_count = {}
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                with_payload=True
            )
            for res in results:
                t = res.payload.get("type", "raw")
                types_count[t] = types_count.get(t, 0) + 1

            return {
                "total_memories": total_count,
                "by_type": types_count,
                "by_quadrant": quadrants_count,
                "dimension": self.dimension,
                "collection_name": self.collection_name
            }
        except Exception as e:
            print(f"Error getting vector stats: {e}")
            return {"error": str(e), "total_memories": 0}
