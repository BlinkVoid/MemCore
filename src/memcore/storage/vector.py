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
                # In a real app, we might want to migrate or use a different collection name

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
        
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True
        )

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

    def update_memory_access(self, memory_id: str):
        """Updates the last_accessed timestamp for a memory."""
        from datetime import datetime
        self.client.set_payload(
            collection_name=self.collection_name,
            payload={"last_accessed": datetime.now().isoformat()},
            points=[memory_id]
        )
