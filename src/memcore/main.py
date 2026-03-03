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
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.memcore.utils.llm import LLMInterface
from src.memcore.gatekeeper.router import GatekeeperRouter
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.storage.queue import ConsolidationQueue
from src.memcore.memory.tiered import TieredContextManager
from src.memcore.memory.consolidation import MemoryConsolidator
from src.memcore.memory.feedback_optimizer import FeedbackOptimizer
from src.memcore.memory.advanced_search import AdvancedSearch, SearchFilters
from src.memcore.utils.watcher import DocumentWatcher
from src.memcore.utils.reporter import HTMLReporter
from src.memcore.utils.import_export import MemoryExporter, MemoryImporter
from src.memcore.utils.backup import MemoryBackupManager
from src.memcore.utils.garbage_collection import MemoryGarbageCollector
from src.memcore.utils.analytics import MemoryAnalytics
from src.memcore.utils.templates import MemoryTemplateManager
from src.memcore.utils.sync import MultiDeviceSync

# Skills
from src.memcore.skills import (
    FeedbackSkill,
    VaultSyncSkill,
    ConsolidateExportSkill,
    RecategorizeSkill,
    IngestConsolidatedSkill,
)

# Task Management
from src.memcore.tasks import TaskManager, ReminderScheduler

# Optional dashboard import
try:
    from src.memcore.dashboard.server import DashboardServer
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    DashboardServer = None

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

        # Initialize feedback optimizer for Phase 4
        self.feedback_optimizer = FeedbackOptimizer(self.llm, self.graph_store)

        # Tiered manager with dynamic weight support
        self.tiered_manager = TieredContextManager(
            self.vector_store,
            self.graph_store,
            weight_provider=self.feedback_optimizer.get_current_weights
        )

        # Initialize consolidation queue with stateful persistence
        queue_db_path = os.path.join(DATA_DIR, "consolidation_queue.db")
        self.consolidation_queue = ConsolidationQueue(db_path=queue_db_path)

        self.consolidator = MemoryConsolidator(
            self.llm, self.vector_store, self.graph_store, self.consolidation_queue
        )

        # Import/Export tools
        self.exporter = MemoryExporter(self.vector_store, self.graph_store)
        self.importer = MemoryImporter(self.llm, self.vector_store, self.graph_store)

        # Advanced search
        self.advanced_search = AdvancedSearch(self.vector_store, self.llm)

        # Backup manager
        self.backup_manager = MemoryBackupManager(DATA_DIR)

        # Garbage collector
        self.garbage_collector = MemoryGarbageCollector(
            self.vector_store,
            self.graph_store,
            self.consolidation_queue
        )

        # Analytics
        self.analytics = MemoryAnalytics(self.vector_store, self.graph_store)

        # Template manager
        self.template_manager = MemoryTemplateManager()

        # Multi-device sync
        self.sync_manager = MultiDeviceSync(DATA_DIR)

        # Skills (user-facing slash commands)
        self.feedback_skill = FeedbackSkill(self.feedback_optimizer)
        self.vault_sync_skill = VaultSyncSkill(
            getattr(self, 'document_watcher', None),
            self.vector_store,
            self.llm
        )
        self.consolidate_export_skill = ConsolidateExportSkill(
            self.vector_store,
            self.graph_store,
            self.llm,
            DATA_DIR
        )
        self.recategorize_skill = RecategorizeSkill(
            self.vector_store,
            self.graph_store
        )
        self.ingest_consolidated_skill = IngestConsolidatedSkill(
            self.vector_store,
            self.graph_store,
            self.llm,
            DATA_DIR
        )

        # Task Management
        self.task_manager = TaskManager(DATA_DIR, self.vector_store)
        self.reminder_scheduler = ReminderScheduler(self.task_manager, self.llm)

        # Dashboard server (initialized in run())
        self.dashboard_server = None
        self.dashboard_port = 8081

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
        
        # MCP Server setup (FastMCP)
        self.mcp_server = FastMCP("memcore-gatekeeper")
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
            result = await self.consolidator.process_queue_with_synthesis(batch_size=10)
            reflections = result.get('reflections_generated', 0)
            print(f"Queue processing complete: {result['completed']} completed, {result['failed']} failed, {reflections} reflections generated")
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
        """Setup FastMCP tools using decorator-based API."""

        @self.mcp_server.tool()
        async def mem_query(
            query: str,
            quadrant_hint: Optional[str] = None,
            context_limit: Optional[int] = None
        ) -> str:
            """Retrieve context and memory based on a query."""
            result = await self.handle_mem_query(query, quadrant_hint, context_limit)
            return result[0].text if result else "No results"

        @self.mcp_server.tool()
        async def mem_save(
            content: str,
            summary: str,
            quadrants: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> str:
            """Store a new memory (short-term or long-term)."""
            args = {
                "content": content,
                "summary": summary,
                "quadrants": quadrants or ["general"],
                "metadata": metadata or {}
            }
            result = await self.handle_mem_save(args)
            return result[0].text if result else "Save failed"

        @self.mcp_server.tool()
        async def fetch_detail(memory_id: str) -> str:
            """Fetch L2 full details for a specific memory ID."""
            result = await self.handle_fetch_detail(memory_id)
            return result[0].text if result else "Not found"

        @self.mcp_server.tool()
        async def fetch_source(memory_id: str) -> str:
            """Retrieve the original source document content (e.g., Obsidian markdown)."""
            result = await self.handle_fetch_source(memory_id)
            return result[0].text if result else "Not found"

        @self.mcp_server.tool()
        async def mem_stats() -> str:
            """Get memory statistics and system status."""
            result = await self.handle_stats()
            return result[0].text if result else "Stats unavailable"

        @self.mcp_server.tool()
        async def fetch_reflections(
            pattern_type: str = "all",
            min_confidence: str = "medium"
        ) -> str:
            """Retrieve synthesized reflections and patterns detected across memories."""
            result = await self.handle_fetch_reflections(pattern_type, min_confidence)
            return result[0].text if result else "No reflections found"

        @self.mcp_server.tool()
        async def view_conflicts(status: str = "all") -> str:
            """View conflicting memories that require resolution."""
            result = await self.handle_view_conflicts(status)
            return result[0].text if result else "No conflicts found"

        @self.mcp_server.tool()
        async def optimization_report(window_days: int = 7) -> str:
            """View feedback-driven optimization statistics."""
            result = await self.handle_optimization_report(window_days)
            return result[0].text if result else "Report unavailable"

        # === Task Management Tools ===
        @self.mcp_server.tool()
        async def add_task(
            title: str,
            description: str = "",
            priority: str = "medium",
            due_date: Optional[str] = None,
            tags: Optional[List[str]] = None,
            estimated_minutes: Optional[int] = None,
            context: str = ""
        ) -> str:
            """Add a new task/todo with priority. Use due_date in ISO format (YYYY-MM-DD)."""
            result = await self.handle_add_task(
                title, description, priority, due_date, tags, estimated_minutes, context
            )
            return result[0].text if result else "Failed to add task"

        @self.mcp_server.tool()
        async def list_tasks(
            status: str = "pending",
            priority: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """List your tasks. Filter by status (pending/in_progress/completed) and priority."""
            result = await self.handle_list_tasks(status, priority, limit)
            return result[0].text if result else "Failed to list tasks"

        @self.mcp_server.tool()
        async def complete_task(task_id: str, notes: str = "") -> str:
            """Mark a task as completed."""
            result = await self.handle_complete_task(task_id, notes)
            return result[0].text if result else "Failed to complete task"

        @self.mcp_server.tool()
        async def update_task(
            task_id: str,
            priority: Optional[str] = None,
            due_date: Optional[str] = None,
            status: Optional[str] = None
        ) -> str:
            """Update task priority, due date, or status."""
            result = await self.handle_update_task(task_id, priority, due_date, status)
            return result[0].text if result else "Failed to update task"

        @self.mcp_server.tool()
        async def task_stats() -> str:
            """Get task statistics and overview."""
            result = await self.handle_task_stats()
            return result[0].text if result else "Stats unavailable"

        @self.mcp_server.tool()
        async def export_memories(
            output_path: str,
            format: str = "json",
            filter_quadrants: Optional[List[str]] = None
        ) -> str:
            """Export memories to JSON, Markdown, or CSV format."""
            result = await self.handle_export_memories(output_path, format, filter_quadrants)
            return result[0].text if result else "Export failed"

        @self.mcp_server.tool()
        async def import_memories(
            input_path: str,
            format: str = "json",
            skip_existing: bool = True
        ) -> str:
            """Import memories from JSON, Obsidian vault, or CSV."""
            result = await self.handle_import_memories(input_path, format, skip_existing)
            return result[0].text if result else "Import failed"

        @self.mcp_server.tool()
        async def search_memories(
            query: str = "",
            memory_types: Optional[List[str]] = None,
            quadrants: Optional[List[str]] = None,
            min_confidence: Optional[str] = None,
            min_importance: Optional[float] = None,
            max_importance: Optional[float] = None,
            created_after: Optional[str] = None,
            created_before: Optional[str] = None,
            include_tags: Optional[List[str]] = None,
            exclude_tags: Optional[List[str]] = None,
            content_contains: Optional[str] = None,
            limit: int = 20,
            offset: int = 0
        ) -> str:
            """Advanced search with filters for memories."""
            result = await self.handle_search_memories(
                query, memory_types, quadrants, min_confidence,
                min_importance, max_importance, created_after, created_before,
                include_tags, exclude_tags, content_contains, limit, offset
            )
            return result[0].text if result else "Search failed"

        @self.mcp_server.tool()
        async def create_backup(
            description: str = "",
            include_vectors: bool = True,
            include_graph: bool = True,
            include_queue: bool = True
        ) -> str:
            """Create a full backup of all memory data."""
            result = await self.handle_create_backup(description, include_vectors, include_graph, include_queue)
            return result[0].text if result else "Backup failed"

        @self.mcp_server.tool()
        async def restore_backup(backup_id: str, force: bool = False) -> str:
            """Restore memory data from a backup. Use force=True to overwrite existing data."""
            result = await self.handle_restore_backup(backup_id, force)
            return result[0].text if result else "Restore failed"

        @self.mcp_server.tool()
        async def list_backups() -> str:
            """List all available backups."""
            result = await self.handle_list_backups()
            return result[0].text if result else "Failed to list backups"

        @self.mcp_server.tool()
        async def delete_backup(backup_id: str) -> str:
            """Delete a specific backup."""
            result = await self.handle_delete_backup(backup_id)
            return result[0].text if result else "Delete failed"

        @self.mcp_server.tool()
        async def run_maintenance(
            dry_run: bool = True,
            stale_days: int = 365,
            remove_duplicates: bool = True
        ) -> str:
            """Run garbage collection to clean up orphaned and stale memories. Set dry_run=False to actually remove."""
            result = await self.handle_run_maintenance(dry_run, stale_days, remove_duplicates)
            return result[0].text if result else "Maintenance failed"

        @self.mcp_server.tool()
        async def storage_stats() -> str:
            """Get storage statistics and health metrics."""
            result = await self.handle_storage_stats()
            return result[0].text if result else "Stats unavailable"

        @self.mcp_server.tool()
        async def analytics_report() -> str:
            """Get comprehensive analytics report on memory usage and patterns."""
            result = await self.handle_analytics_report()
            return result[0].text if result else "Analytics unavailable"

        @self.mcp_server.tool()
        async def list_templates() -> str:
            """List available memory templates for structured capture."""
            result = await self.handle_list_templates()
            return result[0].text if result else "Templates unavailable"

        @self.mcp_server.tool()
        async def save_with_template(
            template_id: str,
            content: str,
            summary: str = "",
            custom_tags: Optional[List[str]] = None
        ) -> str:
            """Save a memory using a structured template."""
            result = await self.handle_save_with_template(template_id, content, summary, custom_tags)
            return result[0].text if result else "Save failed"

        @self.mcp_server.tool()
        async def suggest_template(content: str) -> str:
            """Get template suggestions based on content."""
            result = await self.handle_suggest_template(content)
            return result[0].text if result else "Suggestion failed"

        @self.mcp_server.tool()
        async def sync_status() -> str:
            """Check multi-device sync status and configuration."""
            result = await self.handle_sync_status()
            return result[0].text if result else "Sync status unavailable"

        @self.mcp_server.tool()
        async def sync_push(include_vectors: bool = True) -> str:
            """Push local memories to sync target for multi-device access."""
            result = await self.handle_sync_push(include_vectors)
            return result[0].text if result else "Sync push failed"

        @self.mcp_server.tool()
        async def sync_pull(conflict_resolution: str = "timestamp") -> str:
            """Pull memories from sync target (use 'local' or 'remote' for conflict resolution)."""
            result = await self.handle_sync_pull(conflict_resolution)
            return result[0].text if result else "Sync pull failed"

        @self.mcp_server.tool()
        async def configure_sync(sync_directory: str) -> str:
            """Configure sync directory for multi-device synchronization."""
            result = await self.handle_configure_sync(sync_directory)
            return result[0].text if result else "Configuration failed"

    async def handle_export_memories(
        self,
        output_path: str,
        format: str,
        filter_quadrants: Optional[List[str]]
    ) -> list[types.TextContent]:
        """Handle memory export request."""
        try:
            if format.lower() == "json":
                result = await self.exporter.export_to_json(
                    output_path,
                    filter_quadrants=filter_quadrants
                )
                text = f"""✅ Export Complete (JSON)

Records exported: {result['records_exported']}
Output file: {result['output_path']}
Embeddings included: {result['include_embeddings']}
"""
            elif format.lower() == "markdown":
                result = await self.exporter.export_to_markdown(
                    output_path,
                    filter_quadrants=filter_quadrants
                )
                text = f"""✅ Export Complete (Markdown)

Files created: {result['files_created']}
Output directory: {result['output_directory']}
Grouped by quadrant: {result['grouped_by_quadrant']}
"""
            elif format.lower() == "csv":
                result = await self.exporter.export_to_csv(
                    output_path,
                    filter_quadrants=filter_quadrants
                )
                text = f"""✅ Export Complete (CSV)

Records exported: {result['records_exported']}
Output file: {result['output_path']}
"""
            else:
                return [types.TextContent(type="text", text=f"❌ Unknown format: {format}. Use: json, markdown, csv")]

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Export failed: {e}")]

    async def handle_import_memories(
        self,
        input_path: str,
        format: str,
        skip_existing: bool
    ) -> list[types.TextContent]:
        """Handle memory import request."""
        try:
            if format.lower() == "json":
                result = await self.importer.import_from_json(
                    input_path,
                    skip_existing=skip_existing
                )
            elif format.lower() == "obsidian":
                result = await self.importer.import_from_obsidian_vault(input_path)
            elif format.lower() == "csv":
                result = await self.importer.import_from_csv(
                    input_path,
                    skip_existing=skip_existing
                )
            else:
                return [types.TextContent(type="text", text=f"❌ Unknown format: {format}. Use: json, obsidian, csv")]

            text = f"""✅ Import Complete

Total records: {result.get('total_records', result.get('total_files', 0))}
Imported: {result['imported']}
Skipped (existing): {result.get('skipped', 0)}
Errors: {result['errors']}
"""
            if result.get('error_details'):
                text += "\nErrors (first 10):\n"
                for err in result['error_details']:
                    text += f"  - {err}\n"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Import failed: {e}")]

    async def handle_search_memories(
        self,
        query: str,
        memory_types: Optional[List[str]],
        quadrants: Optional[List[str]],
        min_confidence: Optional[str],
        min_importance: Optional[float],
        max_importance: Optional[float],
        created_after: Optional[str],
        created_before: Optional[str],
        include_tags: Optional[List[str]],
        exclude_tags: Optional[List[str]],
        content_contains: Optional[str],
        limit: int,
        offset: int
    ) -> list[types.TextContent]:
        """Handle advanced memory search with filters."""
        try:
            # Build SearchFilters from parameters
            filters = SearchFilters()
            if memory_types:
                filters.memory_types = memory_types
            if quadrants:
                filters.quadrants = quadrants
            if min_confidence:
                filters.min_confidence = min_confidence
            if min_importance is not None:
                filters.min_importance = min_importance
            if max_importance is not None:
                filters.max_importance = max_importance
            if include_tags:
                filters.include_tags = include_tags
            if exclude_tags:
                filters.exclude_tags = exclude_tags
            if content_contains:
                filters.content_contains = content_contains

            # Parse date filters
            if created_after:
                filters.created_after = self.advanced_search.parse_date_filter(created_after)
            if created_before:
                filters.created_before = self.advanced_search.parse_date_filter(created_before)

            # Execute search
            result = await self.advanced_search.search(
                query=query,
                filters=filters,
                limit=limit,
                offset=offset
            )

            # Format results
            if not result["results"]:
                return [types.TextContent(type="text", text="🔍 No memories found matching your criteria.")]

            text = f"""🔍 Search Results ({result['returned']} of {result['total']})

Filters Applied: {result['filters_applied']}
---
"""
            for i, mem in enumerate(result["results"], 1):
                text += f"\n{i}. [{mem['type'].upper()}] {mem['summary'][:80]}"
                if len(mem['summary']) > 80:
                    text += "..."
                text += f"\n   ID: {mem['id']}"
                text += f" | Quadrants: {', '.join(mem['quadrants'])}"
                text += f" | Confidence: {mem['confidence']}"
                text += f" | Importance: {mem['importance']:.2f}"
                if mem.get('tags'):
                    text += f"\n   Tags: {', '.join(mem['tags'][:5])}"
                if mem.get('content_preview'):
                    preview = mem['content_preview'][:120].replace(chr(10), ' ')
                    text += f"\n   Preview: {preview}..."
                text += "\n"

            if result['total'] > result['returned']:
                text += f"\n📄 Page {offset // limit + 1} | Use offset={offset + limit} for next page"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Search failed: {e}")]

    async def handle_create_backup(
        self,
        description: str,
        include_vectors: bool,
        include_graph: bool,
        include_queue: bool
    ) -> list[types.TextContent]:
        """Handle backup creation request."""
        try:
            result = await self.backup_manager.create_backup(
                description=description,
                include_vectors=include_vectors,
                include_graph=include_graph,
                include_queue=include_queue
            )

            size_mb = result['size_bytes'] / (1024 * 1024)

            text = f"""✅ Backup Created Successfully

Backup ID: {result['backup_id']}
Size: {size_mb:.2f} MB
Includes:
  - Vectors: {'✓' if result['includes_vectors'] else '✗'}
  - Graph: {'✓' if result['includes_graph'] else '✗'}
  - Queue: {'✓' if result['includes_queue'] else '✗'}

Location: {result['backup_path']}
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Backup failed: {e}")]

    async def handle_restore_backup(
        self,
        backup_id: str,
        force: bool
    ) -> list[types.TextContent]:
        """Handle backup restore request."""
        try:
            result = await self.backup_manager.restore_backup(backup_id, force)

            if not result['success']:
                if result.get('requires_force'):
                    return [types.TextContent(
                        type="text",
                        text=f"⚠️ Existing data detected. Use force=True to overwrite.\nError: {result['error']}"
                    )]
                return [types.TextContent(type="text", text=f"❌ Restore failed: {result['error']}")]

            text = f"""✅ Backup Restored Successfully

Backup ID: {result['backup_id']}
Restored components:
"""
            for component in result['restored']:
                text += f"  ✓ {component}\n"

            if result['errors']:
                text += "\n⚠️ Errors:\n"
                for error in result['errors']:
                    text += f"  - {error}\n"

            text += f"\n📝 Description: {result['manifest'].get('description', 'N/A')}"
            text += f"\n📅 Created: {result['manifest'].get('created_at', 'N/A')}"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Restore failed: {e}")]

    async def handle_list_backups(self) -> list[types.TextContent]:
        """Handle backup list request."""
        try:
            backups = await self.backup_manager.list_backups()
            stats = self.backup_manager.get_backup_stats()

            if not backups:
                return [types.TextContent(
                    type="text",
                    text=f"📦 No backups found.\n\nBackup directory: {stats['backup_directory']}"
                )]

            text = f"""📦 Available Backups ({stats['backup_count']} total, {stats['total_size_mb']:.2f} MB)

"""
            for backup in backups:
                size_mb = backup.size_bytes / (1024 * 1024)
                text += f"""ID: {backup.id}
  Description: {backup.description}
  Created: {backup.created_at.strftime('%Y-%m-%d %H:%M:%S')}
  Size: {size_mb:.2f} MB
  Includes: {'V' if backup.includes_vectors else ''}{'G' if backup.includes_graph else ''}{'Q' if backup.includes_queue else ''}
---
"""

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Failed to list backups: {e}")]

    async def handle_delete_backup(self, backup_id: str) -> list[types.TextContent]:
        """Handle backup deletion request."""
        try:
            result = await self.backup_manager.delete_backup(backup_id)

            if result['success']:
                freed_mb = result['freed_bytes'] / (1024 * 1024)
                return [types.TextContent(
                    type="text",
                    text=f"✅ Backup {result['backup_id']} deleted. Freed {freed_mb:.2f} MB."
                )]
            else:
                return [types.TextContent(type="text", text=f"❌ Delete failed: {result['error']}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Delete failed: {e}")]

    async def handle_run_maintenance(
        self,
        dry_run: bool,
        stale_days: int,
        remove_duplicates: bool
    ) -> list[types.TextContent]:
        """Handle maintenance/garbage collection request."""
        try:
            result = await self.garbage_collector.run_full_cleanup(
                dry_run=dry_run,
                stale_days=stale_days,
                remove_duplicates=remove_duplicates
            )

            mode_text = "DRY RUN (no changes made)" if dry_run else "LIVE RUN"
            text = f"""🔧 Maintenance Report - {mode_text}

📊 Summary:
  Total items that would be removed: {result['summary']['total_items_removed']}
  Space that would be reclaimed: {result['summary']['total_space_reclaimed_mb']:.2f} MB
  Operations run: {result['summary']['operations_run']}

📋 Details:
"""
            for op in result['operations']:
                text += f"""
{op['cleanup_type'].upper()}:
  Items found: {op['items_found']}
  Items removed: {op['items_removed']}
  Space reclaimed: {op['space_reclaimed_mb']:.2f} MB
  Errors: {len(op['errors'])}
"""

            if dry_run:
                text += "\n⚠️ This was a dry run. No changes were made.\n"
                text += "Set dry_run=False to actually perform cleanup.\n"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Maintenance failed: {e}")]

    async def handle_storage_stats(self) -> list[types.TextContent]:
        """Handle storage statistics request."""
        try:
            stats = await self.garbage_collector.get_storage_stats()

            if 'error' in stats:
                return [types.TextContent(type="text", text=f"❌ Failed to get stats: {stats['error']}")]

            text = f"""📊 Storage Statistics

Vector Memories: {stats['vector_memories']:,}
Graph Nodes: {stats['graph_nodes']:,}
Graph Edges: {stats['graph_edges']:,}

Last Updated: {stats['timestamp']}

💡 Tip: Run `run_maintenance` to clean up orphaned records and duplicates.
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Stats failed: {e}")]

    async def handle_analytics_report(self) -> list[types.TextContent]:
        """Handle analytics report request."""
        try:
            report = await self.analytics.generate_full_report()

            overview = report['overview']
            health = report['health']
            quadrants = report['quadrants']
            types_dist = report['types']

            text = f"""📊 Memory Analytics Report

╔══════════════════════════════════════════════════════════════╗
║ OVERVIEW                                                     ║
╠══════════════════════════════════════════════════════════════╣
  Total Memories: {overview.get('total_memories', 0):,}
  Average Importance: {overview.get('average_importance', 0):.3f}
  High Importance: {overview.get('high_importance_count', 0)}
  Unique Tags: {overview.get('unique_tags', 0)}
  Date Span: {overview.get('date_range', {}).get('span_days', 0)} days
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║ HEALTH SCORE: {health.get('overall', 0):.2f} ({health.get('status', 'unknown').upper()}){' ' * (35 - len(health.get('status', 'unknown')))}║
╠══════════════════════════════════════════════════════════════╣
  Quadrant Coverage: {health.get('factors', {}).get('quadrant_coverage', 0):.2f}
  Quality Ratio: {health.get('factors', {}).get('quality_ratio', 0):.2f}
  Recent Activity: {health.get('factors', {}).get('recent_activity', 0):.2f}
  Connectivity: {health.get('factors', {}).get('connectivity', 0):.2f}
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║ QUADRANTS                                                    ║
╠══════════════════════════════════════════════════════════════╣
"""
            for quad, stats in quadrants.items():
                text += f"  {quad:15} | {stats.count:5} | avg imp: {stats.avg_importance:.2f}\n"

            text += """╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║ MEMORY TYPES                                                 ║
╠══════════════════════════════════════════════════════════════╣
"""
            for mem_type, count in sorted(types_dist.items(), key=lambda x: -x[1]):
                text += f"  {mem_type:20} : {count:,}\n"

            text += """╚══════════════════════════════════════════════════════════════╝

Top Tags:"""

            for tag_info in report['tags'].get('top_tags', [])[:10]:
                text += f"\n  #{tag_info['tag']} ({tag_info['count']})"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Analytics failed: {e}")]

    async def handle_list_templates(self) -> list[types.TextContent]:
        """Handle template list request."""
        try:
            templates = self.template_manager.list_templates()

            text = """📝 Available Memory Templates

"""
            for t in templates:
                text += f"""{t['name']} (ID: {t['id']})
  Description: {t['description']}
  Quadrants: {', '.join(t['default_quadrants'])}
  Tags: {', '.join(t['default_tags'])}
  Suggested Importance: {t['suggested_importance']}
---
"""

            text += """
💡 Usage:
  save_with_template(template_id="meeting_notes", content="...")

Or get suggestions:
  suggest_template(content="Your raw text here")
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Templates failed: {e}")]

    async def handle_save_with_template(
        self,
        template_id: str,
        content: str,
        summary: str,
        custom_tags: Optional[List[str]]
    ) -> list[types.TextContent]:
        """Handle save with template request."""
        try:
            # Apply template
            result = self.template_manager.apply_template(template_id, content)

            if "error" in result:
                return [types.TextContent(type="text", text=f"❌ Template error: {result['error']}")]

            template = self.template_manager.get_template(template_id)

            # Build metadata
            tags = list(template.default_tags)
            if custom_tags:
                tags.extend(custom_tags)
            tags = list(set(tags))

            # Save memory
            memory_id = str(uuid.uuid4())
            await self._save_memory(
                memory_id=memory_id,
                summary=summary or f"{template.name} - {datetime.now().strftime('%Y-%m-%d')}",
                content=content,
                quadrants=template.default_quadrants,
                tags=tags,
                importance=template.suggested_importance
            )

            text = f"""✅ Memory Saved with Template

Template: {template.name}
Memory ID: {memory_id}
Quadrants: {', '.join(template.default_quadrants)}
Tags: {', '.join(tags)}
Importance: {template.suggested_importance}
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Save failed: {e}")]

    async def handle_suggest_template(self, content: str) -> list[types.TextContent]:
        """Handle template suggestion request."""
        try:
            suggestions = self.template_manager.suggest_template(content)

            if not suggestions:
                return [types.TextContent(
                    type="text",
                    text="🤔 No strong template matches. Use list_templates to see all options."
                )]

            text = """💡 Suggested Templates

"""
            for s in suggestions:
                text += f"""{s['name']} (ID: {s['template_id']})
  Match Score: {s['match_score']}
  Description: {s['description']}
---
"""

            text += f"\nTop match: Use template_id='{suggestions[0]['template_id']}'"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Suggestion failed: {e}")]

    async def handle_sync_status(self) -> list[types.TextContent]:
        """Handle sync status request."""
        try:
            status = await self.sync_manager.sync_status()

            text = f"""🔄 Multi-Device Sync Status

Device ID: {status['device_id']}
Sync Enabled: {'✓' if status['sync_enabled'] else '✗'}
Last Sync: {status['last_sync'] or 'Never'}

Configuration:
  Sync Directory: {status['sync_directory'] or 'Not configured'}
  Local Bundles: {status['bundles_available']}

💡 Usage:
  configure_sync(sync_directory="/path/to/sync")
  sync_push()          # Upload to sync target
  sync_pull()          # Download from sync target
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Sync status failed: {e}")]

    async def handle_sync_push(self, include_vectors: bool) -> list[types.TextContent]:
        """Handle sync push request."""
        try:
            result = await self.sync_manager.sync_push(
                self.vector_store,
                self.graph_store,
                include_vectors=include_vectors
            )

            text = f"""🔄 Sync Push {'✅' if result.status.value == 'success' else '❌'}

Status: {result.status.value}
Message: {result.message}
Records Uploaded: {result.records_uploaded}
"""
            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Sync push failed: {e}")]

    async def handle_sync_pull(self, conflict_resolution: str) -> list[types.TextContent]:
        """Handle sync pull request."""
        try:
            result = await self.sync_manager.sync_pull(
                self.vector_store,
                self.graph_store,
                conflict_resolution=conflict_resolution
            )

            text = f"""🔄 Sync Pull {'✅' if result.status.value == 'success' else '⚠️'}

Status: {result.status.value}
Message: {result.message}
Records Downloaded: {result.records_downloaded}
Conflicts: {len(result.conflicts)}
"""
            if result.conflicts:
                text += "\n⚠️ Conflicts detected:\n"
                for c in result.conflicts[:5]:
                    text += f"  - {c}\n"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Sync pull failed: {e}")]

    async def handle_configure_sync(self, sync_directory: str) -> list[types.TextContent]:
        """Handle sync configuration request."""
        try:
            result = await self.sync_manager.setup_remote(sync_directory)

            if result['success']:
                text = f"""✅ Sync Configured

Sync Directory: {result['remote_url']}
Device ID: {result['device_id']}

{result['message']}
"""
                return [types.TextContent(type="text", text=text)]
            else:
                return [types.TextContent(type="text", text=f"❌ Configuration failed: {result.get('error', 'Unknown')}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Configuration failed: {e}")]

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

    async def handle_mem_query(self, query: str, quadrant_hint: Optional[str] = None,
                                context_limit: Optional[int] = None) -> list[types.TextContent]:
        # 1. Routing (using FAST model via router)
        if not quadrant_hint:
            classification = await self.router.classify_request(query)
            quadrant = classification.quadrant
        else:
            quadrant = quadrant_hint

        # 2. Progressive Tiered Retrieval with token budgeting
        query_vector = await self.llm.get_embedding(query)
        search_quadrants = [quadrant]
        if quadrant != "ai_instructions":
            search_quadrants.append("ai_instructions")

        # Create request node early (for dynamic scoring context)
        request_id = str(uuid.uuid4())

        # Use progressive disclosure: L0 -> L1 with token budget
        context_result = await self.tiered_manager.get_progressive_context(
            query_vector,
            quadrants=search_quadrants,
            max_tokens=context_limit,
            request_id=request_id
        )

        # 3. Update recency for included memories
        for item in context_result["l0_items"]:
            self.vector_store.update_memory_access(item["id"])

        # 4. Graph Mapping (Record the request and link to memories that fulfilled it)
        self.graph_store.add_request_node(request_id, query, context_result["context_string"])
        for mem_id in context_result["l2_candidates"][:3]:
            self.graph_store.link_request_to_memory(request_id, mem_id)

        # 5. Build response with progressive context
        response_text = f"Quadrant: {quadrant}\n\n"
        response_text += context_result["context_string"]

        # Add hint about L2 availability
        if context_result["l2_candidates"]:
            response_text += f"\n💡 Use fetch_detail with IDs: {', '.join(context_result['l2_candidates'][:3])} for full content\n"

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

    async def handle_fetch_reflections(
        self,
        pattern_type: str = "all",
        min_confidence: str = "medium"
    ) -> list[types.TextContent]:
        """Retrieve synthesized reflections about user patterns."""
        # Search for reflections in vector store
        query_vector = await self.llm.get_embedding("user patterns preferences behavior")

        # Search in general quadrant (reflections are stored there)
        results = self.vector_store.search_memories(
            query_vector,
            limit=20,
            filter_quadrants=["general"]
        )

        # Filter for reflections only
        reflections = []
        for res in results:
            payload = res.payload
            if payload.get("type") != "reflection":
                continue

            # Filter by confidence
            confidence = payload.get("confidence", "medium")
            confidence_levels = {"high": 3, "medium": 2, "low": 1}
            if confidence_levels.get(confidence, 0) < confidence_levels.get(min_confidence, 2):
                continue

            # Filter by pattern type
            res_pattern_type = payload.get("pattern_type", "preference")
            if pattern_type != "all" and res_pattern_type != pattern_type:
                continue

            reflections.append({
                "id": res.id,
                "summary": payload.get("summary", "Untitled"),
                "reflection": payload.get("content", ""),
                "confidence": confidence,
                "pattern_type": res_pattern_type,
                "memory_count": payload.get("memory_count", 0),
                "supporting_evidence": payload.get("supporting_evidence", "")
            })

        if not reflections:
            return [types.TextContent(type="text", text="No reflections found. Memories need to be consolidated to generate reflections.")]

        # Format response
        response_text = f"=== Synthesized Reflections ({len(reflections)} found) ===\n\n"

        for r in reflections:
            response_text += f"📊 {r['summary']}\n"
            response_text += f"   Confidence: {r['confidence']} | Type: {r['pattern_type']}\n"
            response_text += f"   Based on: {r['memory_count']} memories\n"
            response_text += f"   Insight: {r['reflection']}\n"
            if r['supporting_evidence']:
                response_text += f"   Evidence: {r['supporting_evidence'][:100]}...\n"
            response_text += f"   ID: {r['id']}\n\n"

        response_text += "Use fetch_detail with a reflection ID to see full details.\n"

        return [types.TextContent(type="text", text=response_text)]

    async def handle_view_conflicts(self, status: str = "all") -> list[types.TextContent]:
        """View conflicting memories that require resolution."""
        # Search for memories with conflict markers
        query_vector = await self.llm.get_embedding("conflict contradiction override")

        results = self.vector_store.search_memories(
            query_vector,
            limit=50,
            filter_quadrants=None  # Search all quadrants
        )

        conflicts = []
        needs_review = []

        for res in results:
            payload = res.payload

            # Check for needs_review flag (deferred conflicts)
            if payload.get("needs_review"):
                needs_review.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content": payload.get("content", ""),
                    "reason": payload.get("conflict_reason", "Unknown")
                })

            # Check for conflict edges in graph
            related = self.graph_store.get_related_nodes(res.id, "CONFLICTS_WITH")
            if related:
                conflict_entries = []
                for rel in related:
                    rel_metadata = rel.get("metadata", {})
                    conflict_entries.append({
                        "with": rel.get("target"),
                        "resolution": rel_metadata.get("resolution", "unknown"),
                        "reason": rel_metadata.get("reason", ""),
                        "winner": rel_metadata.get("winner")
                    })

                conflicts.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content": payload.get("content", ""),
                    "type": payload.get("type", "general"),
                    "conflicts_with": conflict_entries
                })

        # Filter based on status
        if status == "unresolved":
            conflicts = [c for c in conflicts if any(
                cw.get("resolution") == "keep_both_marked" or cw.get("winner") is None
                for cw in c["conflicts_with"]
            )]
        elif status == "resolved":
            conflicts = [c for c in conflicts if any(
                cw.get("winner") is not None
                for cw in c["conflicts_with"]
            )]
        elif status == "deferred":
            return self._format_conflict_response([], needs_review)

        return self._format_conflict_response(conflicts, needs_review)

    def _format_conflict_response(
        self,
        conflicts: List[Dict],
        needs_review: List[Dict]
    ) -> list[types.TextContent]:
        """Format conflict data for display."""
        response_text = "=== Memory Conflicts Report ===\n\n"

        if needs_review:
            response_text += f"⚠️  Needs Manual Review ({len(needs_review)} items):\n"
            response_text += "-" * 40 + "\n"
            for item in needs_review:
                response_text += f"  ID: {item['id']}\n"
                response_text += f"  Summary: {item['summary']}\n"
                response_text += f"  Reason: {item['reason']}\n\n"

        if conflicts:
            response_text += f"🔗 Active Conflicts ({len(conflicts)} memories involved):\n"
            response_text += "-" * 40 + "\n"
            for conflict in conflicts:
                response_text += f"\n  📌 {conflict['summary']}\n"
                response_text += f"     ID: {conflict['id']}\n"
                response_text += f"     Type: {conflict['type']}\n"

                for cw in conflict["conflicts_with"]:
                    winner_marker = " 👑" if cw.get("winner") == conflict["id"] else ""
                    response_text += f"     ⚔️  vs {cw['with'][:8]}... "
                    response_text += f"[{cw['resolution']}]{winner_marker}\n"
                    if cw.get("reason"):
                        response_text += f"        Reason: {cw['reason'][:60]}...\n"
        else:
            response_text += "\n✅ No conflicts found.\n"

        response_text += "\n"
        response_text += "Legend:\n"
        response_text += "  👑 = Winner of the conflict\n"
        response_text += "  keep_existing = Existing memory prioritized\n"
        response_text += "  replace_with_new = New memory took precedence\n"
        response_text += "  keep_both_marked = Both retained (unresolved)\n"
        response_text += "  defer = Requires manual review\n"

        return [types.TextContent(type="text", text=response_text)]

    async def handle_optimization_report(self, window_days: int = 7) -> list[types.TextContent]:
        """Retrieve feedback-driven optimization statistics."""
        report = self.feedback_optimizer.get_optimization_report(window_days)

        response_text = f"""=== Feedback Optimization Report ({window_days} days) ===

📊 Feedback Statistics:
  Total Feedback: {report['total_feedback']}
  Positive Ratio: {report['positive_ratio']:.1%} if report['positive_ratio'] else 'N/A'
  Negative Count: {report['negative_count']}

🔧 Current Weights:
  Relevance (W_rel):   {report['current_weights']['W_rel']:.3f}
  Recency   (W_rec):   {report['current_weights']['W_rec']:.3f}
  Importance (W_imp):  {report['current_weights']['W_imp']:.3f}

📈 Common Failures:
  Most Common: {report['most_common_failure'] or 'None recorded'}

  Breakdown:
"""
        if report.get('failure_breakdown'):
            for failure_type, count in sorted(report['failure_breakdown'].items(), key=lambda x: x[1], reverse=True):
                response_text += f"    - {failure_type}: {count}\n"
        else:
            response_text += "    No failures recorded\n"

        response_text += f"""
⚙️  Auto-Adjustments:
  Weight adjustments made: {report['adjustments_made']}

Notes:
- Weights auto-adjust based on negative feedback with high/medium confidence
- Default weights: W_rel=0.5, W_rec=0.3, W_imp=0.2 (sum to 1.0)
- Maximum deviation from defaults: ±0.2
"""
        return [types.TextContent(type="text", text=response_text)]

    # === Task Management Handlers ===

    async def handle_add_task(
        self,
        title: str,
        description: str,
        priority: str,
        due_date: Optional[str],
        tags: Optional[List[str]],
        estimated_minutes: Optional[int],
        context: str
    ) -> list[types.TextContent]:
        """Handle adding a new task."""
        try:
            result = await self.task_manager.add_task(
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                tags=tags,
                estimated_minutes=estimated_minutes,
                context=context
            )

            if result["success"]:
                task = result["task"]
                text = f"""✅ Task Added

ID: {task['id']}
Title: {task['title']}
Priority: {task['priority'].upper()}
Status: {task['status']}
"""
                if task.get('due_date'):
                    text += f"Due: {task['due_date']}\n"

                text += f"\nI'll remind you about this based on priority."

                return [types.TextContent(type="text", text=text)]
            else:
                return [types.TextContent(type="text", text=f"❌ Failed: {result.get('error', 'Unknown')}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]

    async def handle_list_tasks(
        self,
        status: str,
        priority: Optional[str],
        limit: int
    ) -> list[types.TextContent]:
        """Handle listing tasks."""
        try:
            tasks = self.task_manager.list_tasks(
                status=status if status != "all" else None,
                priority=priority,
                limit=limit
            )

            if not tasks:
                return [types.TextContent(type="text", text="📋 No tasks found. Use add_task to create one!")]

            # Calculate urgency scores
            now = datetime.now()
            scored_tasks = []
            for task in tasks:
                score = self.task_manager._calculate_urgency_score(task, now)
                scored_tasks.append((task, score))

            # Sort by score
            scored_tasks.sort(key=lambda x: x[1], reverse=True)

            text = f"📋 Your Tasks ({len(tasks)} total)\n\n"

            for i, (task, score) in enumerate(scored_tasks, 1):
                urgency = "🔴" if score > 0.9 else "🟠" if score > 0.75 else "🟡" if score > 0.5 else "⚪"
                text += f"{urgency} {i}. {task.title}\n"
                text += f"   ID: {task.id[:8]}... | Priority: {task.priority.upper()} | Status: {task.status}\n"

                if task.due_date:
                    due = datetime.fromisoformat(task.due_date.replace('Z', '+00:00'))
                    days_until = (due - now).days
                    if days_until < 0:
                        text += f"   ⚠️ OVERDUE by {abs(days_until)} days\n"
                    elif days_until == 0:
                        text += f"   ⏰ Due today\n"
                    else:
                        text += f"   📅 Due in {days_until} days\n"

                text += "\n"

            text += "💡 Use complete_task(task_id) to mark done\n"
            text += "💡 Use update_task(task_id, priority='high') to reprioritize"

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]

    async def handle_complete_task(
        self,
        task_id: str,
        notes: str
    ) -> list[types.TextContent]:
        """Handle completing a task."""
        try:
            result = await self.task_manager.complete_task(task_id, notes)

            if result["success"]:
                return [types.TextContent(
                    type="text",
                    text=f"✅ Task completed!\n\n{result['task']['title']}\n\nGreat job! 🎉"
                )]
            else:
                return [types.TextContent(type="text", text=f"❌ {result.get('error', 'Failed')}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]

    async def handle_update_task(
        self,
        task_id: str,
        priority: Optional[str],
        due_date: Optional[str],
        status: Optional[str]
    ) -> list[types.TextContent]:
        """Handle updating a task."""
        try:
            result = await self.task_manager.update_task(
                task_id=task_id,
                priority=priority,
                due_date=due_date,
                status=status
            )

            if result["success"]:
                return [types.TextContent(
                    type="text",
                    text=f"✅ Task updated!\n\n{result['task']['title']}\nPriority: {result['task']['priority']}\nStatus: {result['task']['status']}"
                )]
            else:
                return [types.TextContent(type="text", text=f"❌ {result.get('error', 'Failed')}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]

    async def handle_task_stats(self) -> list[types.TextContent]:
        """Handle task statistics."""
        try:
            stats = self.task_manager.get_stats()

            text = f"""📊 Task Statistics

Total Tasks: {stats['total']}
Pending: {stats.get('pending', 0)}
Overdue: {stats.get('overdue', 0)} ⚠️

By Priority:
"""
            for priority, count in sorted(stats['by_priority'].items(), key=lambda x: -self.task_manager.PRIORITY_WEIGHTS.get(x[0], 0)):
                text += f"  {priority.upper()}: {count}\n"

            if stats.get('overdue', 0) > 0:
                text += "\n🔔 You have overdue tasks! Use list_tasks() to see them."

            return [types.TextContent(type="text", text=text)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]

    async def run_stdio(self):
        """Run in stdio mode (for client-spawned processes)."""
        # FastMCP's run() is synchronous, so we run it in a thread
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.mcp_server.run(transport="stdio")
        )

    async def run_http(self, host: str = "127.0.0.1", port: int = 8080):
        """Run in HTTP mode (standalone service with streamable-http transport)."""
        print(f"MemCore HTTP server starting on http://{host}:{port}")
        print(f"  - MCP endpoint: http://{host}:{port}/mcp")
        print(f"  - Health check: http://{host}:{port}/health")
        print(f"  - Status report: http://{host}:{port}/status")

        # FastMCP's run() with streamable-http transport
        # Note: This starts its own uvicorn server
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.mcp_server.run(transport="streamable-http", port=port)
        )
    
    async def run(
        self,
        mode: str = "stdio",
        host: str = "127.0.0.1",
        port: int = 8080,
        dashboard_port: Optional[int] = None
    ):
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

        # 7. Start dashboard if port specified and available
        if dashboard_port and DASHBOARD_AVAILABLE:
            self.dashboard_port = dashboard_port
            self.dashboard_server = DashboardServer(
                vector_store=self.vector_store,
                graph_store=self.graph_store,
                llm=self.llm,
                host=host,
                port=dashboard_port,
                data_dir=DATA_DIR
            )
            # Start dashboard in background
            asyncio.create_task(self.dashboard_server.start())
            print(f"[Dashboard] Web dashboard running on http://{host}:{dashboard_port}")
        elif dashboard_port and not DASHBOARD_AVAILABLE:
            print("[Dashboard] Dashboard dependencies not installed. Run: uv sync --extra dashboard")

        # 8. Start reminder scheduler for task management
        self.reminder_scheduler.start()
        print("[Tasks] Reminder scheduler started")

        # 9. Start MCP loop in chosen mode
        if mode == "stdio":
            await self.run_stdio()
        elif mode == "http":
            await self.run_http(host, port)
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'stdio' or 'http'.")

def main():
    parser = argparse.ArgumentParser(description="MemCore - Agentic Memory Management System")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (client-spawned) or http (standalone service)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to in HTTP mode (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to in HTTP mode (default: 8080)"
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8081,
        help="Port for web dashboard (default: 8081, set to 0 to disable)"
    )

    args = parser.parse_args()

    agent = MemCoreAgent()
    # Pass dashboard_port if non-zero
    dashboard_port = args.dashboard_port if args.dashboard_port != 0 else None
    asyncio.run(agent.run(mode=args.mode, host=args.host, port=args.port, dashboard_port=dashboard_port))

if __name__ == "__main__":
    main()
