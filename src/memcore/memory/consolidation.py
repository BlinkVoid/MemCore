"""
Memory Consolidation Pipeline - STM to LTM conversion with stateful queue.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid

from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.storage.queue import ConsolidationQueue, JobStatus


class MemoryConsolidator:
    """
    Multi-stage memory consolidation with stateful queue support.
    
    Pipeline:
    1. Raw memories are enqueued for processing
    2. Jobs are dequeued and processed (extract → deduplicate → resolve → store)
    3. Results marked as completed or failed for retry
    """
    
    def __init__(self, llm: LLMInterface, vector_store: VectorStore, 
                 graph_store: GraphStore, queue: Optional[ConsolidationQueue] = None):
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.queue = queue or ConsolidationQueue()
    
    async def queue_raw_memories(self, raw_memories: List[Dict[str, Any]]) -> List[str]:
        """
        Queue raw memories for consolidation instead of processing immediately.
        
        Args:
            raw_memories: List of memory dicts with memory_id, content, summary, quadrants
        
        Returns:
            List of job IDs
        """
        if not raw_memories:
            return []
        
        # Prepare memories for batch enqueue
        memories_for_queue = []
        for mem in raw_memories:
            memories_for_queue.append({
                "memory_id": mem["id"],
                "content": mem["content"],
                "summary": mem["summary"],
                "quadrants": mem.get("quadrants", ["general"]),
                "source_uri": mem.get("source_uri"),
                "importance": mem.get("importance", 0.5),
                "max_retries": 3
            })
        
        job_ids = self.queue.enqueue_batch(memories_for_queue)
        print(f"[Consolidator] Queued {len(job_ids)} memories for consolidation")
        return job_ids
    
    async def process_queue(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Process pending jobs from the queue.
        
        Args:
            batch_size: Number of jobs to process in this batch
        
        Returns:
            Summary of processing results
        """
        jobs = self.queue.dequeue(limit=batch_size)
        
        if not jobs:
            return {"processed": 0, "completed": 0, "failed": 0}
        
        results = {"processed": len(jobs), "completed": 0, "failed": 0, "errors": []}
        
        for job in jobs:
            try:
                await self._process_job(job)
                self.queue.mark_completed(job["id"], {"memory_id": job["memory_id"]})
                results["completed"] += 1
                
                # Mark raw memory as archived in vector store
                self.vector_store.client.set_payload(
                    collection_name=self.vector_store.collection_name,
                    payload={"type": "archived_raw"},
                    points=[job["memory_id"]]
                )
                
            except Exception as e:
                error_msg = str(e)
                self.queue.mark_failed(job["id"], error_msg)
                results["failed"] += 1
                results["errors"].append({
                    "job_id": job["id"],
                    "memory_id": job["memory_id"],
                    "error": error_msg
                })
                print(f"[Consolidator] Job {job['id']} failed: {error_msg}")
        
        return results
    
    async def _process_job(self, job: Dict[str, Any]):
        """Process a single consolidation job through the pipeline."""
        # Stage 1: Fact & Instruction Extraction
        extracted = await self._stage_extract({
            "id": job["memory_id"],
            "content": job["memory_content"],
            "summary": job["memory_summary"],
            "quadrants": job["quadrants"],
            "source_uri": job.get("source_uri")
        })
        
        # Stage 2: Process extracted items
        for item in extracted.get("facts", []) + extracted.get("instructions", []):
            await self._process_consolidated_item(item, job)
    
    async def _stage_extract(self, raw_memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts and instructions from a raw memory using STRONG model."""
        context = f"- {raw_memory['summary']}: {raw_memory['content']}"
        
        prompt = f"""
        Extract atomic facts and procedural instructions from this memory.
        
        Memory:
        {context}
        
        Source Quadrants: {', '.join(raw_memory.get('quadrants', ['general']))}
        
        Guidelines:
        - Facts: Objective information about the user, preferences, projects, etc.
        - Instructions: SOPs, coding preferences, agent behavior guidelines
        - Each item should be atomic (one concept per item)
        - Include relevant quadrants for each extracted item
        
        Return JSON:
        {{
            "facts": [
                {{"summary": "brief title", "content": "full fact", "quadrants": ["personal"]}}
            ],
            "instructions": [
                {{"summary": "brief title", "content": "full instruction", "quadrants": ["ai_instructions"]}}
            ]
        }}
        """
        
        response = await self.llm.completion(
            messages=[
                {"role": "system", "content": "You are a memory analyst specializing in fact extraction and instruction identification."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            tier="strong"
        )
        
        return json.loads(response)
    
    async def _process_consolidated_item(self, item: Dict[str, Any], source_job: Dict[str, Any]):
        """Process a single extracted item - check for conflicts and store."""
        # Search for potentially conflicting or redundant info in LTM
        item_vector = await self.llm.get_embedding(item["content"])
        
        filter_quadrant = item["quadrants"][0] if item.get("quadrants") else None
        existing = self.vector_store.search_memories(
            item_vector, 
            limit=3, 
            filter_quadrants=[filter_quadrant] if filter_quadrant else None
        )
        
        if existing:
            # Stage 3: Conflict Resolution & Merging
            await self._resolve_and_merge(item, existing, source_job)
        else:
            # Stage 4: New LTM Entry
            await self._store_ltm(item, item_vector, source_job.get("source_uri"))
    
    async def _resolve_and_merge(self, new_item: Dict[str, Any], 
                                  existing_items: List[Any],
                                  source_job: Dict[str, Any]):
        """Resolve conflicts between new and existing memories."""
        existing_context = "\n".join([
            f"ID {e.id}: {e.payload.get('content', 'N/A')}" 
            for e in existing_items
        ])
        
        prompt = f"""
        Compare this NEW information with EXISTING knowledge.
        
        NEW: {new_item['content']}
        
        EXISTING:
        {existing_context}
        
        Decide:
        1. DUPLICATE: New info is already known (no action needed).
        2. CONFLICT: New info contradicts existing (both should be kept, marked as conflict).
        3. REFINEMENT: New info adds detail or updates existing (merge into existing).
        
        Return JSON:
        {{
            "action": "DUPLICATE|CONFLICT|REFINEMENT",
            "resolution": "merged content if REFINEMENT",
            "target_id": "existing_id_if_applicable",
            "reason": "brief explanation"
        }}
        """
        
        response = await self.llm.completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            tier="strong"
        )
        
        res = json.loads(response)
        action = res.get("action", "DUPLICATE")
        
        if action == "REFINEMENT" and res.get("target_id"):
            # Update the existing entry
            updated_vector = await self.llm.get_embedding(res["resolution"])
            new_payload = {
                "content": res["resolution"],
                "summary": new_item["summary"],
                "quadrants": new_item.get("quadrants", ["general"]),
                "importance": 0.9,
                "type": "consolidated",
                "source_uri": source_job.get("source_uri"),
                "updated_at": datetime.now().isoformat(),
                "consolidated_from": source_job["memory_id"]
            }
            self.vector_store.upsert_memory(res["target_id"], updated_vector, new_payload)
            
            # Add to graph as refinement relationship
            self.graph_store.add_edge(
                source_job["memory_id"], 
                res["target_id"], 
                "REFINES",
                metadata={"reason": res.get("reason", "")}
            )
            
        elif action == "CONFLICT":
            # Store new memory and mark conflict
            new_id = await self._store_ltm(
                new_item, 
                source_uri=source_job.get("source_uri"),
                parent_job=source_job
            )
            
            target_id = res.get("target_id")
            if target_id:
                self.graph_store.add_edge(
                    new_id, 
                    target_id, 
                    "CONTRADICTS",
                    metadata={"reason": res.get("reason", "")}
                )
                
        elif action == "DUPLICATE":
            # Just link the raw memory to the existing one
            if res.get("target_id"):
                self.graph_store.add_edge(
                    source_job["memory_id"],
                    res["target_id"],
                    "DUPLICATE_OF"
                )
    
    async def _store_ltm(self, item: Dict[str, Any], 
                         vector: Optional[List[float]] = None,
                         source_uri: Optional[str] = None,
                         parent_job: Optional[Dict] = None) -> str:
        """Store a new long-term memory."""
        new_id = str(uuid.uuid4())
        
        if not vector:
            vector = await self.llm.get_embedding(item["content"])
        
        # Determine importance based on quadrant
        quadrants = item.get("quadrants", ["general"])
        importance = 1.0 if "ai_instructions" in quadrants else 0.9
        
        payload = {
            "content": item["content"],
            "summary": item["summary"],
            "quadrants": quadrants,
            "importance": importance,
            "source_uri": source_uri or item.get("source_uri"),
            "type": "consolidated",
            "created_at": datetime.now().isoformat()
        }
        
        if parent_job:
            payload["consolidated_from"] = parent_job["memory_id"]
        
        self.vector_store.upsert_memory(new_id, vector, payload)
        self.graph_store.add_node(
            new_id,
            "memory",
            {"summary": item["summary"], "type": "consolidated"},
            source_uri=payload["source_uri"]
        )
        
        return new_id
    
    async def consolidate(self, raw_memories: List[Dict[str, Any]], 
                          use_queue: bool = True) -> Dict[str, Any]:
        """
        Main entry point for consolidation.
        
        Args:
            raw_memories: List of raw memories to consolidate
            use_queue: If True, queue for later processing. If False, process immediately.
        
        Returns:
            Summary of consolidation operation
        """
        if not raw_memories:
            return {"status": "no_op", "message": "No memories to consolidate"}
        
        if use_queue:
            # Queue for background processing
            job_ids = await self.queue_raw_memories(raw_memories)
            return {
                "status": "queued",
                "jobs_created": len(job_ids),
                "pending_in_queue": self.queue.get_pending_count()
            }
        else:
            # Process immediately (synchronous mode for testing/small batches)
            results = {"processed": 0, "completed": 0, "failed": 0}
            
            for memory in raw_memories:
                try:
                    extracted = await self._stage_extract(memory)
                    for item in extracted.get("facts", []) + extracted.get("instructions", []):
                        await self._process_consolidated_item(item, {
                            "memory_id": memory["id"],
                            "source_uri": memory.get("source_uri")
                        })
                    results["completed"] += 1
                except Exception as e:
                    results["failed"] += 1
                    print(f"[Consolidator] Immediate processing failed: {e}")
                
                results["processed"] += 1
            
            return {"status": "immediate", **results}
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the consolidation queue."""
        return self.queue.get_stats()
    
    def recover_from_crash(self) -> int:
        """
        Reset processing jobs to pending (call on startup).
        
        Returns:
            Number of jobs reset
        """
        return self.queue.reset_processing_jobs()
