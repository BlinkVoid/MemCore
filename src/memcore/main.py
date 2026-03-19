import asyncio
import os
import uuid
import argparse
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

# Project Imports
from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.storage.queue import ConsolidationQueue
from src.memcore.gatekeeper.router import GatekeeperRouter
from src.memcore.memory.tiered import TieredContextManager
from src.memcore.memory.consolidation import MemoryConsolidator
from src.memcore.agent.consolidation_agent import ConsolidationManager
from src.memcore.memory.feedback_optimizer import FeedbackOptimizer
from src.memcore.memory.advanced_search import AdvancedSearch, SearchFilters
from src.memcore.utils.watcher import DocumentWatcher
from src.memcore.utils.reporter import HTMLReporter
from src.memcore.dashboard.server import DashboardRouter
from src.memcore.tasks import TaskManager, ReminderScheduler
from src.memcore.utils.obsidian_ingester import ObsidianIngester

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "dataCrystal")
LOG_FILE = os.path.join(DATA_DIR, "logs", "memcore.log")

# Setup Logging
os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemCore")

load_dotenv()

class MemCoreServer:
    """Unified MemCore Server hosting MCP and Dashboard."""
    
    def __init__(self):
        # 1. Core Services
        self.llm = LLMInterface()
        self.vector_store = VectorStore(
            location=os.path.join(DATA_DIR, "qdrant_storage"),
            dimension=self.llm.get_embedding_dimension()
        )
        self.graph_store = GraphStore(db_path=os.path.join(DATA_DIR, "memcore_graph.db"))
        self.consolidation_queue = ConsolidationQueue(db_path=os.path.join(DATA_DIR, "consolidation_queue.db"))
        
        # 2. Logic Engines
        self.router = GatekeeperRouter(self.llm)
        self.feedback_optimizer = FeedbackOptimizer(self.llm, self.graph_store)
        self.tiered_manager = TieredContextManager(
            self.vector_store, self.graph_store, 
            weight_provider=self.feedback_optimizer.get_current_weights
        )
        self.consolidator = MemoryConsolidator(
            self.llm, self.vector_store, self.graph_store, self.consolidation_queue
        )
        self.consolidation_manager = ConsolidationManager(self.consolidator, self.llm)
        self.task_manager = TaskManager(DATA_DIR, self.vector_store)
        self.reminder_scheduler = ReminderScheduler(self.task_manager, self.llm)
        
        # 3. FastMCP for Tools
        self.mcp = FastMCP("memcore-gatekeeper")
        self._register_mcp_tools()
        
        # 4. Background Tasks
        self.scheduler = AsyncIOScheduler()
        self._setup_scheduler()
        
        # 5. Document Watcher
        watch_dir = os.getenv("OBSIDIAN_VAULT_PATH")
        self.watcher = DocumentWatcher(watch_dir, self.reindex_file) if watch_dir else None

    def _register_mcp_tools(self):
        """Register all tools to the FastMCP instance."""
        
        @self.mcp.tool()
        async def mem_query(query: str, quadrant_hint: Optional[str] = None) -> str:
            """Query the memory system for relevant context."""
            # Use router if no hint provided
            quadrant = quadrant_hint or (await self.router.classify_request(query)).quadrant
            
            # Retrieve tiered context
            query_vector = await self.llm.get_embedding(query)
            context = await self.tiered_manager.get_progressive_context(
                query_vector, quadrants=[quadrant, "ai_instructions"]
            )
            
            return f"Context from {quadrant}:\n\n{context['context_string']}"

        @self.mcp.tool()
        async def mem_save(content: str, summary: str, quadrants: List[str] = ["general"]) -> str:
            """Save a new memory."""
            mem_id = str(uuid.uuid4())
            vector = await self.llm.get_embedding(content)
            payload = {
                "content": content, "summary": summary, "quadrants": quadrants,
                "timestamp": datetime.now().isoformat(), "type": "raw"
            }
            self.vector_store.upsert_memory(mem_id, vector, payload)
            self.graph_store.add_node(mem_id, "memory", {"summary": summary, "type": "raw"})
            
            # Asynchronously trigger the Strand Agent to evaluate the system
            asyncio.create_task(self.consolidation_manager.evaluate_environment())
            
            return f"Stored memory {mem_id}"

        @self.mcp.tool()
        async def add_task(title: str, priority: str = "medium") -> str:
            """Add a task to the system."""
            res = await self.task_manager.add_task(title=title, priority=priority)
            return "Task added" if res["success"] else "Failed"

    def _setup_scheduler(self):
        """Configure background recurring jobs."""
        # Gentle fallback tickler to ensure the agent evaluates occasionally
        # even if no mem_save events occurred recently
        self.scheduler.add_job(self.consolidation_manager.evaluate_environment, 'interval', minutes=30)

    async def reindex_file(self, path: str):
        """Re-index a single file from the watcher."""
        ingester = ObsidianIngester(os.path.dirname(path), self.llm, self.vector_store, self.graph_store)
        await ingester._process_file(path, force_rescan=True)

    async def run(self, host: str = "127.0.0.1", port: int = 8080):
        """Start the unified server."""
        logger.info(f"Starting Unified MemCore Server on http://{host}:{port}")
        
        # Start background services
        self.scheduler.start()
        if self.watcher: self.watcher.start()
        self.reminder_scheduler.start()
        
        # Setup Dashboard
        dash = DashboardRouter(self.vector_store, self.graph_store, self.llm, self.consolidation_queue, DATA_DIR)
        
        # Merge MCP and Dashboard onto one Starlette App
        # FastMCP.streamable_http_app() returns a Starlette app with MCP routes
        app = self.mcp.streamable_http_app()
        dash.attach_routes(app)
        
        # Add Health/Status
        @app.route("/health")
        async def health(request): return JSONResponse({"status": "healthy"})
        
        @app.route("/status")
        async def status(request):
            return JSONResponse({
                "memories": self.vector_store.get_stats().get("total_memories", 0),
                "queue": self.consolidation_queue.get_pending_count()
            })

        @app.route("/api/run-consolidation", methods=["POST"])
        async def run_consolidation(request):
            """Directly run consolidation pipeline, bypassing the Strands agent.

            Useful for batch processing with CLI providers (cli/kimi, cli/claude)
            that don't support the Strands streaming protocol.

            Query params:
                batch_size: Number of jobs to process per batch (default: 5)
                queue_first: If true, queue raw memories before processing (default: true)
                reset_stale: If true, reset stuck 'processing' jobs to 'pending' first (default: false)
            """
            try:
                batch_size = int(request.query_params.get("batch_size", 5))
                queue_first = request.query_params.get("queue_first", "true").lower() == "true"
                reset_stale = request.query_params.get("reset_stale", "false").lower() == "true"

                results = {"queued": 0, "processed": None, "reset": 0}

                if reset_stale:
                    reset_count = self.consolidator.recover_from_crash()
                    results["reset"] = reset_count
                    logger.info(f"Reset {reset_count} stale processing jobs to pending")

                if queue_first:
                    raw = self.vector_store.get_raw_memories(limit=100)
                    if raw:
                        mem_dicts = [{
                            "id": r.id,
                            "content": r.payload.get("content", ""),
                            "summary": r.payload.get("summary", ""),
                            "quadrants": r.payload.get("quadrants", ["general"]),
                            "source_uri": r.payload.get("source_uri"),
                            "importance": r.payload.get("importance", 0.5)
                        } for r in raw]
                        job_ids = await self.consolidator.queue_raw_memories(mem_dicts)
                        results["queued"] = len(job_ids)

                pending = self.consolidation_queue.get_pending_count()
                if pending > 0:
                    proc_results = await self.consolidator.process_queue_with_synthesis(batch_size=batch_size)
                    results["processed"] = proc_results

                results["queue_after"] = self.consolidation_queue.get_stats()
                return JSONResponse({"success": True, **results})
            except Exception as e:
                logger.error(f"Direct consolidation failed: {e}", exc_info=True)
                return JSONResponse({"success": False, "error": str(e)}, status_code=500)

        # Run with Uvicorn
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    
    server = MemCoreServer()
    await server.run(args.host, args.port)

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
