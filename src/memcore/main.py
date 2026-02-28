import asyncio
import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from strands_sdk.client import StrandsClient
from strands_sdk.types import AgentConfig
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.memcore.utils.llm import LLMInterface
from src.memcore.gatekeeper.router import GatekeeperRouter
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.memory.tiered import TieredContextManager
from src.memcore.memory.consolidation import MemoryConsolidator
from src.memcore.utils.watcher import DocumentWatcher

load_dotenv()

class MemCoreAgent:
    def __init__(self):
        self.llm = LLMInterface()
        self.vector_store = VectorStore(dimension=self.llm.get_embedding_dimension())
        self.graph_store = GraphStore()
        self.router = GatekeeperRouter(self.llm)
        self.tiered_manager = TieredContextManager(self.vector_store)
        self.consolidator = MemoryConsolidator(self.llm, self.vector_store, self.graph_store)
        
        # Strand SDK setup (Optional platform connection)
        strands_key = os.getenv("STRANDS_API_KEY")
        if strands_key:
            self.strand_client = StrandsClient(api_key=strands_key)
        else:
            self.strand_client = None
            print("Notice: STRANDS_API_KEY not found. Running in local-only mode.")
        
        # Scheduler for consolidation
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.consolidate_memories, 'interval', hours=8)
        
        # Document Watcher
        watch_dir = os.getenv("OBSIDIAN_VAULT_PATH")
        if watch_dir:
            self.watcher = DocumentWatcher(watch_dir, self.reindex_file)
        else:
            self.watcher = None
        
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
        """Background task for memory consolidation."""
        print(f"[{datetime.now()}] Checking for memories to consolidate...")
        
        # 1. Fetch raw memories
        raw_results = self.vector_store.get_raw_memories(limit=50)
        if not raw_results:
            print("No new raw memories found. Skipping consolidation.")
            self.graph_store.set_metadata("last_consolidation", datetime.now().isoformat())
            return

        print(f"Consolidating {len(raw_results)} memories...")
        
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

        # 3. Run multi-stage consolidation
        await self.consolidator.consolidate(memories_to_process)

        # 4. Mark processed memories as 'archived_raw'
        for r in raw_results:
            self.vector_store.client.set_payload(
                collection_name=self.vector_store.collection_name,
                payload={"type": "archived_raw"},
                points=[r.id]
            )

        # 5. Update metadata
        self.graph_store.set_metadata("last_consolidation", datetime.now().isoformat())
        print("Consolidation complete.")

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
        
        # 3. Scoring
        scored_memories = self.tiered_manager.score_memories(l0_results)
        
        # 4. Formatted Response (Separating Instructions and Knowledge)
        instructions = [m for m in scored_memories if "ai_instructions" in m["quadrants"]]
        knowledge = [m for m in scored_memories if "ai_instructions" not in m["quadrants"]]

        response_text = f"Quadrant: {quadrant}\n\n"
        
        if instructions:
            response_text += "--- Relevant Instructions (SOPs) ---\n"
            for m in instructions[:3]:
                response_text += f"- [{m['id']}] {m['summary']} (Score: {m['final_score']:.2f})\n"
                self.vector_store.update_memory_access(m['id']) # Update recency
            response_text += "\n"

        response_text += "--- Knowledge & Context ---\n"
        for i, mem in enumerate(knowledge[:5]):
            response_text += f"{i+1}. [{mem['id']}] {mem['summary']} (Score: {mem['final_score']:.2f})\n"
            self.vector_store.update_memory_access(mem['id']) # Update recency
        
        # 5. Graph Mapping (Record the request and the actual served answer)
        request_id = str(uuid.uuid4())
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

    async def run(self):
        # 1. Start scheduler
        self.scheduler.start()
        
        # 2. Start watcher
        if self.watcher:
            self.watcher.start()
        
        # 3. Check if we need immediate consolidation
        last_con = self.graph_store.get_metadata("last_consolidation")
        if last_con:
            last_dt = datetime.fromisoformat(last_con)
            if (datetime.now() - last_dt).total_seconds() > 8 * 3600:
                print("Last consolidation was > 8h ago. Triggering now...")
                asyncio.create_task(self.consolidate_memories())
        else:
            # First run
            asyncio.create_task(self.consolidate_memories())

        # 3. Start MCP loop
        async with stdio_server() as (read_stream, write_stream):
            await self.mcp_server.run(
                read_stream,
                write_stream,
                self.mcp_server.create_initialization_options()
            )

if __name__ == "__main__":
    agent = MemCoreAgent()
    asyncio.run(agent.run())
