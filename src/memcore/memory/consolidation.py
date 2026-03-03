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
from src.memcore.memory.instructions import InstructionExtractor, InstructionStore
from src.memcore.memory.reflections import ReflectionGenerator, DeduplicationEngine
from src.memcore.memory.conflicts import ConflictResolver, ConflictManager, ConflictResolution


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

        # Specialized instruction handling
        self.instruction_extractor = InstructionExtractor(llm)
        self.instruction_store = InstructionStore(vector_store, graph_store)

        # Fact synthesis and reflection generation
        self.reflection_generator = ReflectionGenerator(llm)
        self.deduplication_engine = DeduplicationEngine(llm)

        # Conflict resolution for contradictory memories
        self.conflict_resolver = ConflictResolver(llm)
        self.conflict_manager = ConflictManager(graph_store)
    
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

        # Stage 2: Process extracted items (facts and instructions)
        for item in extracted.get("facts", []) + extracted.get("instructions", []):
            await self._process_consolidated_item(item, job)

    async def process_queue_with_synthesis(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Process pending jobs with fact synthesis and reflection generation.

        This enhanced pipeline:
        1. Processes individual jobs (extract facts/instructions)
        2. Generates reflections from related facts across jobs
        3. Stores reflections with links to source memories
        """
        jobs = self.queue.dequeue(limit=batch_size)

        if not jobs:
            return {"processed": 0, "completed": 0, "failed": 0, "reflections_generated": 0}

        results = {
            "processed": len(jobs),
            "completed": 0,
            "failed": 0,
            "reflections_generated": 0,
            "errors": []
        }

        # Collect all extracted facts for synthesis
        all_facts = []

        # Stage 1: Process individual jobs
        for job in jobs:
            try:
                await self._process_job(job)
                self.queue.mark_completed(job["id"], {"memory_id": job["memory_id"]})
                results["completed"] += 1

                # Collect facts for later synthesis
                extracted = await self._stage_extract({
                    "id": job["memory_id"],
                    "content": job["memory_content"],
                    "summary": job["memory_summary"],
                    "quadrants": job["quadrants"],
                    "source_uri": job.get("source_uri")
                })
                for fact in extracted.get("facts", []):
                    all_facts.append({
                        "id": job["memory_id"],
                        **fact
                    })

                # Mark raw memory as archived
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

        # Stage 2: Generate reflections from collected facts
        if len(all_facts) >= 3:
            try:
                reflections = await self.reflection_generator.generate_reflections(all_facts)
                for reflection in reflections:
                    await self._store_reflection(reflection)
                    results["reflections_generated"] += 1
                    print(f"[Consolidator] Generated reflection: {reflection['summary']}")
            except Exception as e:
                print(f"[Consolidator] Reflection generation failed: {e}")

        return results

    async def _store_reflection(self, reflection: Dict[str, Any]):
        """Store a generated reflection with links to source memories."""
        reflection_id = reflection["id"]

        # Get embedding for the reflection
        vector = await self.llm.get_embedding(reflection["reflection"])

        # Store in vector DB with special type
        payload = {
            "content": reflection["reflection"],
            "summary": reflection["summary"],
            "quadrants": ["general"],  # Reflections can apply broadly
            "importance": 0.85,  # Reflections are important synthesized knowledge
            "type": "reflection",
            "confidence": reflection.get("confidence", "medium"),
            "pattern_type": reflection.get("pattern_type", "preference"),
            "supporting_evidence": reflection.get("supporting_evidence", ""),
            "memory_count": reflection.get("memory_count", 0),
            "source_memory_ids": reflection.get("source_memory_ids", []),
            "created_at": reflection.get("created_at", datetime.now().isoformat())
        }

        self.vector_store.upsert_memory(reflection_id, vector, payload)

        # Add to graph
        self.graph_store.add_node(
            reflection_id,
            "reflection",
            {
                "summary": reflection["summary"],
                "pattern_type": reflection.get("pattern_type"),
                "confidence": reflection.get("confidence")
            }
        )

        # Link reflection to source memories
        for source_id in reflection.get("source_memory_ids", []):
            self.graph_store.add_edge(
                reflection_id,
                source_id,
                "DERIVED_FROM",
                metadata={"type": "synthesis"}
            )
    
    async def _stage_extract(self, raw_memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract facts and instructions from a raw memory using STRONG model.

        Uses specialized instruction extraction pipeline for ai_instructions quadrant.
        """
        raw_content = raw_memory['content']
        context = f"- {raw_memory['summary']}: {raw_content}"

        # Check if this memory might contain instructions
        quadrants = raw_memory.get('quadrants', ['general'])
        has_instruction_quadrant = 'ai_instructions' in quadrants

        # Extract instructions using specialized pipeline if relevant
        instructions = []
        if has_instruction_quadrant:
            extracted_instructions = await self.instruction_extractor.extract(
                raw_content,
                context=f"Source: {raw_memory.get('source_uri', 'unknown')}"
            )
            # Convert to standard format
            for instr in extracted_instructions:
                instructions.append({
                    "summary": instr["summary"],
                    "content": instr["content"],
                    "quadrants": ["ai_instructions"],
                    "_instruction_meta": instr  # Keep full metadata
                })

        # Extract facts using standard method
        prompt = f"""
        Extract atomic facts from this memory.

        Memory:
        {context}

        Source Quadrants: {', '.join(quadrants)}

        Guidelines:
        - Facts: Objective information about the user, preferences, projects, etc.
        - Focus on "what is true" not "what to do"
        - Each item should be atomic (one concept per item)
        - Include relevant quadrants for each extracted item

        Return JSON:
        {{
            "facts": [
                {{"summary": "brief title", "content": "full fact", "quadrants": ["personal"]}}
            ]
        }}
        """

        response = await self.llm.completion(
            messages=[
                {"role": "system", "content": "You are a memory analyst specializing in fact extraction."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            tier="strong"
        )

        data = json.loads(response)

        # Merge instructions from specialized pipeline
        data["instructions"] = instructions

        return data
    
    async def _process_consolidated_item(self, item: Dict[str, Any], source_job: Dict[str, Any]):
        """
        Process a single extracted item - check for conflicts and store.

        Uses specialized instruction handling for ai_instructions quadrant.
        """
        is_instruction = "ai_instructions" in item.get("quadrants", [])

        # Get embedding
        item_vector = await self.llm.get_embedding(item["content"])

        if is_instruction:
            # Use specialized instruction pipeline
            await self._process_instruction(item, item_vector, source_job)
        else:
            # Standard fact processing
            filter_quadrant = item["quadrants"][0] if item.get("quadrants") else None
            existing = self.vector_store.search_memories(
                item_vector,
                limit=3,
                filter_quadrants=[filter_quadrant] if filter_quadrant else None
            )

            if existing:
                await self._resolve_and_merge(item, existing, source_job)
            else:
                await self._store_ltm(item, item_vector, source_job.get("source_uri"))

    async def _process_instruction(
        self,
        item: Dict[str, Any],
        vector: List[float],
        source_job: Dict[str, Any]
    ):
        """
        Process an instruction using specialized instruction store.

        Handles override semantics for conflicting instructions.
        """
        # Check for instructions that might be overridden
        overridden = self.instruction_store.find_overridden_instructions(item, vector)

        if overridden:
            print(f"[Consolidator] Instruction '{item['summary']}' may override {len(overridden)} existing")
            for o in overridden:
                # Mark override relationship in graph
                self.graph_store.add_edge(
                    source_job["memory_id"],
                    o["id"],
                    "OVERRIDES",
                    metadata={
                        "reason": f"New instruction: {item['summary']}",
                        "relationship": o["relationship"]
                    }
                )

        # Store the instruction
        await self.instruction_store.store_instruction(
            item,
            vector,
            source_uri=source_job.get("source_uri")
        )
        print(f"[Consolidator] Stored instruction: {item['summary']}")
    
    async def _resolve_and_merge(self, new_item: Dict[str, Any],
                                  existing_items: List[Any],
                                  source_job: Dict[str, Any]):
        """
        Resolve conflicts between new and existing memories.

        Uses hierarchy-based conflict resolution:
        1. First tries priority-based resolution (constraint > verified > general)
        2. Falls back to semantic analysis for similar-priority items
        3. Records conflicts in graph for tracking
        """
        # Convert new_item to memory format expected by conflict resolver
        new_memory = {
            "summary": new_item["summary"],
            "content": new_item["content"],
            "type": new_item.get("type", "general"),
            "quadrants": new_item.get("quadrants", ["general"]),
            "tags": new_item.get("tags", []),
            "verified": new_item.get("verified", False),
            "explicitly_corrected": new_item.get("explicitly_corrected", False),
            "confidence": new_item.get("confidence", "medium"),
            "importance": new_item.get("importance", 0.5),
            "created_at": datetime.now().isoformat()
        }

        best_match = None
        best_resolution = None
        highest_similarity = 0.0

        # Check each existing item for conflicts
        for existing in existing_items:
            existing_memory = {
                "id": existing.id,
                "summary": existing.payload.get("summary", ""),
                "content": existing.payload.get("content", ""),
                "type": existing.payload.get("type", "general"),
                "quadrants": existing.payload.get("quadrants", ["general"]),
                "tags": existing.payload.get("tags", []),
                "verified": existing.payload.get("verified", False),
                "explicitly_corrected": existing.payload.get("explicitly_corrected", False),
                "confidence": existing.payload.get("confidence", "medium"),
                "importance": existing.payload.get("importance", 0.5),
                "created_at": existing.payload.get("created_at")
            }

            # Use hierarchy-based conflict resolution
            resolution = await self.conflict_resolver.resolve_conflict(
                new_memory,
                existing_memory,
                context=f"Source: {source_job.get('source_uri', 'unknown')}"
            )

            similarity = existing.score if hasattr(existing, 'score') else 0.8

            # Track the best match (highest similarity with clear resolution)
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = existing
                best_resolution = resolution

        if not best_match or not best_resolution:
            # No good match found, store as new
            await self._store_ltm(new_item,
                                  source_uri=source_job.get("source_uri"),
                                  parent_job=source_job)
            return

        # Handle the resolution
        resolution_type = best_resolution["resolution"]
        winner = best_resolution.get("winner")

        if resolution_type == ConflictResolution.REPLACE_WITH_NEW:
            # New memory has higher priority - replace existing
            print(f"[Consolidator] Replacing '{best_match.payload.get('summary')}' with higher priority item")

            # Update the existing entry with new content
            updated_vector = await self.llm.get_embedding(new_item["content"])
            new_payload = {
                "content": new_item["content"],
                "summary": new_item["summary"],
                "quadrants": new_item.get("quadrants", ["general"]),
                "importance": new_item.get("importance", 0.9),
                "type": "consolidated",
                "source_uri": source_job.get("source_uri"),
                "updated_at": datetime.now().isoformat(),
                "consolidated_from": source_job["memory_id"],
                "replaces": best_match.id
            }
            self.vector_store.upsert_memory(best_match.id, updated_vector, new_payload)

            # Record override relationship
            self.conflict_manager.record_override(
                source_job["memory_id"],
                best_match.id,
                reason=best_resolution.get("reason", "Higher priority replacement")
            )

        elif resolution_type == ConflictResolution.KEEP_EXISTING:
            # Existing memory wins - just link as duplicate/reference
            print(f"[Consolidator] Keeping existing (higher priority), linking new as related")

            self.graph_store.add_edge(
                source_job["memory_id"],
                best_match.id,
                "RELATED_TO",
                metadata={
                    "reason": "Lower priority than existing",
                    "resolution": "keep_existing"
                }
            )

        elif resolution_type == ConflictResolution.MERGE:
            # Merge content from both
            print(f"[Consolidator] Merging with existing: {best_match.payload.get('summary')}")

            merged_content = await self._merge_contents(
                new_item["content"],
                best_match.payload.get("content", ""),
                new_item["summary"]
            )

            updated_vector = await self.llm.get_embedding(merged_content)
            new_payload = {
                "content": merged_content,
                "summary": new_item["summary"],
                "quadrants": new_item.get("quadrants", ["general"]),
                "importance": max(new_item.get("importance", 0.5), best_match.payload.get("importance", 0.5)),
                "type": "consolidated",
                "source_uri": source_job.get("source_uri"),
                "updated_at": datetime.now().isoformat(),
                "consolidated_from": source_job["memory_id"]
            }
            self.vector_store.upsert_memory(best_match.id, updated_vector, new_payload)

        elif resolution_type == ConflictResolution.KEEP_BOTH_MARKED:
            # Store new and mark conflict
            print(f"[Consolidator] Storing as conflicting memory")

            new_id = await self._store_ltm(
                new_item,
                source_uri=source_job.get("source_uri"),
                parent_job=source_job
            )

            # Record conflict in graph
            self.conflict_manager.record_conflict(
                new_id,
                best_match.id,
                resolution=ConflictResolution.KEEP_BOTH_MARKED,
                reason=best_resolution.get("reason", "Similar priority, both kept"),
                winner_id=None
            )

        else:  # DEFER_TO_USER or default
            # Store both and mark for manual review
            print(f"[Consolidator] Conflict deferred - storing both for review")

            new_id = await self._store_ltm(
                new_item,
                source_uri=source_job.get("source_uri"),
                parent_job=source_job
            )

            # Mark as needing review
            self.vector_store.client.set_payload(
                collection_name=self.vector_store.collection_name,
                payload={"needs_review": True, "conflict_reason": best_resolution.get("reason", "")},
                points=[new_id]
            )

            self.conflict_manager.record_conflict(
                new_id,
                best_match.id,
                resolution=ConflictResolution.DEFER_TO_USER,
                reason=best_resolution.get("reason", "Requires manual resolution"),
                winner_id=None
            )

    async def _merge_contents(self, new_content: str, existing_content: str, summary: str) -> str:
        """Merge two content pieces using LLM."""
        prompt = f"""
        Merge these two related pieces of information into a coherent single statement.

        NEW INFORMATION:
        {new_content}

        EXISTING INFORMATION:
        {existing_content}

        Create a merged version that:
        - Preserves all unique facts from both
        - Removes redundancy
        - Maintains clarity and conciseness

        Return only the merged text, no explanation.
        """

        response = await self.llm.completion(
            messages=[{"role": "user", "content": prompt}],
            tier="strong"
        )

        return response.strip()
    
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
