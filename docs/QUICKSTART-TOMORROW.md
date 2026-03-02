# MemCore - Quick Start Guide

## Overview

MemCore is a **standalone agentic memory management system** that runs as a persistent service. Multiple MCP clients (like Kimi CLI, Claude Desktop, etc.) can connect to the same MemCore instance via SSE (Server-Sent Events).

---

## Quick Start (3 Steps)

### Step 1: Configure Environment

Edit `.env` and add your API key:

```bash
# For Kimi (recommended for Chinese/English)
MOONSHOT_API_KEY=sk-your-actual-api-key-here

# Or choose another provider (see README.md for options)
```

Get your key from: https://platform.moonshot.cn/

### Step 2: Verify Configuration

```bash
uv run scripts/verify_config.py
```

Expected output:
```
📋 Selected Provider: kimi
🔤 Embedding Configuration:
   Type: LOCAL (vendor-agnostic)
   Model: local/intfloat/multilingual-e5-large
   Dimension: 1024
   Language Support: ✓ Multilingual (Chinese, English, 100+ languages)
   ✓ Supports Chinese memories and queries
🔑 API Key Status:
  ✓ MOONSHOT_API_KEY: Set
```

### Step 3: Start MemCore Server

#### Option A: Using PowerShell Script (Recommended for Windows)

```powershell
# Simply run the start script
.\start-memcore.ps1

# Or with custom port
.\start-memcore.ps1 -Port 9000

# Run in background
.\start-memcore.ps1 -Background
```

#### Option B: Manual Start

```bash
# Install SSE dependencies (first time only)
uv sync --extra sse

# Start the server
uv run scripts/run_server.py

# Or with custom settings
uv run src/memcore/main.py --mode sse --host 0.0.0.0 --port 9000
```

The server will start at `http://127.0.0.1:8080` by default.

---

## Configure Your MCP Client

Once MemCore is running, configure your MCP client to connect to it.

### For Kimi CLI (`.mcp.json`)

```json
{
  "mcpServers": {
    "memcore": {
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```

### For Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "memcore": {
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```

### Health Check

Verify the server is running:

```bash
curl http://127.0.0.1:8080/health
```

Should return: `OK`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MemCore Standalone                       │
│                     (Single Process)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Gatekeeper │  │   Memory    │  │   Consolidation     │  │
│  │   (Router)   │  │   Tiers     │  │   (Background)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Vector DB  │  │  Graph DB   │  │  Document Watcher   │  │
│  │  (Qdrant)   │  │ (NetworkX)  │  │  (Obsidian Vault)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                         │                                    │
│                    ┌────┴────┐                               │
│                    │ SSE API │ ← Multiple clients connect    │
│                    │:8080   │   here                         │
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

**Key Benefits:**
- **Single instance** serves multiple clients
- **Background consolidation** runs continuously
- **Shared memory** across all clients
- **Document watcher** keeps vault in sync

---

## Available Tools

Once connected, clients can use these MCP tools:

| Tool | Purpose |
|------|---------|
| `mem_query` | Retrieve context and memory based on query |
| `mem_save` | Store a new memory (short-term or long-term) |
| `fetch_detail` | Fetch full details for a specific memory ID |
| `submit_feedback` | Submit feedback on memory retrieval |
| `fetch_source` | Retrieve original source document |

---

## Project Structure

```
MemCore/
├── start-memcore.ps1        # ⭐ PowerShell start script
├── src/memcore/
│   ├── main.py              # Entry point with SSE/stdio modes
│   ├── gatekeeper/
│   │   └── router.py        # Query classification (fast model)
│   ├── memory/
│   │   ├── tiered.py        # L0/L1/L2 context management
│   │   └── consolidation.py # STM → LTM (strong model)
│   ├── storage/
│   │   ├── vector.py        # Qdrant vector store
│   │   └── graph.py         # NetworkX graph store
│   └── utils/
│       ├── llm.py           # LLM interface, embeddings
│       ├── equations.py     # Scoring formulas
│       └── watcher.py       # File system watcher
├── scripts/
│   ├── run_server.py        # SSE server helper
│   ├── run_stdio.py         # Stdio mode helper
│   └── verify_config.py     # Configuration checker
├── docs/
│   └── QUICKSTART-TOMORROW.md  # This file
└── .env                     # Your API keys (gitignored)
```

---

## Key Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| LLM Provider | `kimi` | Best Chinese/English bilingual |
| Fast Model | `moonshot-v1-8k` | Quick tasks, classification |
| Strong Model | `moonshot-v2.5-32k` | Complex extraction |
| Embedding | `multilingual-e5-large` | 1024-dim, 100+ languages |
| Vector DB | Qdrant | Local storage in `data/qdrant_storage` |
| Graph DB | SQLite + NetworkX | Local storage in `data/memcore_graph.db` |
| Default Port | `8080` | Configurable via `--port` |

---

## Testing Chinese Support

```bash
# Test Chinese embeddings
uv run scripts/test_chinese_support.py
```

This will:
1. Download the 2.24GB multilingual embedding model (first time only)
2. Generate embeddings for Chinese text
3. Verify 1024-dim output

---

## Important Design Decisions

### 1. Standalone Service Architecture
- MemCore runs as a **persistent process**
- Multiple MCP clients connect via **SSE transport**
- Background tasks (consolidation, watching) run continuously

### 2. Vendor-Agnostic Embeddings
- All providers use **same local embedding model**
- Switch from Kimi to Bedrock/Gemini **without re-indexing**
- Local embeddings = no API costs for embedding

### 3. Chinese-First Configuration
- Default embedding supports 100+ languages
- Kimi recommended for bilingual chat
- Can store/retrieve memories in Chinese or English

### 4. Model Tiers
- `fast`: Classification, routing (~500ms)
- `strong`: Extraction, consolidation (~2-5s)
- Explicit selection in code (not automatic)

---

## Common Commands

```bash
# Verify setup
uv run scripts/verify_config.py

# Test Chinese embeddings
uv run scripts/test_chinese_support.py

# Start server (SSE mode)
uv run scripts/run_server.py

# Start with custom port
uv run scripts/run_server.py --port 9000

# Stdio mode (for testing)
uv run scripts/run_stdio.py

# Check available embedding models
uv run scripts/check_embedding_models.py
```

---

## PowerShell Script Options

```powershell
# Show help
.\start-memcore.ps1 -Help

# Start with default settings
.\start-memcore.ps1

# Custom port
.\start-memcore.ps1 -Port 9000

# Bind to all interfaces (allow remote connections)
.\start-memcore.ps1 -ListenHost 0.0.0.0

# Run in background (detached)
.\start-memcore.ps1 -Background

# Specify log file
.\start-memcore.ps1 -LogFile "C:\logs\memcore.log"
```

---

## Troubleshooting

### "Connection Refused" Error
- Ensure MemCore server is running: `curl http://127.0.0.1:8080/health`
- Check the port matches in `.mcp.json`
- Verify no firewall blocking the port

### "Invalid Authentication" Error
- Check `MOONSHOT_API_KEY` is set correctly in `.env`
- Verify key is active at https://platform.moonshot.cn/

### Embedding Model Download Slow
- First run downloads 2.24GB model
- Subsequent runs use cached model
- Requires ~4GB RAM

### Dimension Mismatch Error
- **DO NOT CHANGE** embedding model after storing data
- Would require re-indexing entire database
- Choose once at the beginning

### Server Won't Start
- Check port 8080 is not in use: `netstat -ano | findstr 8080`
- Try a different port: `.\start-memcore.ps1 -Port 9000`
- Check logs in `data/logs/` or console output

---

## Documentation References

| Topic | Document |
|-------|----------|
| Embedding selection | `docs/embedding-strategy.md` |
| Chinese support | `docs/multilingual-strategy.md` |
| Model tiers | `docs/model-tier-strategy.md` |
| Architecture | `docs/research-memcore-architecture.md` |
| Core concepts | `docs/core-concepts.md` |
| API specification | `docs/api-specification.md` |

---

## Next Steps

1. ✅ Add API key to `.env`
2. ✅ Run `uv run scripts/verify_config.py`
3. ✅ Start server with `.\start-memcore.ps1`
4. ✅ Configure MCP client to use `http://127.0.0.1:8080/sse`
5. ✅ Test with `mem_query` tool

Happy memory hacking! 🧠🚀
