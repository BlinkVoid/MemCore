from typing import List, Dict, Any, Optional
from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
import json
import uuid

class MemoryConsolidator:
    def __init__(self, llm: LLMInterface, vector_store: VectorStore, graph_store: GraphStore):
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def consolidate(self, raw_memories: List[Dict[str, Any]]):
        """
        Multi-stage consolidation pipeline.
        """
        if not raw_memories:
            return

        # Stage 1: Fact & Instruction Extraction (using STRONG model)
        extracted_data = await self._stage_extract(raw_memories)
        
        # Stage 2: Conflict Detection & Synthesis
        for item in extracted_data.get("facts", []) + extracted_data.get("instructions", []):
            await self._process_consolidated_item(item)

    async def _stage_extract(self, raw_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        context = "\n".join([f"- {m['summary']}: {m['content']}" for m in raw_memories])
        prompt = f"""
        Extract facts and procedural instructions from these memories.
        
        Raw Memories:
        {context}
        
        Return JSON: {{"facts": [...], "instructions": [...]}}
        Each item must have "summary", "content", and "quadrants".
        """
        response = await self.llm.completion(
            messages=[{"role": "system", "content": "You are a memory analyst."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            tier="strong"
        )
        return json.loads(response)

    async def _process_consolidated_item(self, item: Dict[str, Any]):
        # Search for potentially conflicting or redundant info in LTM
        item_vector = await self.llm.get_embedding(item["content"])
        existing = self.vector_store.search_memories(item_vector, limit=3, filter_quadrant=item["quadrants"][0] if item["quadrants"] else None)
        
        if existing:
            # Stage 3: Conflict Resolution & Merging
            await self._resolve_and_merge(item, existing)
        else:
            # Stage 4: New LTM Entry
            await self._store_ltm(item, item_vector)

    async def _resolve_and_merge(self, new_item: Dict[str, Any], existing_items: List[Any]):
        # Use LLM to decide if it's a conflict, a duplicate, or a refinement
        existing_context = "\n".join([f"ID {e.id}: {e.payload['content']}" for e in existing_items])
        
        prompt = f"""
        Compare this NEW information with EXISTING knowledge.
        
        NEW: {new_item['content']}
        
        EXISTING:
        {existing_context}
        
        Decide:
        1. DUPLICATE: New info is already known.
        2. CONFLICT: New info contradicts existing.
        3. REFINEMENT: New info adds detail or updates existing.
        
        Return JSON: {{"action": "DUPLICATE|CONFLICT|REFINEMENT", "resolution": "the merged content if applicable", "target_id": "existing_id_if_applicable"}}
        """
        
        response = await self.llm.completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            tier="strong"
        )
        res = json.loads(response)
        
        if res["action"] == "REFINEMENT" and res.get("target_id"):
            # Update the existing entry
            updated_vector = await self.llm.get_embedding(res["resolution"])
            new_payload = {
                "content": res["resolution"],
                "summary": new_item["summary"],
                "quadrants": new_item["quadrants"],
                "importance": 0.9,
                "type": "consolidated",
                "source_uri": new_item.get("source_uri"),
                "updated_at": datetime.now().isoformat()
            }
            self.vector_store.upsert_memory(res["target_id"], updated_vector, new_payload)
        elif res["action"] == "CONFLICT":
            # Store as conflict node in graph and alert user via metadata
            new_id = await self._store_ltm(new_item, source_uri=new_item.get("source_uri"))
            self.graph_store.add_edge(new_id, res["target_id"], "CONTRASTED_WITH")

    async def _store_ltm(self, item: Dict[str, Any], vector: Optional[List[float]] = None, source_uri: Optional[str] = None) -> str:
        new_id = str(uuid.uuid4())
        if not vector:
            vector = await self.llm.get_embedding(item["content"])
        
        payload = {
            "content": item["content"],
            "summary": item["summary"],
            "quadrants": item["quadrants"],
            "importance": 0.9 if "ai_instructions" not in item["quadrants"] else 1.0,
            "source_uri": source_uri or item.get("source_uri"),
            "type": "consolidated"
        }
        self.vector_store.upsert_memory(new_id, vector, payload)
        self.graph_store.add_node(
            new_id, 
            "memory", 
            {"summary": item["summary"], "type": "consolidated"},
            source_uri=payload["source_uri"]
        )
        return new_id

from datetime import datetime
