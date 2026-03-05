# MemCore: Agentic Memory Management System

**MemCore** is a centralized "brain" for AI agents, providing tiered context retrieval, memory consolidation, and relationship mapping through the Model Context Protocol (MCP).

## Project Overview

- **Core Mission**: Provide a persistent, searchable, and self-organizing memory layer for AI agents.
- **Architecture**:
    - **Gatekeeper**: Routes queries and classifies them into quadrants (coding, personal, research, ai_instructions).
    - **Tiered Context**: Implements progressive disclosure (L0: Index, L1: Snippet, L2: Full Detail) to optimize token usage.
    - **Storage**: Hybrid system using **Qdrant** (Vector Store) for semantic search and **SQLite** (Graph Store) for relationships and metadata.
    - **Consolidation**: Background process (every 8h) that promotes short-term memories (STM) to long-term facts (LTM).
    - **Transport**: Supports both **SSE (Server-Sent Events)** for standalone service mode and **Stdio** for client-spawned mode.

## Core Technologies

- **Language**: Python 3.12+
- **Package Manager**: `uv` (Fastest performance, uses `uv.lock`)
- **MCP Framework**: `mcp` (FastMCP implementation in `main.py`)
- **LLM Abstraction**: `litellm` (Supports Kimi, Bedrock, Gemini, DeepSeek)
- **Vector DB**: `qdrant-client` (Local storage in `dataCrystal/qdrant_storage`)
- **Graph DB**: `sqlite3` / `networkx` (Local file `dataCrystal/memcore_graph.db`)
- **Embeddings**: `fastembed` (Local execution by default)
- **SDK**: `strands-sdk` (Optional agentic monitoring)

## Build and Run Commands

### Development Setup
```powershell
# Install dependencies
uv sync --all-extras

# Verify configuration
uv run scripts/verify_config.py
```

### Running the Server
```powershell
# Recommended: Standalone SSE Server
.\start-memcore.ps1

# Stdio Mode (for direct client spawning)
uv run src/memcore/main.py --mode stdio
```

### Management
```powershell
# Stop the server
.\stop-memcore.ps1

# Run tests
uv run tests/scenario_runner.py
```

## Development Conventions

### 1. Memory Quadrants
All memories belong to one of four quadrants. Always specify or infer these:
- `coding`: Software development, logic, architecture.
- `personal`: User preferences, identity, history.
- `research`: Facts, external data, documentation.
- `ai_instructions`: System prompts, SOPs, agent behaviors.

### 2. LLM Model Tiers
The system distinguishes between model strengths to balance cost and performance:
- **Fast Tier**: Used for routing, classification, and simple summaries (e.g., `gemini-2.0-flash`).
- **Strong Tier**: Used for consolidation, conflict resolution, and complex reasoning (e.g., `gemini-2.0-pro`).

### 3. File Structure & Data Paths
- **Source**: All logic resides in `src/memcore/`.
- **Data**: Persistent data is stored in `dataCrystal/`. **Never commit files in this directory.**
- **Scripts**: Maintenance and testing utilities are in `scripts/`.

### 4. Coding Standards
- **Async First**: Use `async/await` for all I/O, storage, and LLM operations.
- **Type Hinting**: Mandatory for all function signatures and class members.
- **Absolute Imports**: Always use `from src.memcore...` rather than relative imports.
- **FastMCP**: Use the decorator-based tool definition in `main.py` for new MCP tools.

## Key Files

- `src/memcore/main.py`: The central orchestrator and MCP server entry point.
- `src/memcore/memory/tiered.py`: Logic for L0/L1/L2 scoring and disclosure.
- `src/memcore/memory/consolidation.py`: Pipeline for memory synthesis and LTM promotion.
- `src/memcore/storage/vector.py`: Qdrant interface for semantic retrieval.
- `src/memcore/storage/graph.py`: SQLite interface for relationship and metadata management.
- `src/memcore/utils/llm.py`: Unified interface for LLM provider switching.

## Documentation References

- **API Tools**: `docs/api-specification.md`
- **Architecture**: `docs/research-memcore-architecture.md`
- **Math/Scoring**: `docs/core-concepts.md`
- **Agent Guide**: `AGENTS.md` (Detailed technical manual for AI assistants)
