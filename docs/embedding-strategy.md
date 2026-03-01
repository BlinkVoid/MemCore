# MemCore Embedding Strategy

## Overview

MemCore uses **local embeddings by default** to ensure vendor-agnostic operation. This document explains the strategy, trade-offs, and migration considerations.

## Default Configuration

| Attribute | Value |
|-----------|-------|
| **Model** | `BAAI/bge-base-en-v1.5` |
| **Dimension** | 768 |
| **Size** | ~210MB |
| **Framework** | fastembed (ONNX Runtime) |
| **Context Length** | 512 tokens |

## Why 768-Dim BGE-Base?

### The Trade-off Space

| Model | Dim | Size | Quality | Speed | MTEB Avg |
|-------|-----|------|---------|-------|----------|
| bge-small-en-v1.5 | 384 | 67MB | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 62.0 |
| **bge-base-en-v1.5** | **768** | **210MB** | **⭐⭐⭐⭐** | **⭐⭐⭐⭐** | **63.5** |
| bge-large-en-v1.5 | 1024 | 1.2GB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 64.2 |
| snowflake-arctic-embed-m | 768 | 430MB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 64.2 |
| nomic-embed-text-v1.5 | 768 | 520MB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 62.3 |

### Reasoning

1. **Better than 384-dim**: 768-dim captures more semantic nuance, critical for a memory system where retrieval accuracy matters
2. **Not too large**: 210MB is reasonable for local deployment vs 1.2GB for large models
3. **Quality plateau**: MTEB scores show diminishing returns above 768-dim for general retrieval
4. **Well-tested**: BGE models are widely adopted and battle-tested in production RAG systems

## Vendor Lock-in Avoidance

### The Problem

If you use vendor-specific embeddings:
```
Kimi Chat API → moonshot-embed-v1 (1536-dim) → Store in Qdrant
Switch to Bedrock → Need different embeddings → Must re-index everything!
```

### The Solution

```
Any Chat API (Kimi/Bedrock/Gemini) → local/BAAI/bge-base-en-v1.5 (768-dim)
Switch providers → Same embeddings → No re-indexing needed!
```

## ⚠️ Critical Warning

**Changing the embedding model after data is stored requires RE-INDEXING your entire vector database!**

### What This Means

1. **Choose once**: Select your embedding model at the start
2. **Dimension must match**: New model must have same dimension OR you recreate the collection
3. **Data migration**: Existing memories need to be re-embedded with new model

### Migration Process (if needed)

```python
# 1. Export all raw memories
memories = vector_store.get_all_memories()

# 2. Create new collection with new dimension
vector_store.create_collection(name="memories_v2", dimension=NEW_DIM)

# 3. Re-embed with new model
for mem in memories:
    new_embedding = await llm.get_embedding(mem.content)  # Uses new model
    vector_store.upsert(mem.id, new_embedding, mem.payload)

# 4. Update alias
vector_store.swap_collection("memories", "memories_v2")
```

## Available Local Models

### 384-Dim (Lightweight)
- `BAAI/bge-small-en-v1.5` (67MB) - Use if resource-constrained
- `sentence-transformers/all-MiniLM-L6-v2` (90MB) - Good general purpose

### 768-Dim (Recommended)
- **`BAAI/bge-base-en-v1.5`** (210MB) - **DEFAULT** - Best balance
- `snowflake/snowflake-arctic-embed-m` (430MB) - Optimized for retrieval
- `nomic-ai/nomic-embed-text-v1.5` (520MB) - 8k context length

### 1024-Dim (High Quality)
- `BAAI/bge-large-en-v1.5` (1.2GB) - Maximum quality
- `mixedbread-ai/mxbai-embed-large-v1` (640MB) - Good quality/size ratio
- `thenlper/gte-large` (1.2GB) - Good for semantic similarity

## Configuration

### Change Embedding Model (at setup only!)

```bash
# In .env
EMBEDDING_MODEL=local/BAAI/bge-large-en-v1.5  # 1024-dim for higher quality
# OR
EMBEDDING_MODEL=local/snowflake-arctic-embed-m  # 768-dim, optimized for retrieval
```

### Use Cloud Embeddings (not recommended)

```bash
# Kimi cloud embeddings (vendor-specific)
EMBEDDING_MODEL=moonshot/moonshot-embed-v1  # 1536-dim

# AWS Bedrock
EMBEDDING_MODEL=bedrock/amazon.titan-embed-text-v2:0  # 1024-dim
```

## Storage Implications

### Vector Database Schema

Qdrant collection is created with fixed dimension:

```python
# storage/vector.py
self.client.create_collection(
    collection_name="memories",
    vectors_config=models.VectorParams(
        size=768,  # Determined by embedding model
        distance=models.Distance.COSINE
    )
)
```

### Memory Usage Estimate

| Records | 384-dim | 768-dim | 1024-dim |
|---------|---------|---------|----------|
| 1,000 | 1.5 MB | 3 MB | 4 MB |
| 10,000 | 15 MB | 30 MB | 40 MB |
| 100,000 | 150 MB | 300 MB | 400 MB |
| 1,000,000 | 1.5 GB | 3 GB | 4 GB |

*Plus metadata overhead (typically 2-3x embedding size)*

## Best Practices

1. **Start with bge-base-en-v1.5 (768-dim)** - Good default for most use cases
2. **Only use small (384-dim) if resource-constrained** - Edge deployment, limited RAM
3. **Use large (1024-dim) only if recall is critical** - Medical, legal, high-stakes domains
4. **Never change embedding model in production** - Plan migration window if needed
5. **Monitor MRR/Recall metrics** - Validate retrieval quality with your data

## References

- [BGE Paper](https://arxiv.org/abs/2309.07597) - BAAI General Embeddings
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Embedding model benchmarks
- [fastembed Documentation](https://qdrant.github.io/fastembed/) - Local embedding framework
