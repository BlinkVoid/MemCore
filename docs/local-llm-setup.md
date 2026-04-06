# Local LLM Setup for MemCore

Run MemCore with local LLMs - no API keys or cloud services required!

## Quick Start with Ollama

### 1. Install Ollama
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - download from https://ollama.com/download
```

### 2. Pull Models
```bash
# Fast model (for classification/routing)
ollama pull qwen2.5:7b

# Strong model (for consolidation)
ollama pull qwen2.5:32b
# OR for smaller machines:
ollama pull llama3.1:8b
```

### 3. Configure MemCore

Edit `.env`:
```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434

# Optional: Override default models
LLM_MODEL_FAST=qwen2.5:7b
LLM_MODEL_STRONG=qwen2.5:32b
```

### 4. Update LLM Interface

Add to `src/memcore/utils/llm.py`:

```python
MODEL_CATALOGUE = {
    # ... existing providers ...
    
    "ollama": {
        "fast": "ollama/qwen2.5:7b",
        "strong": "ollama/qwen2.5:32b",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"
    },
}

PROVIDER_API_KEYS = {
    # ... existing ...
    "ollama": [],  # No API key needed
}
```

## Model Recommendations

| Use Case | Model | VRAM Required | Speed |
|----------|-------|---------------|-------|
| Fast (Routing) | qwen2.5:7b | 6GB | Fast |
| Strong (Consolidation) | qwen2.5:14b | 12GB | Medium |
| Strong (Best Quality) | qwen2.5:32b | 24GB | Slow |
| Balanced | llama3.1:8b | 6GB | Fast |

## Pros & Cons

### ✅ Advantages
- **Free** - No API costs
- **Private** - Data never leaves your machine
- **Offline** - Works without internet
- **No rate limits** - Process as fast as your hardware allows

### ❌ Disadvantages
- **Hardware requirements** - Need GPU for good performance
- **Setup complexity** - Must manage models yourself
- **Slower** - Local models typically slower than cloud APIs
- **Quality** - May not match Kimi K2.5 for complex tasks

## Testing

```bash
# Test Ollama is running
curl http://localhost:11434/api/tags

# Test MemCore with local LLM
uv run scripts/verify_config.py
```
