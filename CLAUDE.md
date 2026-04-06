# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MemCore is a standalone agentic memory management system that serves as a centralized "brain" for AI agents. It runs as a persistent MCP (Model Context Protocol) server exposing memory tools (`mem_query`, `mem_save`, `fetch_detail`, etc.) that multiple clients can connect to via SSE.

## Development Commands

This project uses `uv` as the package manager. Python 3.12+ is required.

```bash
# Install dependencies
uv sync

# Install with SSE server support
uv sync --extra sse

# Verify configuration (tests API keys and embedding model)
uv run scripts/verify_config.py

# Start the server (SSE mode - standalone service)
uv run src/memcore/main.py --mode sse --port 8080
uv run scripts/run_server.py

# Start the server (stdio mode - for client-spawned processes)
uv run src/memcore/main.py --mode stdio
uv run scripts/run_stdio.py

# Windows PowerShell helper scripts
.\start-memcore.ps1          # Start server
.\start-memcore.ps1 -Port 9000   # Custom port
.\stop-memcore.ps1           # Stop server

# Test/verify components
uv run scripts/test_chinese_support.py
uv run scripts/check_embedding_models.py

# Run scenarios (integration tests)
uv run tests/scenario_runner.py
```

## Architecture

### Core Data Flow

The memory lifecycle follows this pipeline:

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Raw Memory  │────▶│ Consolidation    │────▶│ Long-Term Memory    │
│  (type=raw)  │     │ Queue (SQLite)   │     │ (type=consolidated) │
└──────────────┘     └──────────────────┘     └─────────────────────┘
                            │
                            ▼
                     ┌──────────────────┐
                     │ LLM Extraction   │
                     │ - Facts          │
                     │ - Instructions   │
                     └──────────────────┘
```

1. **Ingestion**: `mem_save` stores memories as "raw" with `type=raw` in Qdrant
2. **Queueing**: `consolidate_memories()` (runs every 8h) finds raw memories and queues them
3. **Processing**: `process_consolidation_queue()` (runs every 30min) dequeues and processes jobs
4. **Extraction**: Uses STRONG model tier to extract atomic facts and instructions
5. **Resolution**: Checks for duplicates/conflicts against existing LTM
6. **Storage**: Saves consolidated memories with `type=consolidated` and higher importance

### Tiered Context Disclosure (L0/L1/L2)

The system reveals context in tiers to minimize token costs:

- **L0 (Index)**: High-level summaries returned by `mem_query`. Contains `id`, `summary`, `score`, `type`
- **L1 (Snippet)**: Brief overviews via `tiered_manager.get_l1_context()` - not currently exposed via MCP
- **L2 (Full Detail)**: Raw content retrieved via `fetch_detail(memory_id)` tool only when explicitly requested

### Memory Scoring

The Importance Equation combines three factors:

```python
Score = (W_rel × Relevance) + (W_rec × Recency) + (W_imp × Importance)
```

- **Relevance**: Cosine similarity from Qdrant vector search
- **Recency**: Ebbinghaus forgetting curve `e^(-Δt/strength)` - see `utils/equations.py`
- **Importance**: Intrinsic score (0.0-1.0) assigned during consolidation

The Gatekeeper Router classifies queries into quadrants (coding, personal, research, ai_instructions) and searches both the target quadrant AND `ai_instructions` quadrant (for SOPs).

### Storage Layer

| Component | Technology | Location | Purpose |
|-----------|------------|----------|---------|
| Vector Store | Qdrant (local) | `dataCrystal/qdrant_storage/` | Semantic search, embeddings |
| Graph Store | SQLite | `dataCrystal/memcore_graph.db` | Relationships, request tracking |
| Queue | SQLite | `dataCrystal/consolidation_queue.db` | Stateful job queue |

All storage uses absolute paths derived from `PROJECT_ROOT` in `main.py`.

### Model Tiers

The LLMInterface uses two tiers configured in `utils/llm.py`:

- **fast**: For routing/classification (~500ms) - e.g., `moonshot-v1-8k`, `deepseek-chat`
- **strong**: For extraction/consolidation (~2-5s) - e.g., `moonshot-v2.5-32k`, `deepseek-reasoner`

Embeddings are always local (vendor-agnostic) via `fastembed` using `intfloat/multilingual-e5-large` (1024-dim) by default.

### Background Processes

The `MemCoreAgent` scheduler runs three jobs:

1. **consolidate_memories**: Every 8 hours - queues raw memories for processing
2. **process_consolidation_queue**: Every 30 minutes - processes pending jobs
3. **generate_status_report**: Every 1 hour - updates HTML dashboard

The DocumentWatcher (if `OBSIDIAN_VAULT_PATH` is set) watches for `.md` file changes and auto-reindexes.

## Key Implementation Details

### Consolidation Queue State Machine

Jobs in the queue have statuses: `pending` → `processing` → (`completed`|`failed`|`retrying`)

- On startup, `recover_from_crash()` resets `processing` jobs back to `pending`
- Failed jobs retry up to 3 times before marked as `failed`
- Job history is tracked in `job_history` table for debugging

### Conflict Resolution

When the consolidator finds similar existing memories, it uses the STRONG model to decide:

- **DUPLICATE**: New info already known - link but don't store
- **CONFLICT**: Contradictory info - store both, mark with `CONTRADICTS` edge
- **REFINEMENT**: New info updates existing - merge and update

### MCP Tools

Tools are defined in `MemCoreAgent._setup_mcp_tools()` in `main.py`:

- `mem_query`: Retrieve L0 context, requires `query`, optional `quadrant_hint`
- `mem_save`: Store raw memory, requires `content` and `summary`
- `fetch_detail`: Get L2 full content for a memory ID
- `submit_feedback`: Rate retrieval quality (-1 or +1), triggers RCA on negative
- `fetch_source`: Retrieve original source document (e.g., Obsidian file)
- `mem_stats`: Get system statistics

### Configuration

All configuration is via environment variables in `.env`:

- `LLM_PROVIDER`: `deepseek` (default), `kimi`, `bedrock`, `gemini`, `ollama`
- Provider-specific API keys (e.g., `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`)
- `EMBEDDING_MODEL`: Default is `local/intfloat/multilingual-e5-large` (1024-dim, multilingual)
- `OBSIDIAN_VAULT_PATH`: Optional path to watch for document sync

**Important**: Changing `EMBEDDING_MODEL` after storing data requires re-indexing the entire vector database.
