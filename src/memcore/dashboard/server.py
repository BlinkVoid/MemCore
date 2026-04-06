"""
MemCore Dashboard Router

Provides routes and handlers for the web dashboard to be integrated
directly into the main MCP Starlette application.
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from starlette.responses import JSONResponse, HTMLResponse, PlainTextResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates

try:
    from src.memcore.dashboard.analytics import AnalyticsProvider
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    AnalyticsProvider = None


class DashboardRouter:
    """
    Dashboard handlers for MemCore.
    Designed to be attached to an existing Starlette application.
    """

    def __init__(
        self,
        vector_store,
        graph_store,
        llm,
        queue=None,
        data_dir: str = None
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm = llm
        self.queue = queue
        self.data_dir = Path(data_dir) if data_dir else Path("dataCrystal")
        self.activity_log_path = self.data_dir / "logs" / "activity.jsonl"

        # Initialize analytics provider
        if ANALYTICS_AVAILABLE and vector_store and graph_store:
            self.analytics = AnalyticsProvider(vector_store, graph_store, str(self.data_dir))
        else:
            self.analytics = None

        # Setup templates
        template_dir = Path(__file__).parent / "templates"
        self.templates = Jinja2Templates(directory=str(template_dir))

    def attach_routes(self, app):
        """Attach dashboard routes to a Starlette application."""
        app.add_route("/", self.handle_index, methods=["GET"])
        app.add_route("/analytics", self.handle_analytics_page, methods=["GET"])
        
        # API Routes
        app.add_route("/api/memories", self.handle_api_memories, methods=["GET"])
        app.add_route("/api/memories/{memory_id}", self.handle_api_memory_detail, methods=["GET"])
        app.add_route("/api/memories/{memory_id}", self.handle_api_memory_delete, methods=["DELETE"])
        app.add_route("/api/memories/{memory_id}", self.handle_api_memory_update, methods=["PUT"])
        app.add_route("/api/search", self.handle_api_search, methods=["POST"])
        app.add_route("/api/stats", self.handle_api_stats, methods=["GET"])
        app.add_route("/api/conflicts", self.handle_api_conflicts, methods=["GET"])
        app.add_route("/api/reflections", self.handle_api_reflections, methods=["GET"])
        app.add_route("/api/weights", self.handle_api_weights, methods=["GET"])
        app.add_route("/api/queue", self.handle_api_queue, methods=["GET"])
        app.add_route("/api/consolidate", self.handle_api_consolidate, methods=["POST"])
        app.add_route("/api/process-queue", self.handle_api_process_queue, methods=["POST"])
        app.add_route("/api/activity", self.handle_api_activity, methods=["GET"])
        app.add_route("/api/logs", self.handle_api_logs, methods=["GET"])
        app.add_route("/api/analytics", self.handle_api_analytics, methods=["GET"])
        app.add_route("/api/heatmap", self.handle_api_heatmap, methods=["GET"])
        app.add_route("/api/stop", self.handle_api_stop, methods=["POST"])

    async def handle_index(self, request: Request) -> HTMLResponse:
        """Serve the main dashboard HTML."""
        return self.templates.TemplateResponse("index.html", {"request": request})

    async def handle_analytics_page(self, request: Request) -> HTMLResponse:
        """Serve the analytics dashboard HTML."""
        return self.templates.TemplateResponse("analytics.html", {"request": request})

    async def handle_api_memories(self, request: Request) -> JSONResponse:
        """Get paginated list of memories."""
        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
            quadrant = request.query_params.get("quadrant")
            mem_type = request.query_params.get("type")

            # Get all memories via search with dummy vector
            query_vector = await self.llm.get_embedding("list all memories")

            filter_quadrants = [quadrant] if quadrant else None
            results = self.vector_store.search_memories(
                query_vector,
                limit=limit + offset,
                filter_quadrants=filter_quadrants
            )

            memories = []
            for res in results[offset:]:
                payload = res.payload
                if mem_type and payload.get("type") != mem_type:
                    continue

                memories.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content_preview": payload.get("content", "")[:200],
                    "quadrants": payload.get("quadrants", ["general"]),
                    "tags": payload.get("tags", []),
                    "type": payload.get("type", "raw"),
                    "importance": payload.get("importance", 0.5),
                    "created_at": payload.get("created_at"),
                    "score": res.score
                })

            return JSONResponse({
                "memories": memories,
                "total": len(results),
                "limit": limit,
                "offset": offset
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_memory_detail(self, request: Request) -> JSONResponse:
        """Get detailed information about a specific memory."""
        try:
            memory_id = request.path_params["memory_id"]
            result = self.vector_store.get_memory_by_id(memory_id)

            if not result:
                return JSONResponse({"error": "Memory not found"}, status_code=404)

            payload = result[0].payload
            related = self.graph_store.get_related_nodes(memory_id, "RELATED_TO")

            return JSONResponse({
                "id": memory_id,
                "content": payload.get("content", ""),
                "summary": payload.get("summary", ""),
                "quadrants": payload.get("quadrants", ["general"]),
                "tags": payload.get("tags", []),
                "type": payload.get("type", "raw"),
                "importance": payload.get("importance", 0.5),
                "confidence": payload.get("confidence", "medium"),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "source_uri": payload.get("source_uri"),
                "related_count": len(related)
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_memory_delete(self, request: Request) -> JSONResponse:
        """Delete a specific memory."""
        try:
            memory_id = request.path_params["memory_id"]
            self.vector_store.delete_memory(memory_id)
            self.graph_store.delete_node(memory_id)
            return JSONResponse({"success": True, "deleted": memory_id})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_memory_update(self, request: Request) -> JSONResponse:
        """Update a specific memory."""
        try:
            memory_id = request.path_params["memory_id"]
            body = await request.json()

            memory_data = self.vector_store.get_memory_by_id(memory_id)
            if not memory_data:
                return JSONResponse({"error": "Memory not found"}, status_code=404)

            existing = memory_data[0].payload
            updates = {}

            if "content" in body:
                updates["content"] = body["content"]
                new_vector = await self.llm.get_embedding(body["content"])
                self.vector_store.upsert_memory(memory_id, new_vector, {**existing, **updates})
            else:
                if "summary" in body: updates["summary"] = body["summary"]
                if "importance" in body: updates["importance"] = body["importance"]
                if updates: self.vector_store.update_memory(memory_id, updates)

            self.graph_store.update_node_metadata(memory_id, {
                "summary": updates.get("summary", existing.get("summary", "")),
                "type": existing.get("type", "memory")
            })

            return JSONResponse({"success": True, "updated": memory_id, "fields": list(updates.keys())})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_search(self, request: Request) -> JSONResponse:
        """Search memories by query."""
        try:
            body = await request.json()
            query = body.get("query", "")
            limit = body.get("limit", 20)
            quadrant = body.get("quadrant")

            if not query:
                return JSONResponse({"error": "Query is required"}, status_code=400)

            query_vector = await self.llm.get_embedding(query)
            results = self.vector_store.search_memories(
                query_vector,
                limit=limit,
                filter_quadrants=[quadrant] if quadrant else None
            )

            memories = []
            for res in results:
                payload = res.payload
                memories.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content_preview": payload.get("content", "")[:200],
                    "quadrants": payload.get("quadrants", ["general"]),
                    "tags": payload.get("tags", []),
                    "type": payload.get("type", "raw"),
                    "importance": payload.get("importance", 0.5),
                    "score": res.score
                })

            return JSONResponse({"query": query, "memories": memories, "count": len(memories)})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_stats(self, request: Request) -> JSONResponse:
        """Get system statistics."""
        try:
            vector_stats = self.vector_store.get_stats()
            graph_stats = self.graph_store.get_stats()
            quadrant_counts = vector_stats.get("by_quadrant", {})
            reflections_count = vector_stats.get("by_type", {}).get("reflection", 0)

            weights = {"W_rel": 0.5, "W_rec": 0.3, "W_imp": 0.2}
            stored_weights = self.graph_store.get_metadata("score_weights")
            if stored_weights:
                try:
                    weights = json.loads(stored_weights) if isinstance(stored_weights, str) else stored_weights
                except: pass

            return JSONResponse({
                "vector": vector_stats,
                "graph": graph_stats,
                "quadrants": quadrant_counts,
                "reflections_count": reflections_count,
                "weights": weights,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_conflicts(self, request: Request) -> JSONResponse:
        """Get memory conflicts."""
        try:
            query_vector = await self.llm.get_embedding("conflict contradiction")
            results = self.vector_store.search_memories(query_vector, limit=100)

            conflicts = []
            for res in results:
                related = self.graph_store.get_related_nodes(res.id, "CONFLICTS_WITH")
                if related:
                    conflicts.append({
                        "id": res.id,
                        "summary": res.payload.get("summary", "Untitled"),
                        "type": res.payload.get("type", "raw"),
                        "conflicts_with": len(related)
                    })
            return JSONResponse({"conflicts": conflicts})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_reflections(self, request: Request) -> JSONResponse:
        """Get synthesized reflections."""
        try:
            query_vector = await self.llm.get_embedding("user patterns preferences")
            results = self.vector_store.search_memories(query_vector, limit=20, filter_quadrants=["general"])

            reflections = []
            for res in results:
                payload = res.payload
                if payload.get("type") == "reflection":
                    reflections.append({
                        "id": res.id,
                        "summary": payload.get("summary", ""),
                        "reflection": payload.get("content", ""),
                        "confidence": payload.get("confidence", "medium"),
                        "pattern_type": payload.get("pattern_type", "preference"),
                        "memory_count": payload.get("memory_count", 0)
                    })
            return JSONResponse({"reflections": reflections})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_weights(self, request: Request) -> JSONResponse:
        """Get current scoring weights."""
        try:
            weights = {"W_rel": 0.5, "W_rec": 0.3, "W_imp": 0.2}
            defaults = weights.copy()
            stored_weights = self.graph_store.get_metadata("score_weights")
            if stored_weights:
                try: weights = json.loads(stored_weights) if isinstance(stored_weights, str) else stored_weights
                except: pass

            deviations = {k: round(weights.get(k, defaults[k]) - defaults[k], 3) for k in defaults.keys()}
            return JSONResponse({"current": weights, "defaults": defaults, "deviations": deviations})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_queue(self, request: Request) -> JSONResponse:
        """Get consolidation queue status."""
        try:
            if not self.queue:
                return JSONResponse({"enabled": False, "message": "Queue not configured"})
            stats = self.queue.get_stats()
            return JSONResponse({
                "enabled": True, "pending": stats.get("pending", 0),
                "processing": stats.get("processing", 0), "completed": stats.get("completed", 0),
                "failed": stats.get("failed", 0), "message": f"{stats.get('pending', 0)} pending"
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_consolidate(self, request: Request) -> JSONResponse:
        """Info about consolidation."""
        return JSONResponse({"success": True, "message": "Consolidation runs automatically every 8 hours"})

    async def handle_api_process_queue(self, request: Request) -> JSONResponse:
        """Return queue processing status."""
        stats = self.queue.get_stats() if self.queue else {}
        return JSONResponse({"success": True, "message": "Queue is processed automatically", "stats": stats})

    async def handle_api_activity(self, request: Request) -> JSONResponse:
        """Get recent LLM activity log."""
        try:
            limit = int(request.query_params.get("limit", 50))
            activities = []
            if self.activity_log_path.exists():
                with open(self.activity_log_path, "r") as f:
                    lines = f.readlines()
                    for line in reversed(lines[-limit:]):
                        try: activities.append(json.loads(line.strip()))
                        except: continue
            return JSONResponse({"activities": activities, "count": len(activities)})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_logs(self, request: Request) -> JSONResponse:
        """Get recent server logs."""
        try:
            lines = int(request.query_params.get("lines", 100))
            level = request.query_params.get("level", "all")
            log_file = self.data_dir / "logs" / "memcore.log"
            log_entries = []

            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                for line in reversed(all_lines[-lines:]):
                    line = line.strip()
                    if not line: continue
                    entry_level = "info"
                    if "error" in line.lower() or "exception" in line.lower(): entry_level = "error"
                    elif "warn" in line.lower(): entry_level = "warn"
                    elif "debug" in line.lower(): entry_level = "debug"
                    
                    if level != "all" and entry_level != level: continue
                    log_entries.append({"level": entry_level, "message": line[:500], "timestamp": datetime.now().isoformat()})

            return JSONResponse({"logs": log_entries[:50], "count": len(log_entries)})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_analytics(self, request: Request) -> JSONResponse:
        """Get detailed analytics."""
        try:
            if not self.analytics: return JSONResponse({"error": "Analytics not available"}, status_code=503)
            stats = await self.analytics.get_detailed_stats()
            return JSONResponse(stats)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_heatmap(self, request: Request) -> JSONResponse:
        """Get activity heatmap data."""
        try:
            if not self.analytics: return JSONResponse({"error": "Analytics not available"}, status_code=503)
            days = int(request.query_params.get("days", 90))
            return JSONResponse(self.analytics.get_activity_heatmap(days))
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_stop(self, request: Request) -> JSONResponse:
        """Stop the server gracefully."""
        async def shutdown():
            await asyncio.sleep(0.5)
            import signal
            os.kill(os.getpid(), signal.SIGTERM)
        asyncio.create_task(shutdown())
        return JSONResponse({"status": "shutting_down", "message": "MemCore server is stopping..."})
