# MemCore - Quick Start Guide for Tomorrow

## What Was Done Today (2026-03-02)

Initialized MemCore project with full Chinese language support and vendor-agnostic embedding design.

---

## 1-Minute Setup

### Step 1: Add Your API Key

Edit `.env` and add your Kimi API key:

```bash
MOONSHOT_API_KEY=sk-your-actual-api-key-here
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

### Step 3: Run the System

```bash
uv run src/memcore/main.py
```

---

## Key Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| LLM Provider | `kimi` | Best Chinese/English bilingual |
| Fast Model | `moonshot-v1-8k` | Quick tasks, classification |
| Strong Model | `moonshot-v2.5-32k` | Complex extraction |
| Embedding | `multilingual-e5-large` | 1024-dim, 100+ languages |
| Vector DB | Qdrant | Local storage |

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

## Project Structure

```
MemCore/
├── src/memcore/
│   ├── main.py              # Entry point, MCP server
│   ├── gatekeeper/
│   │   └── router.py        # Query classification (fast model)
│   ├── memory/
│   │   ├── tiered.py        # L0/L1/L2 context management
│   │   └── consolidation.py # STM → LTM (strong model)
│   ├── storage/
│   │   ├── vector.py        # Qdrant vector store
│   │   └── graph.py         # NetworkX graph store
│   └── utils/
│       ├── llm.py           # LLM interface, embedding model config
│       ├── equations.py     # Scoring formulas
│       └── watcher.py       # File system watcher
├── docs/
│   ├── development-log-2026-03-02.md  # Today's work
│   ├── embedding-strategy.md          # Embedding guide
│   ├── multilingual-strategy.md       # Chinese support
│   ├── model-tier-strategy.md         # Fast/Strong usage
│   └── QUICKSTART-TOMORROW.md         # This file
├── scripts/
│   ├── verify_config.py     # Configuration checker
│   └── test_*.py            # Various tests
└── .env                     # Your API keys (gitignored)
```

---

## Important Design Decisions

### 1. Vendor-Agnostic Embeddings
- All providers use **same local embedding model**
- Switch from Kimi to Bedrock/Gemini **without re-indexing**
- Local embeddings = no API costs for embedding

### 2. Chinese-First Configuration
- Default embedding supports 100+ languages
- Kimi recommended for bilingual chat
- Can store/retrieve memories in Chinese or English

### 3. Model Tiers
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

# Run gatekeeper
uv run src/memcore/main.py

# Check available embedding models
uv run scripts/check_embedding_models.py

# List installed packages
uv pip list
```

---

## Troubleshooting

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

---

## Documentation References

| Topic | Document |
|-------|----------|
| Today's changes | `docs/development-log-2026-03-02.md` |
| Embedding selection | `docs/embedding-strategy.md` |
| Chinese support | `docs/multilingual-strategy.md` |
| Model tiers | `docs/model-tier-strategy.md` |
| Architecture | `docs/research-memcore-architecture.md` |
| Core concepts | `docs/core-concepts.md` |

---

## Ready to Start

1. ✅ Environment configured
2. ✅ Dependencies installed
3. ✅ Chinese support enabled
4. ✅ Vendor-agnostic design
5. ⏳ Waiting for your API key

See you tomorrow! 🚀
