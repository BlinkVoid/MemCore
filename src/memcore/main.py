import asyncio
import os
import uuid
import argparse
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Determine project root for absolute data paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "dataCrystal")

try:
    from strands_sdk.client import StrandsClient
    from strands_sdk.types import AgentConfig
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    StrandsClient = None
    AgentConfig = None
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
import mcp.types as types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.memcore.utils.llm import LLMInterface
from src.memcore.gatekeeper.router import GatekeeperRouter
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.storage.queue import ConsolidationQueue
from src.memcore.memory.tiered import TieredContextManager
from src.memcore.memory.consolidation import MemoryConsolidator
from src.memcore.utils.watcher import DocumentWatcher
from src.memcore.utils.reporter import HTMLReporter

# Import optional dependencies for SSE mode
try:
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import PlainTextResponse
    from starlette.requests import Request
    STARLETTE_AVAILABLE = True
except ImportError:
    STARLETTE_AVAILABLE = False

load_dotenv()

class MemCoreAgent:
    def __init__(self):
        self.llm = LLMInterface()
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Initialize storage with absolute paths
        vector_storage_path = os.path.join(DATA_DIR, "qdrant_storage")
        graph_db_path = os.path.join(DATA_DIR, "memcore_graph.db")
        
        self.vector_store = VectorStore(location=vector_storage_path, dimension=self.llm.get_embedding_dimension())
        self.graph_store = GraphStore(db_path=graph_db_path)
        self.router = GatekeeperRouter(self.llm)
        self.tiered_manager = TieredContextManager(self.vector_store, self.graph_store)
        # Initialize consolidation queue with stateful persistence
        queue_db_path = os.path.join(DATA_DIR, "consolidation_queue.db")
        self.consolidation_queue = ConsolidationQueue(db_path=queue_db_path)
        
        self.consolidator = MemoryConsolidator(
            self.llm, self.vector_store, self.graph_store, self.consolidation_queue
        )
        
        # Strand SDK setup (Optional platform connection)
        strands_key = os.getenv("STRANDS_API_KEY")
        if strands_key and STRANDS_AVAILABLE:
            self.strand_client = StrandsClient(api_key=strands_key)
        else:
            self.strand_client = None
            if not STRANDS_AVAILABLE:
                print("Notice: strands_sdk not available. Running in local-only mode.")
            else:
                print("Notice: STRANDS_API_KEY not found. Running in local-only mode.")
        
        # Scheduler for consolidation and reporting
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.consolidate_memories, 'interval', hours=8)
        self.scheduler.add_job(self.process_consolidation_queue, 'interval', minutes=30)
        self.scheduler.add_job(self.generate_status_report, 'interval', hours=1)
        
        # Document Watcher
        watch_dir = os.getenv("OBSIDIAN_VAULT_PATH")
        if watch_dir:
            self.watcher = DocumentWatcher(watch_dir, self.reindex_file)
        else:
            self.watcher = None
        
        # HTML Reporter
        self.reporter = HTMLReporter(output_dir=os.path.join(DATA_DIR, "reports"))
        
        # MCP Server setup
        self.mcp_server = Server("memcore-gatekeeper")
        self._setup_mcp_tools()

    async def reindex_file(self, file_path: str):
        """Processes a file into memories, replacing old ones from the same source."""
        print(f"Re-indexing file: {file_path}")
        source_uri = f"file://{file_path}"
        
        # 1. Prune old memories
        self.vector_store.delete_memories_by_source(source_uri)
        self.graph_store.delete_nodes_by_source(source_uri)
        
        # 2. Read new content
        with open(file_path, "r") as f:
            content = f.read()
        
        # 3. Process into quadrants
        prompt = f"""
        Extract key facts and instructions from this document.
        Document Source: {file_path}
        Content:
        {content[:4000]} # Truncate if too large
        
        Return JSON: {{"entries": [ {{"summary": "...", "content": "...", "quadrants": [...]}} ]}}
        """
        response = await self.llm.completion(
            messages=[{"role": "system", "content": "You are a memory ingestion agent."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            tier="strong"
        )
        data = json.loads(response)
        
        # 4. Save as raw memories (to be consolidated later)
        for entry in data.get("entries", []):
            await self.handle_mem_save({
                "content": entry["content"],
                "summary": entry["summary"],
                "quadrants": entry["quadrants"],
                "metadata": {"source_uri": source_uri}
            })
        print(f"Re-indexed {len(data.get('entries', []))} entries from {file_path}")

    async def consolidate_memories(self):
        """
        Background task for memory consolidation.
        Queues raw memories for processing; actual processing happens via process_consolidation_queue.
        """
        print(f"[{datetime.now()}] Checking for memories to consolidate...")
        
        # 1. Fetch raw memories
        raw_results = self.vector_store.get_raw_memories(limit=50)
        if not raw_results:
            print("No new raw memories found. Skipping consolidation.")
            self.graph_store.set_metadata("last_consolidation", datetime.now().isoformat())
            return

        print(f"Queueing {len(raw_results)} memories for consolidation...")
        
        # 2. Convert to format consolidator expects
        memories_to_process = [
            {
                "id": r.id,
                "content": r.payload["content"],
                "summary": r.payload["summary"],
                "quadrants": r.payload["quadrants"],
                "source_uri": r.payload.get("source_uri")
            }
            for r in raw_results
        ]

        # 3. Queue for background processing (survives restarts)
        result = await self.consolidator.consolidate(memories_to_process, use_queue=True)
        print(f"Consolidation queue status: {result}")

        # 4. Update metadata
        self.graph_store.set_metadata("last_consolidation", datetime.now().isoformat())
        
    async def process_consolidation_queue(self):
        """
        Process pending jobs from the consolidation queue.
        Runs every 30 minutes to work through queued memories.
        """
        pending = self.consolidation_queue.get_pending_count()
        if pending == 0:
            return
            
        print(f"[{datetime.now()}] Processing consolidation queue ({pending} pending jobs)...")
        
        try:
            result = await self.consolidator.process_queue(batch_size=10)
            print(f"Queue processing complete: {result['completed']} completed, {result['failed']} failed")
        except Exception as e:
            print(f"Error processing consolidation queue: {e}")

    async def generate_status_report(self):
        """Generate HTML status report with memory statistics."""
        print(f"[{datetime.now()}] Generating status report...")
        
        try:
            # Get stats from storage
            vector_stats = self.vector_store.get_stats()
            graph_stats = self.graph_store.get_stats()
            queue_stats = self.consolidation_queue.get_stats()
            
            # Generate and save report
            report_path = self.reporter.save_report(vector_stats, graph_stats, queue_stats)
            print(f"Status report generated: {report_path}")
        except Exception as e:
            print(f"Error generating status report: {e}")

    def _setup_mcp_tools(self):
        @self.mcp_server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="mem_query",
                    description="Retrieve context and memory based on a query.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "quadrant_hint": {"type": "string", "enum": ["coding", "personal", "research", "ai_instructions"]},
                            "context_limit": {"type": "integer", "description": "Max tokens to return (default: 4000)"},
                        },
                        "required": ["query"],
                    },
                ),
                types.Tool(
                    name="mem_save",
                    description="Store a new memory (short-term or long-term).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "summary": {"type": "string"},
                            "quadrants": {"type": "array", "items": {"type": "string"}},
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "importance_override": {"type": "number"},
                                    "source_uri": {"type": "string"}
                                }
                            }
                        },
                        "required": ["content", "summary"],
                    },
                ),
                types.Tool(
                    name="fetch_detail",
                    description="Fetch L2 full details for a specific memory ID.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string"},
                        },
                        "required": ["memory_id"],
                    },
                ),
                types.Tool(
                    name="submit_feedback",
                    description="Submit feedback on a memory retrieval to improve accuracy.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "request_id": {"type": "string"},
                            "memory_id": {"type": "string"},
                            "rating": {"type": "integer", "description": "1 for good, -1 for bad"},
                            "reason": {"type": "string"}
                        },
                        "required": ["request_id", "memory_id", "rating"]
                    }
                ),
                types.Tool(
                    name="fetch_source",
                    description="Retrieve the original source document content (e.g., Obsidian markdown).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string"}
                        },
                        "required": ["memory_id"]
                    }
                ),
                types.Tool(
                    name="mem_stats",
                    description="Get memory statistics and system status. Returns current memory counts and system health.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]

        @self.mcp_server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            if name == "mem_query":
                return await self.handle_mem_query(arguments["query"], arguments.get("quadrant_hint"))
            elif name == "mem_save":
                return await self.handle_mem_save(arguments)
            elif name == "fetch_detail":
                return await self.handle_fetch_detail(arguments["memory_id"])
            elif name == "submit_feedback":
                return await self.handle_feedback(arguments)
            elif name == "fetch_source":
                return await self.handle_fetch_source(arguments["memory_id"])
            elif name == "mem_stats":
                return await self.handle_stats()
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    async def handle_fetch_source(self, memory_id: str) -> list[types.TextContent]:
        memory_data = self.vector_store.get_memory_by_id(memory_id)
        if not memory_data or not memory_data[0].payload.get("source_uri"):
            return [types.TextContent(type="text", text="No source document found for this memory.")]
        
        source_uri = memory_data[0].payload["source_uri"]
        if source_uri.startswith("file://"):
            path = source_uri.replace("file://", "")
            if os.path.exists(path):
                with open(path, "r") as f:
                    content = f.read()
                return [types.TextContent(type="text", text=f"--- Source: {path} ---\n\n{content}")]
        
        return [types.TextContent(type="text", text=f"Source URI {source_uri} not supported or not found.")]

    async def handle_mem_query(self, query: str, quadrant_hint: Optional[str] = None) -> list[types.TextContent]:
        # 1. Routing (using FAST model via router)
        if not quadrant_hint:
            classification = await self.router.classify_request(query)
            quadrant = classification.quadrant
        else:
            quadrant = quadrant_hint

        # 2. Vector Search (L0) - Include both target quadrant and instructions
        query_vector = await self.llm.get_embedding(query)
        search_quadrants = [quadrant]
        if quadrant != "ai_instructions":
            search_quadrants.append("ai_instructions")
            
        l0_results = await self.tiered_manager.get_l0_context(query_vector, quadrants=search_quadrants)

        # 3. Create request node early (for dynamic scoring context)
        request_id = str(uuid.uuid4())

        # 4. Scoring with dynamic relevancy (uses graph weights from previous feedback)
        scored_memories = self.tiered_manager.score_memories(l0_results, request_id=request_id)

        # 5. Formatted Response (Separating Instructions and Knowledge)
        instructions = [m for m in scored_memories if "ai_instructions" in m["quadrants"]]
        knowledge = [m for m in scored_memories if "ai_instructions" not in m["quadrants"]]

        response_text = f"Quadrant: {quadrant}\n\n"

        if instructions:
            response_text += "--- Relevant Instructions (SOPs) ---\n"
            for m in instructions[:3]:
                boost_info = f" [boost: {m.get('dynamic_boost', 1.0):.2f}]" if m.get('dynamic_boost', 1.0) != 1.0 else ""
                response_text += f"- [{m['id']}] {m['summary']} (Score: {m['final_score']:.2f}){boost_info}\n"
                self.vector_store.update_memory_access(m['id']) # Update recency
            response_text += "\n"

        response_text += "--- Knowledge & Context ---\n"
        for i, mem in enumerate(knowledge[:5]):
            boost_info = f" [boost: {mem.get('dynamic_boost', 1.0):.2f}]" if mem.get('dynamic_boost', 1.0) != 1.0 else ""
            response_text += f"{i+1}. [{mem['id']}] {mem['summary']} (Score: {mem['final_score']:.2f}){boost_info}\n"
            self.vector_store.update_memory_access(mem['id']) # Update recency

        # 6. Graph Mapping (Record the request and link to memories that fulfilled it)
        self.graph_store.add_request_node(request_id, query, response_text)
        for mem in scored_memories[:3]:
            self.graph_store.link_request_to_memory(request_id, mem["id"])

        return [types.TextContent(type="text", text=response_text)]

    async def handle_mem_save(self, args: dict) -> list[types.TextContent]:
        memory_id = str(uuid.uuid4())
        content = args["content"]
        summary = args["summary"]
        quadrants = args.get("quadrants", ["general"])
        metadata = args.get("metadata", {})
        
        vector = await self.llm.get_embedding(content)
        payload = {
            "content": content,
            "summary": summary,
            "quadrants": quadrants,
            "timestamp": datetime.now().isoformat(),
            "importance": metadata.get("importance_override", 0.5),
            "source_uri": metadata.get("source_uri"),
            "type": "raw" # Mark for consolidation
        }
        
        self.vector_store.upsert_memory(memory_id, vector, payload)
        self.graph_store.add_node(
            memory_id, 
            "memory", 
            {"summary": summary, "type": "raw"},
            source_uri=metadata.get("source_uri")
        )
        
        return [types.TextContent(type="text", text=f"Memory stored successfully. ID: {memory_id}")]

    async def handle_feedback(self, args: dict) -> list[types.TextContent]:
        request_id = args["request_id"]
        memory_id = args["memory_id"]
        rating = args["rating"]
        reason = args.get("reason", "No reason provided")

        # Update graph weight
        self.graph_store.update_edge_weight(request_id, memory_id, "FULFILLED_BY", float(rating))

        # If negative rating, perform Root Cause Analysis (using STRONG model)
        if rating < 0:
            memory_data = self.vector_store.get_memory_by_id(memory_id)
            request_data = self.graph_store.get_node_metadata(request_id)
            
            prompt = f"""
            Perform Root Cause Analysis on a memory retrieval failure.
            
            User Query: {request_data.get('query') if request_data else 'Unknown'}
            Retrieved Memory: {memory_data[0].payload['summary'] if memory_data else 'Unknown'}
            User Feedback: {reason}
            
            Identify if the issue is:
            - IRRELEVANCE: Semantic search returned unrelated info.
            - OBSOLESCENCE: Info is outdated.
            - NOISE: Too much detail, not enough gist.
            
            Suggest an adjustment to the Importance or Relevance weights.
            """
            
            rca_response = await self.llm.completion(
                messages=[{"role": "user", "content": prompt}],
                tier="strong"
            )
            return [types.TextContent(type="text", text=f"Feedback recorded. RCA Result: {rca_response}")]

        return [types.TextContent(type="text", text="Feedback recorded. Edge weights updated.")]

    async def handle_stats(self) -> list[types.TextContent]:
        """Return memory statistics."""
        vector_stats = self.vector_store.get_stats()
        graph_stats = self.graph_store.get_stats()
        queue_stats = self.consolidation_queue.get_stats()
        
        report_path = os.path.join(DATA_DIR, "reports", "latest.html")
        
        response_text = f"""=== MemCore Status Report ===

Vector Database:
  Total Memories: {vector_stats.get('total_memories', 0)}
  Dimension: {vector_stats.get('dimension', 'N/A')}
  Collection: {vector_stats.get('collection_name', 'N/A')}
  
  By Type:
"""
        for mem_type, count in sorted(vector_stats.get('by_type', {}).items(), key=lambda x: x[1], reverse=True):
            response_text += f"    - {mem_type}: {count}\n"
        
        response_text += f"""
  By Quadrant:
"""
        for quad, count in sorted(vector_stats.get('by_quadrant', {}).items(), key=lambda x: x[1], reverse=True):
            response_text += f"    - {quad}: {count}\n"
        
        response_text += f"""
Graph Database:
  Total Nodes: {graph_stats.get('total_nodes', 0)}
  Total Edges: {graph_stats.get('total_edges', 0)}
  
  Nodes by Type:
"""
        for node_type, count in sorted(graph_stats.get('nodes_by_type', {}).items(), key=lambda x: x[1], reverse=True):
            response_text += f"    - {node_type}: {count}\n"
        
        response_text += f"""
Consolidation Queue:
  Pending: {queue_stats.get('pending', 0)}
  Processing: {queue_stats.get('processing', 0)}
  Retrying: {queue_stats.get('retrying', 0)}
  Completed (total): {queue_stats.get('completed', 0)}
  Failed (total): {queue_stats.get('failed', 0)}
  
System:
  Last Consolidation: {graph_stats.get('last_consolidation', 'Never')}
  HTML Report: {report_path}
"""
        return [types.TextContent(type="text", text=response_text)]

    async def run_stdio(self):
        """Run in stdio mode (for client-spawned processes)."""
        async with stdio_server() as (read_stream, write_stream):
            await self.mcp_server.run(
                read_stream,
                write_stream,
                self.mcp_server.create_initialization_options()
            )
    
    async def run_sse(self, host: str = "127.0.0.1", port: int = 8080):
        """Run in SSE mode (standalone service)."""
        if not STARLETTE_AVAILABLE:
            print("Error: SSE mode requires starlette. Install with: uv add starlette uvicorn")
            return
        
        from uvicorn import Config, Server as UvicornServer
        
        sse_transport = SseServerTransport("/messages")
        
        async def handle_sse(request):
            """Handle SSE connections."""
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                await self.mcp_server.run(
                    read_stream,
                    write_stream,
                    self.mcp_server.create_initialization_options()
                )
        
        async def handle_messages(request):
            """Handle POST messages from client."""
            await sse_transport.handle_post_message(
                request.scope, request.receive, request._send
            )
            return PlainTextResponse("OK")
        
        async def handle_report(request):
            """Serve the HTML status report."""
            report_path = os.path.join(DATA_DIR, "reports", "latest.html")
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    content = f.read()
                from starlette.responses import HTMLResponse
                return HTMLResponse(content)
            else:
                return PlainTextResponse("Report not generated yet. Please wait for the hourly update.", status_code=503)
        
        routes = [
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/health", endpoint=lambda _: PlainTextResponse("OK"), methods=["GET"]),
            Route("/status", endpoint=handle_report, methods=["GET"]),
        ]
        
        app = Starlette(routes=routes)
        config = Config(app, host=host, port=port, log_level="info")
        server = UvicornServer(config)
        
        print(f"MemCore SSE server running on http://{host}:{port}")
        print(f"  - SSE endpoint: http://{host}:{port}/sse")
        print(f"  - Message endpoint: http://{host}:{port}/messages")
        print(f"  - Health check: http://{host}:{port}/health")
        print(f"  - Status report: http://{host}:{port}/status")
        
        await server.serve()
    
    async def run(self, mode: str = "stdio", host: str = "127.0.0.1", port: int = 8080):
        # 1. Crash recovery: Reset any 'processing' jobs back to 'pending'
        recovered = self.consolidator.recover_from_crash()
        if recovered > 0:
            print(f"[Recovery] Reset {recovered} jobs from 'processing' to 'pending' (crash recovery)")
        
        # 2. Start scheduler
        self.scheduler.start()
        
        # 3. Generate initial status report
        asyncio.create_task(self.generate_status_report())
        
        # 4. Start watcher
        if self.watcher:
            self.watcher.start()
        
        # 5. Process any pending queue items immediately
        pending = self.consolidation_queue.get_pending_count()
        if pending > 0:
            print(f"[Startup] {pending} consolidation jobs pending from previous session")
            asyncio.create_task(self.process_consolidation_queue())
        
        # 6. Check if we need immediate consolidation
        last_con = self.graph_store.get_metadata("last_consolidation")
        if last_con:
            last_dt = datetime.fromisoformat(last_con)
            if (datetime.now() - last_dt).total_seconds() > 8 * 3600:
                print("Last consolidation was > 8h ago. Triggering now...")
                asyncio.create_task(self.consolidate_memories())
        else:
            # First run
            asyncio.create_task(self.consolidate_memories())

        # 5. Start MCP loop in chosen mode
        if mode == "stdio":
            await self.run_stdio()
        elif mode == "sse":
            await self.run_sse(host, port)
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'stdio' or 'sse'.")

def main():
    parser = argparse.ArgumentParser(description="MemCore - Agentic Memory Management System")
    parser.add_argument(
        "--mode", 
        choices=["stdio", "sse"], 
        default="stdio",
        help="Transport mode: stdio (client-spawned) or sse (standalone service)"
    )
    parser.add_argument(
        "--host", 
        default="127.0.0.1",
        help="Host to bind to in SSE mode (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8080,
        help="Port to bind to in SSE mode (default: 8080)"
    )
    
    args = parser.parse_args()
    
    agent = MemCoreAgent()
    asyncio.run(agent.run(mode=args.mode, host=args.host, port=args.port))

if __name__ == "__main__":
    main()
