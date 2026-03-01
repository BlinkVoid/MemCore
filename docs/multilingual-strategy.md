# MemCore Multilingual Strategy

## Current State

### Embedding Model (Updated)
- **Current**: `intfloat/multilingual-e5-large` (Multilingual, 1024-dim, 2.24GB)
- **Supports**: 100+ languages including Chinese, Japanese, Korean (CJK)
- **Alternative**: `BAAI/bge-base-en-v1.5` (English-only, 768-dim, 210MB) for smaller footprint

### Chat Models
- **Kimi**: Native Chinese/English bilingual ✓
- **Bedrock Claude**: Multilingual but English-centric
- **Gemini**: Good multilingual support ✓
- **DeepSeek**: Chinese-optimized ✓

## The Problem

```python
# User stores Chinese memory
memory = "用户喜欢喝绿茶，不喜欢咖啡"

# BGE-en embedding struggles with semantic capture
embedding = await llm.get_embedding(memory)  # Poor vector representation!

# Later retrieval fails
query = "用户喜欢什么饮料？"
results = vector_store.search(query)  # Low relevance scores
```

## Solution Options

### Option 1: Multilingual Embedding Model (Recommended)

Replace `bge-base-en-v1.5` with a multilingual model:

| Model | Dim | Size | Languages | MTEB Avg |
|-------|-----|------|-----------|----------|
| `BAAI/bge-m3` | 1024 | 2.2GB | 100+ | 64.5 |
| `intfloat/multilingual-e5-large` | 1024 | 2.2GB | 100+ | 62.3 |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 420MB | 50+ | 48.2 |

**Recommendation**: `BAAI/bge-m3` or `intfloat/multilingual-e5-large`

**Trade-offs**:
- ✅ Handles English + Chinese equally well
- ✅ Single model for all languages
- ✅ No language detection needed
- ❌ Larger size (2.2GB vs 210MB)
- ❌ Slightly slower inference
- ❌ Changing requires re-indexing!

### Option 2: Language-Aware Routing

```python
class MultilingualEmbedder:
    def __init__(self):
        self.en_embedder = TextEmbedding("BAAI/bge-base-en-v1.5")
        self.zh_embedder = TextEmbedding("BAAI/bge-large-zh-v1.5")  # 1024-dim
        
    async def get_embedding(self, text: str) -> List[float]:
        lang = detect_language(text)  # fasttext-langdetect
        if lang == "zh":
            return self._embed_zh(text)
        else:
            return self._embed_en(text)
```

**Trade-offs**:
- ✅ Optimized per-language models
- ✅ Smaller individual models
- ❌ Complex architecture
- ❌ Different dimensions need projection layer
- ❌ Language detection adds latency

### Option 3: Unicode-Aware Universal Model

Use models specifically designed for multilingual:

```python
# Default to multilingual model
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"  # or "intfloat/multilingual-e5-large"
```

## Recommendation: Upgrade to BGE-M3

For a memory system that should handle Chinese:

```python
# src/memcore/utils/llm.py
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"  # 1024-dim, 2.2GB
```

### Why BGE-M3?

1. **State-of-the-art**: Best multilingual retrieval (MTEB: 64.5)
2. **Dense + Sparse**: Supports hybrid retrieval
3. **100+ languages**: Covers virtually all use cases
4. **Matryoshka representation**: Can truncate to 768-dim if needed

### Migration Considerations

| Aspect | bge-base-en (768-dim) | bge-m3 (1024-dim) |
|--------|----------------------|-------------------|
| **Size** | 210MB | 2.2GB |
| **Dimension** | 768 | 1024 |
| **English MTEB** | 63.5 | 64.5 |
| **Chinese MTEB** | ~45 (poor) | 63.0 (excellent) |
| **RAM** | ~500MB | ~3GB |

**Decision required before first run!**

## Implementation Plan

### Phase 1: Make Embedding Model Configurable (Done)
Already supported via `EMBEDDING_MODEL` env var.

### Phase 2: Document Language Support

```bash
# .env.example - Language-aware configuration

# English-only deployment (smaller, faster)
EMBEDDING_MODEL=local/BAAI/bge-base-en-v1.5  # 768-dim, 210MB

# Multilingual deployment (Chinese, Japanese, etc.)
EMBEDDING_MODEL=local/BAAI/bge-m3  # 1024-dim, 2.2GB
```

### Phase 3: Add Language Detection (Optional)

```python
# For analytics/debugging
from langdetect import detect

def get_memory_language(text: str) -> str:
    """Detect primary language of memory content."""
    try:
        return detect(text[:1000])  # Sample first 1000 chars
    except:
        return "unknown"
```

### Phase 4: Quadrant Localization

Current quadrants are English-centric:
```python
quadrants = ["coding", "personal", "research", "ai_instructions"]
```

Could support localized quadrant names:
```python
QUADRANT_ALIASES = {
    "coding": ["coding", "编程", "コード", "開発"],
    "personal": ["personal", "个人", "個人", "プライベート"],
    # ...
}
```

## Immediate Action

Since you're working with Chinese content, I recommend:

1. **Before first data ingestion**, decide on embedding model:
   ```bash
   # For Chinese/English bilingual
   EMBEDDING_MODEL=local/BAAI/bge-m3
   ```

2. Ensure sufficient RAM (4GB+ for bge-m3)

3. Use Kimi as LLM provider (native Chinese support)

## References

- [BGE-M3 Paper](https://arxiv.org/abs/2402.03216) - Multi-lingual embeddings
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Benchmark comparisons
- [BGE-M3 on HuggingFace](https://huggingface.co/BAAI/bge-m3)
