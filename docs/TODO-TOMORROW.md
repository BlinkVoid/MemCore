# MemCore Development Log

**Last Updated:** 2026-03-05 (Phase 5 Complete)

---

## ✅ Completed

### Phase 1: Foundation
- [x] Project scaffolding with `uv`
- [x] Core utility equations (Importance/Recency)
- [x] Vector and Graph storage interfaces
- [x] Gatekeeper Router (quadrant classification)
- [x] MCP interface (`mem_query`, `mem_save`, etc.)

### Phase 2: Memory Intelligence (COMPLETE)

#### ✅ Dynamic Relevancy
- **Files Modified:**
  - `src/memcore/storage/graph.py` - Added `get_memory_weights()` for graph-based scoring
  - `src/memcore/memory/tiered.py` - `score_memories()` now accepts `request_id` for dynamic boost
  - `src/memcore/main.py` - Wired up graph store to tiered manager

- **How it works:**
  - Positive feedback (+1) strengthens FULFILLED_BY edge weights
  - `get_memory_weights()` retrieves edge weights for memories
  - Scores are multiplied by weight (0.5x to 2.0x boost range)
  - Shows `[boost: X.XX]` in query results when active

#### ✅ Advanced Tiered Retrieval
- **Files Modified:**
  - `src/memcore/utils/equations.py` - Added `TokenBudget` class and `estimate_tokens()`
  - `src/memcore/memory/tiered.py` - Added `get_progressive_context()` method
  - `src/memcore/main.py` - `mem_query` now uses progressive disclosure, accepts `context_limit` parameter

- **How it works:**
  - L0 (Index): Always included (summaries only, ~minimal tokens)
  - L1 (Snippet): Auto-promoted for high-confidence memories (adds preview)
  - Token budget tracked - stops adding content when limit reached
  - `context_limit` parameter added to `mem_query` tool
  - Response includes suggestion to use `fetch_detail` for L2

#### ✅ Instruction Extraction (NEW)
- **Files Created:**
  - `src/memcore/memory/instructions.py` - Specialized instruction pipeline

- **Features:**
  - **Instruction Types:** constraint, coding_standard, workflow, behavior, preference
  - **Validation:** Checks for action-oriented language, required fields
  - **Classification:** Auto-classifies instruction type based on content
  - **Priority Scoring:** Constraints (1.0) > Standards (0.9) > Workflows (0.85) > Behaviors (0.8) > Preferences (0.6)
  - **Override Tracking:** Detects when new instruction overrides existing one
  - **Specialized Storage:** Instructions stored with type="instruction" for filtering

- **How it works:**
  - Extracted via specialized prompt for action-oriented content
  - Validated against action patterns ("Always", "Never", "Use", "Prefer", etc.)
  - Checks for similar existing instructions before storing
  - Creates OVERRIDES edge in graph when appropriate

### Phase 3: Autonomous Consolidation (COMPLETE)
- [x] **Stateful Queue** - SQLite-backed, survives restarts
- [x] **Fact Synthesis** - LLM-driven deduplication
- [x] **Conflict Resolution** - Hierarchy-based logic

### Other Completed Items
- DeepSeek provider configured and verified working
- Ollama support added
- `dataCrystal/` added to `.gitignore`
- `CLAUDE.md` created for future development

---

## 🚀 Next Steps

### Phase 4: Feedback & Optimization (COMPLETE)
- [x] **Root Cause Analysis:** Implemented structured failure categorization
- [x] **Global Score Adjustment:** Auto-tune weights ($W_{rel}$, $W_{rec}$, $W_{imp}$) based on feedback
- [x] **HTTP Transport:** Switched from SSE to streamable-http transport

### Phase 4 Details

#### ✅ Root Cause Analysis (RCA) Enhancement
- **Files Created:**
  - `src/memcore/memory/feedback_optimizer.py` - Phase 4 optimization system

- **Features:**
  - **Failure Types:** IRRELEVANCE, OBSOLESCENCE, NOISE, WRONG_QUADRANT, RANKING_ERROR, DUPLICATE, UNKNOWN
  - **Structured Analysis:** LLM categorizes failures with confidence scores
  - **Adjustment Suggestions:** Recommends weight changes based on failure type
  - **Feedback History:** Tracks last 1000 feedback records for analysis

- **How it works:**
  - Negative feedback triggers RCA analysis
  - LLM analyzes query, memory, and user reason
  - Categorizes failure and suggests weight adjustment
  - Records feedback with weights-at-time for historical analysis

#### ✅ Global Score Adjustment
- **Files Modified:**
  - `src/memcore/utils/equations.py` - Added `calculate_importance_score_dynamic()`
  - `src/memcore/memory/tiered.py` - Integrated weight provider callback
  - `src/memcore/main.py` - Added FeedbackOptimizer integration

- **Features:**
  - **Default Weights:** W_rel=0.5, W_rec=0.3, W_imp=0.2 (sum to 1.0)
  - **Auto-Adjustment:** ±0.05 per feedback, max ±0.2 deviation from defaults
  - **Weight Persistence:** Stored in graph metadata
  - **Normalization:** Weights automatically normalized to sum to 1.0
  - **New MCP Tool:** `optimization_report` - View statistics and current weights

- **How it works:**
  - High/medium confidence negative feedback triggers adjustment
  - Adjustment type determined by failure category
  - Weights clamped to prevent extreme deviations
  - Report shows 7-day (configurable) statistics

#### ✅ HTTP Transport (NEW)
- **Files Modified:**
  - `src/memcore/main.py` - Refactored to use FastMCP with streamable-http

- **Changes:**
  - **New Transport:** Switched from SSE to `streamable-http` (MCP 1.26+)
  - **Endpoint:** MCP now at `http://127.0.0.1:8080/mcp` (was `/sse`)
  - **Simplified API:** Uses FastMCP decorator-based tool registration
  - **Removed:** Starlette dependency for SSE routes

- **Migration:**
  ```json
  // Old SSE config
  {"mcpServers": {"memcore": {"url": "http://127.0.0.1:8080/sse"}}}

  // New HTTP config
  {"mcpServers": {"memcore": {"url": "http://127.0.0.1:8080/mcp"}}}
  ```

### Phase 3: Autonomous Consolidation (COMPLETE)

#### ✅ Fact Synthesis (Complete)
- **Files Created:**
  - `src/memcore/memory/reflections.py` - Reflection generation and deduplication

- **Features:**
  - **Reflection Generation:** Identifies patterns across 3+ related memories
  - **LLM Clustering:** Groups memories by semantic similarity using LLM
  - **Pattern Types:** preference, behavior, capability, interest
  - **Confidence Scoring:** high/medium/low based on evidence strength
  - **Deduplication Engine:** Semantic duplicate detection, merge suggestions
  - **New MCP Tool:** `fetch_reflections` - Query synthesized insights

- **How it works:**
  - Collects facts from batch of consolidation jobs
  - Clusters related memories by theme
  - Generates insight statement capturing the pattern
  - Stores reflection with links to source memories (DERIVED_FROM edges)
  - Available via `fetch_reflections` tool

#### ✅ Conflict Resolution (Complete)
- **Files Created:**
  - `src/memcore/memory/conflicts.py` - Hierarchy-based conflict resolution

- **Features:**
  - **Priority Hierarchy:** CONSTRAINT (1.0) > EXPLICIT_CORRECTION (0.95) > VERIFIED_FACT (0.9) > RECENT_FACT (0.8) > GENERAL_FACT (0.7) > PREFERENCE (0.6)
  - **Temporal Authority:** Recent facts get boost; old facts decay
  - **Semantic Fallback:** LLM resolves conflicts when priorities are similar
  - **Conflict Tracking:** CONFLICTS_WITH and OVERRIDES edges in graph
  - **New MCP Tool:** `view_conflicts` - View and manage memory conflicts

- **How it works:**
  - Calculates priority scores based on type, confidence, importance, recency
  - Clear priority difference (>0.15): Higher priority wins automatically
  - Similar priorities: LLM semantic analysis decides resolution
  - Records conflict relationships in graph for tracking
  - Marks deferred conflicts for manual review

### Immediate (Pick One)
1. **Phase 4:** Implement Root Cause Analysis and weight auto-tuning
2. **UI Idea:** System tray indicator for MemCore status
3. **Testing:** Run end-to-end tests with all features

---

## 📊 System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Vector DB (Qdrant) | ✅ Ready | `dataCrystal/qdrant_storage` |
| Graph DB (SQLite) | ✅ Ready | `dataCrystal/memcore_graph.db` |
| Consolidation Queue | ✅ Ready | Stateful, crash-resistant |
| LLM Provider | ✅ Working | DeepSeek verified |
| Dynamic Scoring | ✅ Active | Graph weights boost scores |
| Progressive Retrieval | ✅ Active | Token-budgeted L0→L1 |
| Instruction Pipeline | ✅ Active | Types, validation, override tracking |
| Reflection Generation | ✅ Active | Pattern synthesis from memories |
| Conflict Resolution | ✅ Active | Hierarchy-based priority resolution |
| RCA & Auto-Tuning | ✅ Active | Weight adjustment based on feedback |
| MCP Server | ✅ Ready | HTTP transport (/mcp), 11 core tools |
| Skills System | ✅ Ready | 5 user-facing slash commands |
| Task Management | ✅ Ready | Auto-reminders, priority scoring |
| Web Dashboard | ✅ Ready | http://localhost:8081 |

---

## 🚀 Phase 5: Advanced Features (IN PROGRESS)

### 🚧 System Tray App (Partial)
- **Files Created:**
  - `src/memcore/tray/app.py` - System tray application
  - `src/memcore/tray/__init__.py` - Package init
  - `scripts/run_tray.py` - Convenience script

- **Features:**
  - **Visual Status**: Color-coded icon (green=running, red=stopped, yellow=error)
  - **Quick Controls**: Start/Stop server from tray menu
  - **Memory Count**: Displays number of memories in tooltip
  - **Quick Access**: Open dashboard, view reports, view logs
  - **Configuration**: Edit .env file directly

- **Usage:**
  ```bash
  # Install tray dependencies
  uv sync --extra tray

  # Run tray app
  uv run scripts/run_tray.py
  # Or
  uv run memcore-tray
  ```

#### ✅ Memory Import/Export (Complete)
- **Files Created:**
  - `src/memcore/utils/import_export.py` - Export/Import functionality
  - `scripts/export_memories.py` - CLI export tool
  - `scripts/import_memories.py` - CLI import tool

- **Features:**
  - **Export Formats:** JSON (full data), Markdown (Obsidian-compatible), CSV (spreadsheet)
  - **Import Formats:** JSON, Obsidian vault (Markdown files), CSV
  - **Filters:** Export by quadrants or memory types
  - **CLI Tools:** `export_memories.py`, `import_memories.py`
  - **MCP Tools:** `export_memories`, `import_memories`

- **Usage:**
  ```bash
  # Export to JSON
  uv run scripts/export_memories.py --format json --output memories.json

  # Export to Markdown (Obsidian-compatible)
  uv run scripts/export_memories.py --format markdown --output ./memories_md

  # Import from Obsidian vault
  uv run scripts/import_memories.py --format obsidian --input ~/Obsidian/Vault

  # Import from JSON
  uv run scripts/import_memories.py --format json --input memories.json
  ```

#### ✅ Web Dashboard (Complete - Auto-starts with Server)
- **Files Created:**
  - `src/memcore/dashboard/server.py` - Dashboard server
  - `src/memcore/dashboard/__init__.py` - Package init
  - `scripts/run_dashboard.py` - Standalone script (optional)

- **Features:**
  - **Auto-start**: Dashboard starts alongside MCP server on port 8081
  - **Memory Browser**: List view with search and type filtering
  - **Memory Detail**: Modal view with full content
  - **Statistics**: Real-time stats (memories, nodes, edges, reflections)
  - **Reflections View**: Browse synthesized patterns
  - **Weights Visualization**: Visual bar charts of scoring weights
  - **Dark Theme**: Modern dark UI with gradient accents
  - **Auto-refresh**: Stats update every 30 seconds

- **API Endpoints:**
  - `GET /` - Dashboard HTML
  - `GET /api/memories` - List memories
  - `GET /api/memories/{id}` - Memory detail
  - `POST /api/search` - Search memories
  - `GET /api/stats` - System statistics
  - `GET /api/reflections` - List reflections
  - `GET /api/weights` - Current scoring weights

- **Usage:**
  ```bash
  # Install dashboard dependencies
  uv sync --extra dashboard

  # Start server with dashboard (default: dashboard on port 8081)
  uv run src/memcore/main.py --mode http --dashboard-port 8081

  # Custom ports
  uv run src/memcore/main.py --mode http --port 9000 --dashboard-port 9001

  # Disable dashboard
  uv run src/memcore/main.py --mode http --dashboard-port 0
  ```

  Then open http://localhost:8081 in your browser.

### 📋 Planned Features (ALL COMPLETE ✓)

All Phase 5 features have been implemented:

| Feature | Status | File |
|---------|--------|------|
| Advanced Search | ✅ | `src/memcore/memory/advanced_search.py` |
| Memory Backup/Restore | ✅ | `src/memcore/utils/backup.py` |
| Memory Garbage Collection | ✅ | `src/memcore/utils/garbage_collection.py` |
| Memory Analytics | ✅ | `src/memcore/utils/analytics.py` |
| Memory Templates | ✅ | `src/memcore/utils/templates.py` |
| Conflict Resolution UI | ✅ | Already in `src/memcore/memory/conflicts.py` |
| Multi-device Sync | ✅ | `src/memcore/utils/sync.py` |
| **Task Management** | ✅ | `src/memcore/tasks/` |

### 📋 Task Management with AI Reminders (NEW)

MemCore now tracks tasks/todos with intelligent priority-based reminders:

**MCP Tools:**
- `add_task` - Create tasks with priority (critical/high/medium/low/backlog)
- `list_tasks` - View tasks with urgency indicators (🔴🟠🟡)
- `complete_task` - Mark tasks done
- `update_task` - Change priority, due date, or status
- `task_stats` - Overview of your task load

**Features:**
- **Automatic Reminders**: Scheduler checks every 30 minutes for high-priority tasks
- **Urgency Scoring**: Combines priority, due date, and age to surface what matters
- **Context-Aware**: Records your activity type (coding, researching) to avoid interrupting flow
- **Visual Indicators**: 🔴 Critical/overdue, 🟠 High priority, 🟡 Medium, ⚪ Low

**Files:**
- `src/memcore/tasks/task_manager.py` - Task storage and queries
- `src/memcore/tasks/reminder_scheduler.py` - Automatic reminder system

### 📦 Consolidated Knowledge Export (NEW)

AI-generated consolidated knowledge can be exported to `dataCrystal/consolidated/`:

```
dataCrystal/consolidated/
├── .git/                    # Git tracks knowledge evolution
├── coding/
│   ├── python-patterns.md
│   └── api-design.md
├── personal/
├── research/
└── ai_instructions/
```

Each file contains full provenance (sources, timestamps, confidence) and is tracked in git for time-series analysis of knowledge evolution.

Use `/ingest_consolidated` to import from another MemCore's exported knowledge.

---

## 🎯 Architecture: MCP Tools vs Skills

MemCore uses a hybrid architecture to balance AI autonomy with user control:

### MCP Tools (11 core tools - AI uses these automatically)
Used by the AI during conversation to interact with memory and tasks:

| Tool | Purpose |
|------|---------|
| `mem_query` | Retrieve memories based on query |
| `mem_save` | Store new memory |
| `fetch_detail` | Get full memory + source document |
| `search_memories` | Advanced filtered search |
| `mem_stats` | Quick system statistics |
| `list_templates` | Show available templates |
| `add_task` | Create new task with priority |
| `list_tasks` | View tasks with urgency indicators |
| `complete_task` | Mark task as done |
| `update_task` | Change task priority/due date |
| `task_stats` | Task system overview |

### Skills (5 skills - User explicitly invokes)
User-facing slash commands for admin/reporting tasks:

| Skill | Purpose | Location |
|-------|---------|----------|
| `/feedback` | Submit feedback on memory quality | `src/memcore/skills/feedback_skill.py` |
| `/vault_sync` | Manual vault rescan (`force` subcommand) | `src/memcore/skills/vault_sync_skill.py` |
| `/consolidate_export` | Export AI knowledge to `dataCrystal/consolidated/` with git tracking | `src/memcore/skills/consolidate_export_skill.py` |
| `/recategorize` | Move memory between quadrants | `src/memcore/skills/recategorize_skill.py` |
| `/ingest_consolidated` | Import from another MemCore's dataCrystal | `src/memcore/skills/ingest_consolidated_skill.py` |

### Why This Split?

**MCP Tools (11):**
- Core memory I/O + task management
- AI uses automatically during conversation
- Focused on high-frequency operations

**Skills (5):**
- Rich interactive output
- User controls when to run admin tasks
- Don't clutter AI tool selection
- Can have subcommands (`/vault_sync force`)

---

## 🔧 Quick Commands

```bash
# Start server (with dashboard on port 8081)
.\start-memcore.ps1

# Or manually with custom ports
uv run src/memcore/main.py --mode http --port 8080 --dashboard-port 8081

# Run system tray app (Windows)
uv run scripts/run_tray.py

# Export memories
uv run scripts/export_memories.py --format json --output memories.json

# Import memories
uv run scripts/import_memories.py --format obsidian --input ~/Obsidian/Vault

# Check status
curl http://127.0.0.1:8080/health
start http://127.0.0.1:8080/status

# Verify config
uv run scripts/verify_config.py
```

## ⚠️ Ongoing Debugging & Technical Challenges

The following issues have been identified during the Phase 5/6 transition and are the primary focus of the current architectural redesign:

### 1. Dual-Server Conflict (MCP vs. Dashboard)
- **Problem**: `FastMCP.run()` is a synchronous, blocking call that spawns its own Uvicorn instance. Attempting to run a second Uvicorn/Starlette instance for the Dashboard in a separate thread (via `threading.Thread` or `asyncio.to_thread`) causes event loop deadlocks and port binding race conditions.
- **Symptom**: Ports 8080/8081 appearing "closed" even when the process is running, or 404 errors on valid routes.
- **Solution**: Re-architecting to a **Unified Server**. Use FastMCP only for tool registration, then extract its internal `.app` (Starlette) and attach Dashboard routes directly to it. Run everything under a single Uvicorn instance on port 8080.

### 2. Qdrant Storage Locking
- **Problem**: Qdrant's local storage mode enforces a strict single-process lock. If `VectorStore` is initialized more than once (e.g., once in the main agent and once in a separate dashboard thread), it throws `RuntimeError: Storage folder ... is already accessed`.
- **Symptom**: Startup crashes with "Permission Denied" or "Already accessed" errors.
- **Solution**: Initialize `VectorStore` exactly once at the top level and pass the instance explicitly to all sub-components.

### 3. FastEmbed Initialization Hangs
- **Problem**: The `TextEmbedding` library is heavy and synchronous during model loading. If initialized lazily inside an async retrieval task, it can hang the entire event loop.
- **Symptom**: The server starts, but the first search or save operation hangs indefinitely.
- **Solution**: Moved initialization to `LLMInterface.__init__` (eager loading) and forced `providers=["CPUExecutionProvider"]` to avoid GPU discovery overhead.

### 4. Zombie Process Management
- **Problem**: Windows doesn't always clean up child processes if the parent CLI is killed. Lingering `python.exe` instances hold the Qdrant lock file (`.lock`).
- **Symptom**: New code changes don't seem to take effect because the new process crashes immediately on the DB lock, while an old "zombie" process continues to respond (or hang) on the port.
- **Action**: Use `taskkill` or `Stop-Process` to ensure a totally clean environment before every restart.

## 🛠️ Redesign Progress (March 5, 2026)

- [x] Create `DashboardRouter` to replace standalone `DashboardServer`.
- [x] Rewrite `main.py` to use a single unified Starlette app.
- [x] Fix `VectorStore.get_stats()` indentation and missing method errors.
- [x] Eagerly initialize `fastembed` in the main thread.
- [ ] **Next Step**: Verify unified port 8080 handles both MCP JSON-RPC and Dashboard HTML.
