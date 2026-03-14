import asyncio
import logging
from typing import Dict, Any, List

from strands import Agent
from strands.tools import tool
from src.memcore.agent.model_adapter import MemCoreStrandModel
from src.memcore.utils.llm import LLMInterface
from src.memcore.memory.consolidation import MemoryConsolidator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the **MemCore Consolidation Agent**, an autonomous subsystem responsible for curating the agent's long-term memory.
You manage the transition of short-term, raw memories into structured, durable semantic knowledge.

Your job is to periodically check the system state and determine if action is required to avoid backlog and maintain memory quality.

## Rules:
1. Use `check_consolidation_status` to see if there are raw memories that need queueing, or jobs that need processing.
2. If `raw_memories_count` > 0, use `queue_memories_for_consolidation` to move them to the queue.
3. If `pending_jobs` > 0, use `process_consolidation_queue` to advance the LLM pipeline (this synthesizes facts and instructions).
4. Do not perform operations if not needed.
5. If the system is clean (0 raw, 0 pending), simply output a status report stating everything is caught up.
6. When finished working, ALWAYS use `clear_agent_short_term_memory` to purge your own L1 ephemeral context to save tokens on the next invocation.
"""

class ConsolidationManager:
    """Wrapper class coordinating the Strand Agent and MemCore capabilities."""
    
    def __init__(self, consolidator: MemoryConsolidator, llm_interface: LLMInterface):
        self.consolidator = consolidator
        self.llm = llm_interface
        
        # Instantiate adapter using the STRONG tier for complex routing and curation logic
        self.model = MemCoreStrandModel(llm_interface=self.llm, tier="strong")
        
        # Instantiate tools
        self.tools = [
            tool(self.check_consolidation_status),
            tool(self.queue_memories_for_consolidation),
            tool(self.process_consolidation_queue),
            tool(self.clear_agent_short_term_memory)
        ]
        
        # Instantiate Strand Agent
        self.agent = Agent(
            model=self.model,
            system_prompt=SYSTEM_PROMPT,
            tools=self.tools
        )
    
    def check_consolidation_status(self) -> str:
        """Checks the current state of MemCore's memory backlog and queue."""
        print("[StrandAgent] Tool: Checking consolidation status")
        raw_memories = self.consolidator.vector_store.get_raw_memories(limit=100)
        stats = self.consolidator.get_queue_stats()
        return f"Raw Memories waiting to be queued: {len(raw_memories)}\nQueue Stats: {stats}"

    def queue_memories_for_consolidation(self) -> str:
        """Moves raw memories into the consolidation queue."""
        print("[StrandAgent] Tool: Queuing memories")
        raw_memories = self.consolidator.vector_store.get_raw_memories(limit=100)
        if not raw_memories:
            return "No raw memories to queue."
            
        mem_dicts = []
        for r in raw_memories:
            mem_dicts.append({
                "id": r.id,
                "content": r.payload.get("content", ""),
                "summary": r.payload.get("summary", ""),
                "quadrants": r.payload.get("quadrants", ["general"]),
                "source_uri": r.payload.get("source_uri"),
                "importance": r.payload.get("importance", 0.5)
            })
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.consolidator.queue_raw_memories(mem_dicts),
                self._current_loop
            )
            job_ids = future.result()
            return f"Successfully queued {len(job_ids)} memories."
        except Exception as e:
            return f"Error queuing memories: {e}"

    def process_consolidation_queue(self, batch_size: int = 10) -> str:
        """Processes the pending consolidation queue, extracting facts and synthesizing reflections."""
        print(f"[StrandAgent] Tool: Processing queue (batch={batch_size})")
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.consolidator.process_queue_with_synthesis(batch_size=batch_size),
                self._current_loop
            )
            results = future.result()
            return f"Process Queue Results: {results}"
        except Exception as e:
            return f"Error processing queue: {e}"

    def clear_agent_short_term_memory(self) -> str:
        """Clears the agent's conversational context history to save tokens. MUST be called at end of work."""
        print("[StrandAgent] Tool: Clearing L1 Ephemeral Memory")
        self.agent.clear_context()
        return "Agent context cleared successfully."
        
    async def evaluate_environment(self):
        """Called by MemCore transport events to organically trigger curation."""
        logger.info("ConsolidationManager assessing environment...")
        
        # Capture the main event loop to pass back into tools
        self._current_loop = asyncio.get_running_loop()
        
        # Provide the initial prompt to the agent to kick off the curation loops
        prompt = "Assess the current consolidation status and take any necessary actions. Ensure you clear your context when finished."
        
        try:
            # Run the agent synchronously in a thread
            response = await asyncio.to_thread(self.agent, prompt)
            
            logger.info("ConsolidationManager finished evaluation.")
            return str(response)
        except Exception as e:
            logger.error(f"ConsolidationManager evaluate failed: {e}")
            return f"Error: {e}"
