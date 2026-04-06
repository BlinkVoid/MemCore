# MemCore Development Log - 2026-03-02

## Overview

This document summarizes the initialization and configuration work completed on March 2, 2026, to prepare MemCore for development with Chinese language support.

---

## 1. Project Initialization

### What Was Done
- Explored existing project structure and documentation
- Initialized Python virtual environment using `uv`
- Installed all dependencies from `pyproject.toml`
- Created `.env` from `.env.example`

### Verification
```bash
uv sync  # Installed 89 packages
# Python 3.12.1 ✓
# uv 0.5.25 ✓
```

### Issue Fixed
- Made `strands_sdk` import optional (package uses different import path `mlp_sdk_v3`)
- System now runs in local-only mode when Strand SDK unavailable

---

## 2. LLM Provider Configuration (Kimi Support)

### What Was Done
- Verified Kimi (Moonshot) API was already configured in model catalogue
- Added API key validation for all providers
- Created verification script to test configuration

### Model Catalogue
```python
"kimi": {
    "fast": "moonshot/moonshot-v1-8k",
    "strong": "moonshot/moonshot-v2-5-32k",
    "embedding": "local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic
}
```

### Files Modified
- `src/memcore/utils/llm.py` - Added `PROVIDER_API_KEYS` validation
- `src/memcore/main.py` - Made Strand SDK import optional
- `scripts/verify_config.py` - Created configuration checker
- `.env.example` - Enhanced documentation

### Environment Variables Required
```bash
LLM_PROVIDER=kimi
MOONSHOT_API_KEY=sk-...
```

---

## 3. Embedding Strategy - Vendor-Agnostic Design

### What Was Done
- Changed default embedding from cloud-based to **local embeddings** to avoid vendor lock-in
- This allows switching between Kimi/Bedrock/Gemini/DeepSeek without re-indexing the vector database

### Why Local Embeddings?

| Benefit | Description |
|---------|-------------|
| No Vendor Lock-in | Switch LLM providers without migrating vector DB |
| Cost Savings | No per-token embedding costs |
| Privacy | Data never leaves machine for embeddings |
| Offline Capability | Works without internet (after model download) |

### Files Modified
- `src/memcore/utils/llm.py` - Local embedding implementation via `fastembed`
- `.env.example` - Documented embedding options
- `docs/embedding-strategy.md` - Created comprehensive guide

---

## 4. Embedding Dimension Upgrade (384 → 768 → 1024)

### Evolution of Decision

#### Initial: 384-dim (BGE-small)
- Size: 67MB
- **Rejected**: Insufficient quality for memory retrieval

#### Phase 2: 768-dim (BGE-base)
- Size: 210MB
- MTEB: 63.5
- **Good balance** but English-only

#### Final: 1024-dim (Multilingual-E5-Large)
- Size: 2.24GB
- MTEB: 62.3
- **Selected**: Supports 100+ languages including Chinese

### Current Default
```python
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
# 1024-dim, 2.24GB, supports Chinese/English/Japanese/etc.
```

### ⚠️ Critical Warning
**Changing embedding model after data storage requires RE-INDEXING the entire vector database!**

Dimension must match - cannot change from 1024-dim to 768-dim without recreating the collection.

### Files Modified
- `src/memcore/utils/llm.py` - Updated `DEFAULT_EMBEDDING_MODEL` and dimension detection
- `.env` - Changed to multilingual default
- `.env.example` - Added detailed language selection guidance
- `docs/embedding-strategy.md` - Documented trade-offs and migration process

---

## 5. Chinese Language Support

### What Was Done
- Set multilingual embedding model as default (`intfloat/multilingual-e5-large`)
- Verified all providers use same embedding model (vendor-agnostic)
- Recommended Kimi for best Chinese/English bilingual chat support

### Configuration for Chinese Users
```bash
# .env
LLM_PROVIDER=kimi
MOONSHOT_API_KEY=your_key_here

# Embedding automatically uses multilingual-e5-large (1024-dim)
# Supports: Chinese, English, Japanese, Korean, and 100+ languages
```

### Model Support Matrix

| Provider | Chinese Chat | Embedding |
|----------|--------------|-----------|
| **Kimi** | ✓ Native bilingual | ✓ Multilingual (local) |
| Bedrock | △ Via Claude | ✓ Multilingual (local) |
| Gemini | ✓ Good support | ✓ Multilingual (local) |
| DeepSeek | ✓ Chinese-optimized | ✓ Multilingual (local) |

### Files Created/Modified
- `docs/multilingual-strategy.md` - Complete multilingual guide
- `scripts/test_chinese_support.py` - Chinese embedding test
- `scripts/verify_config.py` - Shows language support status
- All embedding defaults updated to multilingual

---

## 6. Fast/Strong Model Tier Strategy

### Current Implementation

Model selection is **explicit** based on task complexity, not automatic:

| Tier | Cost | Speed | Used For |
|------|------|-------|----------|
| `fast` | Low | ~500ms | Classification, routing |
| `strong` | Higher | ~2-5s | Extraction, consolidation, RCA |

### Usage in Code
```python
# Router classification (simple)
tier="fast"  # Haiku, Moonshot v1-8k, Gemini Flash

# Memory consolidation (complex)
tier="strong"  # Sonnet, Moonshot v2.5-32k, Gemini Pro
```

### Provider Mapping
```python
kimi:     fast=v1-8k           strong=v2.5-32k
bedrock:  fast=claude-haiku    strong=claude-sonnet
gemini:   fast=gemini-flash    strong=gemini-pro
deepseek: fast=deepseek-chat   strong=deepseek-reasoner
```

### Document
- `docs/model-tier-strategy.md` - Complete tier strategy guide

---

## 7. Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/verify_config.py` | Check configuration, API keys, test connectivity |
| `scripts/check_embedding_models.py` | List available fastembed models |
| `scripts/test_local_embedding.py` | Test embeddings across all providers |
| `scripts/test_chinese_support.py` | Test Chinese text embedding |

---

## 8. Documentation Created

| Document | Content |
|----------|---------|
| `docs/embedding-strategy.md` | Embedding model selection, dimensions, trade-offs |
| `docs/multilingual-strategy.md` | Chinese/multilingual support, model options |
| `docs/model-tier-strategy.md` | Fast vs Strong model usage |
| `docs/development-log-2026-03-02.md` | This document |

---

## 9. Files Modified Summary

### Core Code
- `src/memcore/utils/llm.py` - Embedding defaults, dimension detection, multilingual support
- `src/memcore/main.py` - Optional Strand SDK import

### Configuration
- `.env` - Multilingual embedding default
- `.env.example` - Comprehensive embedding documentation

### Documentation
- `README.md` - Updated with embedding and language notes
- `docs/embedding-strategy.md` - New
- `docs/multilingual-strategy.md` - New
- `docs/model-tier-strategy.md` - New

### Scripts
- `scripts/verify_config.py` - New
- `scripts/check_embedding_models.py` - New
- `scripts/test_local_embedding.py` - New
- `scripts/test_chinese_support.py` - New

---

## 10. Current System State

### Ready for Development
- ✅ Python 3.12 + uv environment
- ✅ All dependencies installed
- ✅ Kimi API configured (needs API key)
- ✅ Multilingual embeddings (1024-dim)
- ✅ Chinese language support enabled
- ✅ Vendor-agnostic design
- ✅ MCP tools configured

### To Start Development Tomorrow

1. **Add your Kimi API key** to `.env`:
```bash
MOONSHOT_API_KEY=sk-your-actual-key
```

2. **Verify configuration**:
```bash
uv run scripts/verify_config.py
```

3. **Test Chinese support**:
```bash
uv run scripts/test_chinese_support.py
```

4. **Run the gatekeeper**:
```bash
uv run src/memcore/main.py
```

---

## Key Decisions Made

1. **Local over Cloud Embeddings** - Avoid vendor lock-in
2. **1024-dim over 768-dim** - Better multilingual support
3. **Multilingual over English-only** - Support Chinese natively
4. **Explicit over Automatic** - Clear tier selection in code
5. **Kimi as Recommended** - Best Chinese/English bilingual support

---

## Next Steps (For Tomorrow)

1. Test with actual Kimi API key
2. Verify Chinese memory storage and retrieval
3. Begin implementing core memory features
4. Consider adding Chinese quadrant aliases (optional)
5. Test MCP integration with Chinese queries

---

*Last updated: 2026-03-02 23:45+11:00*
