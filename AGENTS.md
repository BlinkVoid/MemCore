# MemCore - Agentic Memory Management System

> **For AI Coding Agents:** This document provides essential context for working with the MemCore codebase. Read this before making any changes.

## Project Overview

**MemCore** is a standalone, agentic memory management system designed to serve as a centralized "brain" for AI agents across multiple systems and tools. It implements:

- **Tiered Context Disclosure**: L0 (Index), L1 (Snippet), L2 (Full Detail) retrieval to minimize noise and token costs
- **Agentic Gatekeeping**: A watched process using Strand SDK that manages memory lifecycle, consolidation, and conflict resolution
- **Dynamic Scoring**: Multi-factor retrieval based on Relevance, Recency (Ebbinghaus curve), and Importance
- **Memory Consolidation**: Periodic background processing to convert short-term interactions into long-term facts and SOPs
- **MCP Native**: Exposes capabilities via the Model Context Protocol for seamless integration with any MCP-compatible client

### Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MemCore (Port 8080)                       │
│                    Standalone Service                        │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐   │
│  │ Vector DB  │  │ Graph DB   │  │ Document Watcher     │   │
│  │ (Qdrant)   │  │ (SQLite)   │  │ (Obsidian)           │   │
│  └────────────┘  └────────────┘  └──────────────────────┘   │
│                         │                                    │
│                    ┌────┴────┐                               │
│                    │ SSE API │ ← MCP clients connect here    │
│                    └────┬────┘                               │
└─────────────────────────┼───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼─────┐   ┌────▼────┐   ┌──────▼──────┐
    │ Kimi CLI  │   │ Claude  │   │  Other MCP  │
    │           │   │ Desktop │   │   Clients   │
    └───────────┘   └─────────┘   └─────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.12+ | Core runtime |
| Package Manager | `uv` | Fast Python package management |
| Vector DB | Qdrant | Vector storage for memory embeddings |
| Graph DB | SQLite | Relationship tracking between memories |
| LLM Interface | LiteLLM | Unified interface for multiple LLM providers |
| Local Embeddings | FastEmbed | Vendor-agnostic embedding generation |
| MCP Server | `mcp` library | Model Context Protocol implementation |
| Task Scheduling | APScheduler | Background consolidation jobs |
| File Watching | Watchdog | Obsidian vault synchronization |
| Web Framework | Starlette + Uvicorn | SSE transport mode |
| Optional SDK | Strand SDK | Watched process management |

## Project Structure

```
memcore/
├── src/memcore/                  # Main source code
│   ├── __init__.py
│   ├── main.py                   # Entry point, MemCoreAgent class
│   ├── gatekeeper/               # Request routing and classification
│   │   ├── router.py             # Quadrant classification (coding, personal, etc.)
│   │   └── __init__.py
│   ├── memory/                   # Memory management
│   │   ├── tiered.py             # L0/L1/L2 context disclosure
│   │   ├── consolidation.py      # STM to LTM pipeline
│   │   └── __init__.py
│   ├── storage/                  # Data persistence
│   │   ├── vector.py             # Qdrant vector store wrapper
│   │   ├── graph.py              # SQLite graph store
│   │   └── __init__.py
│   └── utils/                    # Utilities
│       ├── llm.py                # LLM interface via LiteLLM
│       ├── equations.py          # Importance/Recency scoring math
│       ├── watcher.py            # File system watcher for Obsidian
│       ├── reporter.py           # HTML status report generation
│       └── __init__.py
├── scripts/                      # Utility scripts
│   ├── verify_config.py          # Configuration validation
│   ├── run_server.py             # Server runner helper
│   ├── run_stdio.py              # Stdio mode runner
│   ├── test_chinese_support.py   # Chinese language testing
│   ├── test_local_embedding.py   # Embedding model testing
│   └── check_embedding_models.py # Model availability check
├── tests/                        # Test suite
│   └── scenario_runner.py        # Integration test scenarios
├── docs/                         # Documentation
│   ├── core-concepts.md          # Mathematical models and concepts
│   ├── api-specification.md      # MCP tool specifications
│   ├── research-memcore-architecture.md  # Architecture details
│   ├── embedding-strategy.md     # Embedding model selection guide
│   ├── multilingual-strategy.md  # Language support documentation
│   └── QUICKSTART-TOMORROW.md    # Resume development guide
├── dataCrystal/                  # Data storage (gitignored)
│   ├── qdrant_storage/           # Vector database files
│   ├── memcore_graph.db          # SQLite graph database
│   ├── logs/                     # Server logs
│   └── reports/                  # HTML status reports
├── pyproject.toml                # Python dependencies
├── .env.example                  # Environment template
├── .mcp.json                     # MCP client configuration
├── start-memcore.ps1             # PowerShell start script
├── stop-memcore.ps1              # PowerShell stop script
└── README.md                     # User-facing documentation
```

## Build and Run Commands

### Prerequisites
- Python 3.12+
- `uv` package manager (https://github.com/astral-sh/uv)
- API key for at least one LLM provider

### Setup
```bash
# Install dependencies
uv sync

# For SSE server mode
uv sync --extra sse

# Configure environment
copy .env.example .env
# Edit .env with your API keys
```

### Running the Server

**SSE Mode (Recommended - Standalone Service):**
```powershell
# Using PowerShell script
.\start-memcore.ps1

# Custom port
.\start-memcore.ps1 -Port 9000

# Background mode
.\start-memcore.ps1 -Background

# Using Python directly
uv run src/memcore/main.py --mode sse --host 127.0.0.1 --port 8080
```

**Stdio Mode (Client-Spawned):**
```bash
uv run src/memcore/main.py --mode stdio
```

### Verification
```bash
# Check configuration
uv run scripts/verify_config.py

# Health check (when server is running)
curl http://127.0.0.1:8080/health
```

### Stopping the Server
```powershell
.\stop-memcore.ps1
# Or force stop
.\stop-memcore.ps1 -Force
```

## Code Style Guidelines

### Python Style
- Follow PEP 8
- Use type hints for function signatures
- Use async/await for I/O operations
- Document classes and public methods with docstrings

### Import Pattern
```python
# Standard library
import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Third-party
from mcp.server import Server
import mcp.types as types

# Local modules (use absolute imports from src)
from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
```

### Key Conventions
1. **LLM Tiers**: Use `"fast"` for routing/classification, `"strong"` for consolidation/complex tasks
2. **Memory Types**: `"raw"` (new), `"consolidated"` (processed), `"archived_raw"` (post-consolidation)
3. **Quadrants**: `"coding"`, `"personal"`, `"research"`, `"ai_instructions"`
4. **Error Handling**: Log errors, return gracefully - don't crash the agent

## MCP Tools Reference

MemCore exposes these MCP tools:

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `mem_query` | Retrieve context based on query | `query`, `quadrant_hint` (optional) |
| `mem_save` | Store a new memory | `content`, `summary`, `quadrants`, `metadata` |
| `fetch_detail` | Get L2 full details for a memory | `memory_id` |
| `submit_feedback` | Rate retrieval quality | `request_id`, `memory_id`, `rating` (1/-1) |
| `fetch_source` | Get original source document | `memory_id` |
| `mem_stats` | Get system statistics | (none) |

## Testing

### Running Tests
```bash
# Run integration scenarios
uv run tests/scenario_runner.py

# Test specific components
uv run scripts/test_local_embedding.py
uv run scripts/test_chinese_support.py
```

### Test Scenarios
The `scenario_runner.py` includes:
- **Scenario A**: Coding knowledge transfer
- **Scenario B**: Identity conflict resolution
- **Scenario C**: Feedback loop & RCA
- **Scenario D**: Document synchronization

## Configuration

### Environment Variables (`.env`)

**Required:**
```bash
LLM_PROVIDER=kimi  # bedrock, gemini, kimi, deepseek
MOONSHOT_API_KEY=your_key_here  # Provider-specific
```

**Embedding Model (IMPORTANT - changing requires re-indexing):**
```bash
# Default: Multilingual (Chinese, English, 100+ languages)
EMBEDDING_MODEL=local/intfloat/multilingual-e5-large  # 1024-dim, ~4GB RAM

# Alternative: English-only, smaller footprint
# EMBEDDING_MODEL=local/BAAI/bge-base-en-v1.5  # 768-dim, 210MB
```

**Optional:**
```bash
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
STRANDS_API_KEY=your_strands_platform_key  # For cloud features
```

### LLM Provider Support

| Provider | Fast Model | Strong Model | Notes |
|----------|------------|--------------|-------|
| Kimi | moonshot-v1-8k | moonshot-v2-5-32k | Recommended for Chinese/English |
| AWS Bedrock | Claude 3.5 Haiku | Claude 3.5 Sonnet | Enterprise AWS users |
| Google Gemini | gemini-2.0-flash | gemini-2.0-pro | Google Cloud users |
| DeepSeek | deepseek-chat | deepseek-reasoner | Cost-effective |

## Memory Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Raw STM   │────▶│ Consolidation│────▶│   LTM Store  │
│  (New Data) │     │  (Every 8h)  │     │(Vector/Graph)│
└─────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Actions:   │
                    │ • Extract    │
                    │ • Deduplicate│
                    │ • Resolve    │
                    │ • Score      │
                    └──────────────┘
```

## Tiered Context Disclosure

| Level | Content | When Used |
|-------|---------|-----------|
| **L0** | Index/Summary | Initial query - "what do I know about X?" |
| **L1** | Snippet/Overview | Relevance confirmed - brief summaries |
| **L2** | Full Detail | Explicitly requested via `fetch_detail` |

## The Importance Equation

Memories are scored using:

```
Score = (W_rel × Relevance) + (W_rec × Recency) + (W_imp × Importance)
```

Where:
- **Relevance**: Cosine similarity of embeddings
- **Recency**: `e^(-Δt/S)` (Ebbinghaus Forgetting Curve)
- **Importance**: 0.0-1.0 assigned during consolidation

## Security Considerations

1. **API Keys**: Stored in `.env` (never commit this file)
2. **Data Storage**: All data is local (Qdrant files + SQLite)
3. **Network**: Default binds to `127.0.0.1` (localhost only)
4. **Embeddings**: Uses local models by default (no data sent to cloud for embeddings)

## Common Development Tasks

### Adding a New MCP Tool
1. Add tool definition in `src/memcore/main.py` `_setup_mcp_tools()` -> `list_tools()`
2. Add handler in `call_tool()` method
3. Implement handler method (e.g., `handle_<tool_name>()`)

### Adding a New LLM Provider
1. Add entry to `MODEL_CATALOGUE` in `src/memcore/utils/llm.py`
2. Add API key requirements to `PROVIDER_API_KEYS`
3. Test with `uv run scripts/verify_config.py`

### Modifying Memory Scoring
1. Update equations in `src/memcore/utils/equations.py`
2. Adjust usage in `src/memcore/memory/tiered.py` -> `score_memories()`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port already in use | Use `-Port 9000` or check `stop-memcore.ps1` |
| Embedding dimension mismatch | Delete `dataCrystal/qdrant_storage` and restart |
| API errors | Run `uv run scripts/verify_config.py` |
| Chinese text not working | Ensure using multilingual embedding model |
| Slow consolidation | Normal - uses strong model, runs every 8 hours |

## Documentation References

- **API Spec**: `docs/api-specification.md`
- **Core Concepts**: `docs/core-concepts.md`
- **Architecture**: `docs/research-memcore-architecture.md`
- **Embedding Strategy**: `docs/embedding-strategy.md`
- **Multilingual Support**: `docs/multilingual-strategy.md`
- **Quick Resume**: `docs/QUICKSTART-TOMORROW.md`

## Data Flow Summary

```
MCP Client → MCP Server → Router (classification) → Vector Search → 
Tiered Manager (scoring) → Response + Graph Update → (Background) Consolidation
```

---

**Last Updated**: This document should be updated when:
- New MCP tools are added
- Architecture changes significantly
- New LLM providers are supported
- Build/deployment processes change
