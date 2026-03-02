# MemCore - Start Here

Quick guide to get MemCore running as a standalone memory service.

## Prerequisites

1. **Python 3.12+** installed
2. **uv** installed (https://github.com/astral-sh/uv)
3. **API Key** from Kimi/Moonshot (https://platform.moonshot.cn/)

## 3-Step Quick Start

### Step 1: Configure

```powershell
# Copy the example environment file
copy .env.example .env

# Edit .env and add your API key
notepad .env
```

Add this line to `.env`:
```
MOONSHOT_API_KEY=sk-your-actual-api-key-here
```

### Step 2: Start MemCore

```powershell
# Start the server
.\start-memcore.ps1

# Or with custom port
.\start-memcore.ps1 -Port 9000
```

You'll see output like:
```
🚀 Starting MemCore server...
   Mode:      SSE (Server-Sent Events)
   Host:      127.0.0.1
   Port:      8080
   Log:       data/logs/memcore.log

Press Ctrl+C to stop the server
```

### Step 3: Configure MCP Client

The `.mcp.json` file is already configured for SSE mode:

```json
{
  "mcpServers": {
    "memcore": {
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```

Your MCP client (Kimi CLI, Claude Desktop, etc.) will now connect to MemCore!

## Verification

Test the server is running:

```powershell
# Health check
curl http://127.0.0.1:8080/health

# Should return: OK
```

## Managing the Server

```powershell
# Start server
.\start-memcore.ps1

# Start in background
.\start-memcore.ps1 -Background

# Stop server
.\stop-memcore.ps1

# Force stop
.\stop-memcore.ps1 -Force

# Show help
.\start-memcore.ps1 -Help
```

## Troubleshooting

### "Port already in use"
```powershell
# Use a different port
.\start-memcore.ps1 -Port 9000
```

### "uv not found"
Install uv from: https://github.com/astral-sh/uv

### "API key not set"
Check your `.env` file has the correct API key.

### Connection refused
Make sure MemCore is running:
```powershell
curl http://127.0.0.1:8080/health
```

## Architecture

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

MemCore runs as a **single persistent process** that serves multiple clients.

## Next Steps

- Read the full guide: `docs/QUICKSTART-TOMORROW.md`
- Learn about architecture: `docs/research-memcore-architecture.md`
- Check API docs: `docs/api-specification.md`

---

Need help? Check the troubleshooting section in `docs/QUICKSTART-TOMORROW.md`
