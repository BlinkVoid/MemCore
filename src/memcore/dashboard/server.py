"""
MemCore Web Dashboard Server

Serves a browser-based management interface for memories.
Uses Starlette for HTTP endpoints alongside the MCP server.
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Optional imports - graceful degradation
try:
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, HTMLResponse, PlainTextResponse
    from starlette.requests import Request
    from starlette.templating import Jinja2Templates
    STARLETTE_AVAILABLE = True
except ImportError:
    STARLETTE_AVAILABLE = False
    Starlette = None
    Route = None
    JSONResponse = None
    HTMLResponse = None
    PlainTextResponse = None
    Request = None
    Jinja2Templates = None

try:
    import uvicorn
    UVICORN_AVAILABLE = True
except ImportError:
    UVICORN_AVAILABLE = False
    uvicorn = None


class DashboardServer:
    """
    Web dashboard for MemCore memory management.

    Provides HTTP endpoints for:
    - Memory browsing and search
    - Memory detail views
    - System statistics
    - Conflict management
    """

    def __init__(
        self,
        vector_store,
        graph_store,
        llm,
        host: str = "127.0.0.1",
        port: int = 8081,
        data_dir: str = None
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm = llm
        self.host = host
        self.port = port
        self.data_dir = Path(data_dir) if data_dir else Path("dataCrystal")

        self.app = self._create_app()
        self.server = None

    def _create_app(self) -> "Starlette":
        """Create the Starlette application."""
        if not STARLETTE_AVAILABLE:
            raise RuntimeError("Starlette is required for the dashboard. Install: uv add starlette")

        routes = [
            Route("/", self.handle_index),
            Route("/api/memories", self.handle_api_memories, methods=["GET"]),
            Route("/api/memories/{memory_id}", self.handle_api_memory_detail, methods=["GET"]),
            Route("/api/memories/{memory_id}", self.handle_api_memory_delete, methods=["DELETE"]),
            Route("/api/search", self.handle_api_search, methods=["POST"]),
            Route("/api/stats", self.handle_api_stats, methods=["GET"]),
            Route("/api/conflicts", self.handle_api_conflicts, methods=["GET"]),
            Route("/api/reflections", self.handle_api_reflections, methods=["GET"]),
            Route("/api/weights", self.handle_api_weights, methods=["GET"]),
        ]

        return Starlette(routes=routes)

    async def handle_index(self, request: "Request") -> "HTMLResponse":
        """Serve the main dashboard HTML."""
        html_content = self._get_dashboard_html()
        return HTMLResponse(content=html_content)

    async def handle_api_memories(self, request: "Request") -> "JSONResponse":
        """Get paginated list of memories."""
        try:
            # Get query params
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

            # Apply offset and type filter
            memories = []
            for res in results[offset:]:
                payload = res.payload

                # Type filter
                if mem_type and payload.get("type") != mem_type:
                    continue

                memories.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content_preview": payload.get("content", "")[:200],
                    "quadrants": payload.get("quadrants", ["general"]),
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

    async def handle_api_memory_detail(self, request: "Request") -> "JSONResponse":
        """Get detailed information about a specific memory."""
        try:
            memory_id = request.path_params["memory_id"]
            result = self.vector_store.get_memory_by_id(memory_id)

            if not result:
                return JSONResponse({"error": "Memory not found"}, status_code=404)

            payload = result[0].payload

            # Get related memories from graph
            related = self.graph_store.get_related_nodes(memory_id, "RELATED_TO")

            memory_data = {
                "id": memory_id,
                "content": payload.get("content", ""),
                "summary": payload.get("summary", ""),
                "quadrants": payload.get("quadrants", ["general"]),
                "type": payload.get("type", "raw"),
                "importance": payload.get("importance", 0.5),
                "confidence": payload.get("confidence", "medium"),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "source_uri": payload.get("source_uri"),
                "tags": payload.get("tags", []),
                "related_count": len(related)
            }

            return JSONResponse(memory_data)

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_memory_delete(self, request: "Request") -> "JSONResponse":
        """Delete a specific memory."""
        try:
            memory_id = request.path_params["memory_id"]

            # Delete from vector store
            self.vector_store.delete_memory(memory_id)

            # Delete from graph store
            self.graph_store.delete_node(memory_id)

            return JSONResponse({"success": True, "deleted": memory_id})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_search(self, request: "Request") -> "JSONResponse":
        """Search memories by query."""
        try:
            body = await request.json()
            query = body.get("query", "")
            limit = body.get("limit", 20)
            quadrant = body.get("quadrant")

            if not query:
                return JSONResponse({"error": "Query is required"}, status_code=400)

            # Generate embedding and search
            query_vector = await self.llm.get_embedding(query)
            filter_quadrants = [quadrant] if quadrant else None

            results = self.vector_store.search_memories(
                query_vector,
                limit=limit,
                filter_quadrants=filter_quadrants
            )

            memories = []
            for res in results:
                payload = res.payload
                memories.append({
                    "id": res.id,
                    "summary": payload.get("summary", "Untitled"),
                    "content_preview": payload.get("content", "")[:200],
                    "quadrants": payload.get("quadrants", ["general"]),
                    "type": payload.get("type", "raw"),
                    "importance": payload.get("importance", 0.5),
                    "score": res.score
                })

            return JSONResponse({
                "query": query,
                "memories": memories,
                "count": len(memories)
            })

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_stats(self, request: "Request") -> "JSONResponse":
        """Get system statistics."""
        try:
            vector_stats = self.vector_store.get_stats()
            graph_stats = self.graph_store.get_stats()

            # Get weight settings
            weights = {"W_rel": 0.5, "W_rec": 0.3, "W_imp": 0.2}
            stored_weights = self.graph_store.get_metadata("score_weights")
            if stored_weights:
                try:
                    weights = json.loads(stored_weights) if isinstance(stored_weights, str) else stored_weights
                except:
                    pass

            return JSONResponse({
                "vector": vector_stats,
                "graph": graph_stats,
                "weights": weights,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_conflicts(self, request: "Request") -> "JSONResponse":
        """Get memory conflicts."""
        try:
            # Search for memories with conflict markers
            query_vector = await self.llm.get_embedding("conflict contradiction")
            results = self.vector_store.search_memories(query_vector, limit=100)

            conflicts = []
            for res in results:
                # Check for CONFLICTS_WITH edges
                related = self.graph_store.get_related_nodes(res.id, "CONFLICTS_WITH")
                if related:
                    payload = res.payload
                    conflicts.append({
                        "id": res.id,
                        "summary": payload.get("summary", "Untitled"),
                        "type": payload.get("type", "raw"),
                        "conflicts_with": len(related)
                    })

            return JSONResponse({"conflicts": conflicts})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_api_reflections(self, request: "Request") -> "JSONResponse":
        """Get synthesized reflections."""
        try:
            query_vector = await self.llm.get_embedding("user patterns preferences")
            results = self.vector_store.search_memories(
                query_vector,
                limit=20,
                filter_quadrants=["general"]
            )

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

    async def handle_api_weights(self, request: "Request") -> "JSONResponse":
        """Get current scoring weights."""
        try:
            weights = {"W_rel": 0.5, "W_rec": 0.3, "W_imp": 0.2}
            defaults = weights.copy()

            stored_weights = self.graph_store.get_metadata("score_weights")
            if stored_weights:
                try:
                    weights = json.loads(stored_weights) if isinstance(stored_weights, str) else stored_weights
                except:
                    pass

            # Calculate deviation
            deviations = {
                k: round(weights.get(k, defaults[k]) - defaults[k], 3)
                for k in defaults.keys()
            }

            return JSONResponse({
                "current": weights,
                "defaults": defaults,
                "deviations": deviations
            })

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    def _get_dashboard_html(self) -> str:
        """Get the dashboard HTML content."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemCore Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 1rem 2rem;
            border-bottom: 1px solid #475569;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 {
            font-size: 1.5rem;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.5rem;
            transition: transform 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            border-color: #60a5fa;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #60a5fa;
        }

        .stat-label {
            font-size: 0.875rem;
            color: #94a3b8;
            margin-top: 0.5rem;
        }

        .panel {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .panel-title {
            font-size: 1.125rem;
            font-weight: 600;
            color: #f1f5f9;
        }

        .search-box {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        .search-box input {
            flex: 1;
            padding: 0.75rem 1rem;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 0.5rem;
            color: #e2e8f0;
            font-size: 0.875rem;
        }

        .search-box input:focus {
            outline: none;
            border-color: #60a5fa;
        }

        .btn {
            padding: 0.75rem 1.25rem;
            background: #3b82f6;
            border: none;
            border-radius: 0.5rem;
            color: white;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        }

        .btn:hover {
            background: #2563eb;
        }

        .btn-secondary {
            background: #475569;
        }

        .btn-secondary:hover {
            background: #64748b;
        }

        .filters {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 0.5rem 1rem;
            background: #334155;
            border: 1px solid #475569;
            border-radius: 0.375rem;
            color: #94a3b8;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .filter-btn:hover, .filter-btn.active {
            background: #3b82f6;
            border-color: #3b82f6;
            color: white;
        }

        .memory-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .memory-item {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            padding: 1rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .memory-item:hover {
            border-color: #60a5fa;
            background: #1e293b;
        }

        .memory-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 0.5rem;
        }

        .memory-title {
            font-weight: 500;
            color: #f1f5f9;
        }

        .memory-type {
            font-size: 0.75rem;
            padding: 0.25rem 0.5rem;
            background: #334155;
            border-radius: 0.25rem;
            color: #94a3b8;
        }

        .memory-type.raw { background: #475569; }
        .memory-type.consolidated { background: #059669; }
        .memory-type.reflection { background: #7c3aed; }

        .memory-preview {
            font-size: 0.875rem;
            color: #94a3b8;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .memory-meta {
            display: flex;
            gap: 1rem;
            margin-top: 0.75rem;
            font-size: 0.75rem;
            color: #64748b;
        }

        .quadrant-tag {
            padding: 0.125rem 0.375rem;
            background: #1e40af;
            border-radius: 0.25rem;
            color: #bfdbfe;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.75);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: #1e293b;
            border: 1px solid #475569;
            border-radius: 0.75rem;
            width: 90%;
            max-width: 800px;
            max-height: 90vh;
            overflow-y: auto;
        }

        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-body {
            padding: 1.5rem;
        }

        .close-btn {
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 1.5rem;
            cursor: pointer;
        }

        .close-btn:hover {
            color: #f1f5f9;
        }

        .loading {
            text-align: center;
            padding: 2rem;
            color: #64748b;
        }

        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #64748b;
        }

        .tabs {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid #334155;
            margin-bottom: 1rem;
        }

        .tab {
            padding: 0.75rem 1.5rem;
            background: none;
            border: none;
            color: #94a3b8;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover {
            color: #e2e8f0;
        }

        .tab.active {
            color: #60a5fa;
            border-bottom-color: #60a5fa;
        }

        .weight-bar {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }

        .weight-label {
            width: 100px;
            font-size: 0.875rem;
            color: #94a3b8;
        }

        .weight-value {
            width: 60px;
            text-align: right;
            font-family: monospace;
            color: #60a5fa;
        }

        .weight-bar-inner {
            flex: 1;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
        }

        .weight-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
            border-radius: 4px;
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>🧠 MemCore Dashboard</h1>
        <div>
            <span id="connection-status">● Connected</span>
        </div>
    </header>

    <div class="container">
        <!-- Stats -->
        <div class="stats-grid" id="stats-container">
            <div class="stat-card">
                <div class="stat-value" id="stat-memories">-</div>
                <div class="stat-label">Total Memories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-nodes">-</div>
                <div class="stat-label">Graph Nodes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-edges">-</div>
                <div class="stat-label">Graph Edges</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-reflections">-</div>
                <div class="stat-label">Reflections</div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('memories')">Memories</button>
            <button class="tab" onclick="switchTab('reflections')">Reflections</button>
            <button class="tab" onclick="switchTab('weights')">Weights</button>
        </div>

        <!-- Memories Panel -->
        <div id="panel-memories" class="panel-content">
            <div class="panel">
                <div class="search-box">
                    <input type="text" id="search-input" placeholder="Search memories..." onkeypress="if(event.key==='Enter') searchMemories()">
                    <button class="btn" onclick="searchMemories()">Search</button>
                </div>

                <div class="filters">
                    <button class="filter-btn active" onclick="filterByType('all')">All</button>
                    <button class="filter-btn" onclick="filterByType('raw')">Raw</button>
                    <button class="filter-btn" onclick="filterByType('consolidated')">Consolidated</button>
                    <button class="filter-btn" onclick="filterByType('reflection')">Reflections</button>
                </div>

                <div class="memory-list" id="memory-list">
                    <div class="loading">Loading memories...</div>
                </div>
            </div>
        </div>

        <!-- Reflections Panel -->
        <div id="panel-reflections" class="panel-content" style="display: none;">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Synthesized Reflections</span>
                </div>
                <div id="reflections-list">
                    <div class="loading">Loading reflections...</div>
                </div>
            </div>
        </div>

        <!-- Weights Panel -->
        <div id="panel-weights" class="panel-content" style="display: none;">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Scoring Weights</span>
                </div>
                <div id="weights-container">
                    <div class="loading">Loading weights...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Memory Detail Modal -->
    <div class="modal" id="memory-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">Memory Detail</h2>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body">
                <!-- Content loaded dynamically -->
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';
        let memories = [];

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadStats();
            loadMemories();
            loadReflections();
            loadWeights();

            // Auto-refresh stats every 30 seconds
            setInterval(loadStats, 30000);
        });

        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                document.getElementById('stat-memories').textContent = data.vector?.total_memories || 0;
                document.getElementById('stat-nodes').textContent = data.graph?.total_nodes || 0;
                document.getElementById('stat-edges').textContent = data.graph?.total_edges || 0;
            } catch (error) {
                console.error('Failed to load stats:', error);
                document.getElementById('connection-status').textContent = '● Disconnected';
                document.getElementById('connection-status').style.color = '#ef4444';
            }
        }

        // Load memories
        async function loadMemories() {
            try {
                const response = await fetch('/api/memories');
                const data = await response.json();
                memories = data.memories || [];
                renderMemories(memories);
            } catch (error) {
                console.error('Failed to load memories:', error);
                document.getElementById('memory-list').innerHTML =
                    '<div class="empty-state">Failed to load memories</div>';
            }
        }

        // Render memories list
        function renderMemories(memoriesToRender) {
            const container = document.getElementById('memory-list');

            if (memoriesToRender.length === 0) {
                container.innerHTML = '<div class="empty-state">No memories found</div>';
                return;
            }

            container.innerHTML = memoriesToRender.map(m => `
                <div class="memory-item" onclick="showMemoryDetail('${m.id}')">
                    <div class="memory-header">
                        <div class="memory-title">${escapeHtml(m.summary)}</div>
                        <span class="memory-type ${m.type}">${m.type}</span>
                    </div>
                    <div class="memory-preview">${escapeHtml(m.content_preview)}</div>
                    <div class="memory-meta">
                        ${m.quadrants.map(q => `<span class="quadrant-tag">${q}</span>`).join('')}
                        <span>Importance: ${(m.importance * 100).toFixed(0)}%</span>
                        <span>Score: ${(m.score * 100).toFixed(1)}%</span>
                    </div>
                </div>
            `).join('');
        }

        // Search memories
        async function searchMemories() {
            const query = document.getElementById('search-input').value.trim();
            if (!query) {
                loadMemories();
                return;
            }

            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, limit: 20 })
                });
                const data = await response.json();
                renderMemories(data.memories || []);
            } catch (error) {
                console.error('Search failed:', error);
            }
        }

        // Filter by type
        function filterByType(type) {
            currentFilter = type;

            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            // Filter memories
            if (type === 'all') {
                renderMemories(memories);
            } else {
                const filtered = memories.filter(m => m.type === type);
                renderMemories(filtered);
            }
        }

        // Show memory detail
        async function showMemoryDetail(id) {
            try {
                const response = await fetch(`/api/memories/${id}`);
                const data = await response.json();

                document.getElementById('modal-title').textContent = data.summary || 'Memory Detail';
                document.getElementById('modal-body').innerHTML = `
                    <div style="margin-bottom: 1rem;">
                        <strong>ID:</strong> <code>${data.id}</code>
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <strong>Type:</strong> <span class="memory-type ${data.type}">${data.type}</span>
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <strong>Quadrants:</strong> ${data.quadrants.map(q =>
                            `<span class="quadrant-tag">${q}</span>`
                        ).join(' ')}
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <strong>Importance:</strong> ${(data.importance * 100).toFixed(0)}%
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <strong>Created:</strong> ${new Date(data.created_at).toLocaleString()}
                    </div>
                    ${data.source_uri ? `
                    <div style="margin-bottom: 1rem;">
                        <strong>Source:</strong> ${data.source_uri}
                    </div>
                    ` : ''}
                    <hr style="border-color: #334155; margin: 1rem 0;">
                    <div style="line-height: 1.6; white-space: pre-wrap;">${escapeHtml(data.content)}</div>
                `;

                document.getElementById('memory-modal').classList.add('active');
            } catch (error) {
                console.error('Failed to load memory detail:', error);
            }
        }

        // Close modal
        function closeModal() {
            document.getElementById('memory-modal').classList.remove('active');
        }

        // Load reflections
        async function loadReflections() {
            try {
                const response = await fetch('/api/reflections');
                const data = await response.json();

                const container = document.getElementById('reflections-list');
                const reflections = data.reflections || [];

                if (reflections.length === 0) {
                    container.innerHTML = '<div class="empty-state">No reflections generated yet</div>';
                    document.getElementById('stat-reflections').textContent = '0';
                    return;
                }

                document.getElementById('stat-reflections').textContent = reflections.length;

                container.innerHTML = reflections.map(r => `
                    <div class="memory-item">
                        <div class="memory-header">
                            <div class="memory-title">${escapeHtml(r.summary)}</div>
                            <span class="memory-type reflection">${r.pattern_type}</span>
                        </div>
                        <div class="memory-preview">${escapeHtml(r.reflection)}</div>
                        <div class="memory-meta">
                            <span>Confidence: ${r.confidence}</span>
                            <span>Based on ${r.memory_count} memories</span>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Failed to load reflections:', error);
            }
        }

        // Load weights
        async function loadWeights() {
            try {
                const response = await fetch('/api/weights');
                const data = await response.json();

                const container = document.getElementById('weights-container');
                const weights = data.current;

                container.innerHTML = `
                    <div style="margin-bottom: 1.5rem;">
                        <p style="color: #94a3b8; margin-bottom: 1rem;">
                            These weights determine how memories are ranked during retrieval.
                            They are automatically adjusted based on feedback.
                        </p>
                    </div>
                    ${Object.entries(weights).map(([key, value]) => `
                        <div class="weight-bar">
                            <div class="weight-label">${key}</div>
                            <div class="weight-bar-inner">
                                <div class="weight-fill" style="width: ${value * 100}%"></div>
                            </div>
                            <div class="weight-value">${value.toFixed(3)}</div>
                        </div>
                    `).join('')}
                    <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #334155;">
                        <p style="color: #64748b; font-size: 0.875rem;">
                            <strong>Relevance (W_rel):</strong> Semantic similarity to query<br>
                            <strong>Recency (W_rec):</strong> How recently accessed<br>
                            <strong>Importance (W_imp):</strong> User-defined importance
                        </p>
                    </div>
                `;
            } catch (error) {
                console.error('Failed to load weights:', error);
            }
        }

        // Switch tabs
        function switchTab(tabName) {
            // Update tab buttons
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');

            // Show/hide panels
            document.querySelectorAll('.panel-content').forEach(panel => {
                panel.style.display = 'none';
            });
            document.getElementById(`panel-${tabName}`).style.display = 'block';

            // Refresh data
            if (tabName === 'reflections') loadReflections();
            if (tabName === 'weights') loadWeights();
        }

        // Utility: Escape HTML
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Close modal on outside click
        document.getElementById('memory-modal').addEventListener('click', (e) => {
            if (e.target.id === 'memory-modal') {
                closeModal();
            }
        });
    </script>
</body>
</html>"""

    async def start(self):
        """Start the dashboard server."""
        if not STARLETTE_AVAILABLE or not UVICORN_AVAILABLE:
            raise RuntimeError(
                "Dashboard requires starlette and uvicorn. Install: uv add starlette uvicorn"
            )

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)

        print(f"MemCore Dashboard running on http://{self.host}:{self.port}")
        await self.server.serve()

    async def stop(self):
        """Stop the dashboard server."""
        if self.server:
            self.server.should_exit = True


def run_dashboard(
    vector_store=None,
    graph_store=None,
    llm=None,
    host: str = "127.0.0.1",
    port: int = 8081,
    data_dir: str = None
):
    """
    Run the dashboard server.

    Usage:
        uv run python -m src.memcore.dashboard
    """
    if not STARLETTE_AVAILABLE:
        print("Error: starlette is required for the dashboard.")
        print("Install with: uv add starlette uvicorn")
        return 1

    if not UVICORN_AVAILABLE:
        print("Error: uvicorn is required for the dashboard.")
        print("Install with: uv add uvicorn")
        return 1

    # Initialize components if not provided
    if not all([vector_store, graph_store, llm]):
        from src.memcore.storage.vector import VectorStore
        from src.memcore.storage.graph import GraphStore
        from src.memcore.utils.llm import LLMInterface

        project_root = Path(__file__).parent.parent.parent.parent
        data_path = Path(data_dir) if data_dir else project_root / "dataCrystal"

        llm = LLMInterface()
        vector_store = VectorStore(
            location=data_path / "qdrant_storage",
            dimension=llm.get_embedding_dimension()
        )
        graph_store = GraphStore(db_path=data_path / "memcore_graph.db")

    server = DashboardServer(
        vector_store=vector_store,
        graph_store=graph_store,
        llm=llm,
        host=host,
        port=port,
        data_dir=data_dir
    )

    try:
        asyncio.run(server.start())
        return 0
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        return 0
    except Exception as e:
        print(f"Dashboard error: {e}")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MemCore Web Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard host")
    parser.add_argument("--port", type=int, default=8081, help="Dashboard port")
    parser.add_argument("--data-dir", help="Data directory path")

    args = parser.parse_args()

    import sys
    sys.exit(run_dashboard(host=args.host, port=args.port, data_dir=args.data_dir))
