# Local LLM Guide for 16GB VRAM (RTX 5080)

## The Reality Check

**16GB VRAM constraints:**
- 7B models: ✅ Fit easily, ⚠️ Quality comparable to GPT-3.5
- 13B models: ⚠️ Tight fit, need aggressive quantization
- 32B models: ❌ Won't fit without massive quality loss
- 70B models: ❌ Impossible

**For MemCore's consolidation task** (complex reasoning, conflict detection, fact extraction), you really want **strong model tier** quality comparable to Claude 3.5 Sonnet or GPT-4. Local 7B models struggle with this.

---

## Models That Actually Fit (16GB)

### 1. Qwen3 (Newest, Best Bet)
```bash
# 8B - Fits easily, good quality
ollama pull qwen3:8b

# 4B - Smaller, faster, decent for routing
ollama pull qwen3:4b
```
**Pros:** Qwen3 just released, significantly better than 2.5
**Cons:** 8B still not Claude 3.5 level for complex reasoning

### 2. Gemma 3 (Google, Very Efficient)
```bash
# 12B - Might fit at Q4, best quality for size
ollama pull gemma3:12b

# 4B - Ultra-fast, good for routing
ollama pull gemma3:4b
```
**Pros:** Extremely efficient architecture
**Cons:** 12B at Q4 might be tight in 16GB

### 3. DeepSeek R1 Distilled (Qwen/Llama)
```bash
# 14B distilled - Tight but possible
ollama pull deepseek-r1:14b

# 7B distilled - Fits easily
ollama pull deepseek-r1:7b
```
**Pros:** Reasoning-focused, good for consolidation logic
**Cons:** Distilled versions lose some capability

### 4. Phi-4 / Phi-4-Mini (Microsoft)
```bash
# 14B - Very efficient, fits in 16GB
ollama pull phi4

# Mini variant - Fast, smaller
ollama pull phi4-mini
```
**Pros:** Microsoft optimized for efficiency
**Cons:** Not as widely tested

---

## Quantization Guide (Fitting Larger Models)

If you want to squeeze a 32B model into 16GB:

| Model Size | Quantization | VRAM | Quality | Recommendation |
|------------|--------------|------|---------|----------------|
| 7B | Q4_K_M | ~5GB | ⭐⭐⭐⭐ | ✅ Good default |
| 7B | Q8_0 | ~8GB | ⭐⭐⭐⭐⭐ | ✅ Best quality |
| 13B | Q4_K_M | ~9GB | ⭐⭐⭐⭐ | ✅ Recommended |
| 14B | Q4_K_M | ~10GB | ⭐⭐⭐⭐ | ✅ Recommended |
| 32B | IQ3_XXS | ~14GB | ⭐⭐⭐ | ⚠️ Quality suffers |
| 32B | Q3_K_M | ~15GB | ⭐⭐⭐ | ⚠️ Borderline usable |

**Download quantized models directly:**
```bash
# From HuggingFace with Ollama
ollama pull <model>:<quant>

# Example:
ollama pull qwen2.5:14b-q4_K_M
```

---

## Honest Assessment

### For MemCore Consolidation (Fact Extraction, Conflict Resolution):

| Approach | Quality | Cost/Day | Recommendation |
|----------|---------|----------|----------------|
| **Kimi API** | ⭐⭐⭐⭐⭐ | ¥1-3 | ✅ **Best option** |
| **DeepSeek API** | ⭐⭐⭐⭐⭐ | ¥0.50-1 | ✅ Cheapest quality option |
| **Claude 3.5 (Bedrock)** | ⭐⭐⭐⭐⭐ | $2-5 | ✅ If you have AWS |
| Local 7B | ⭐⭐⭐ | ¥0 | ❌ Mediocre consolidation |
| Local 14B | ⭐⭐⭐⭐ | ¥0 | ⚠️ Okay, but not great |
| Local 32B (quantized) | ⭐⭐⭐ | ¥0 | ❌ Slow, quality drops |

### My Recommendation

**Stick with API for now.** Here's why the cost is actually reasonable:

1. **Consolidation runs every 8 hours** (3x/day max)
2. **Processes ~10-50 memories per run** (not thousands)
3. **Uses "strong" tier only for consolidation** (~2-5s per memory)
4. **"Fast" tier for routing** (cheap/moderate cost)

**Estimated daily cost:**
- Kimi: ¥1-3 ($0.15-0.45)
- DeepSeek: ¥0.50-1 ($0.07-0.15)
- Bedrock Claude: $0.50-2

**That's less than a coffee per day** for significantly better memory quality.

---

## If You Really Want Local

Best compromise for 16GB VRAM:

```bash
# For "fast" tier (routing) - use local
ollama pull qwen3:8b

# For "strong" tier (consolidation) - use API
# Keep Kimi/DeepSeek for consolidation only
```

Hybrid approach:
1. Set `LLM_MODEL_FAST=ollama/qwen3:8b` (local, fast, cheap)
2. Keep `LLM_MODEL_STRONG=moonshot/moonshot-v2-5-32k` (API, quality)
3. Most requests use fast tier = savings
4. Only consolidation uses strong tier = controlled cost

---

## DeepSeek - The Budget King

If cost is the main concern, **DeepSeek** is your best bet:

```bash
# .env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
```

- **Quality:** Nearly as good as Kimi K2.5
- **Cost:** ~60% cheaper than Kimi
- **Speed:** Fast enough

Get key: https://platform.deepseek.com/

---

## Summary

| Priority | Recommendation |
|----------|----------------|
| **Quality** | Kimi API or DeepSeek API |
| **Cost** | DeepSeek API |
| **Privacy** | Local 14B + accept quality trade-off |
| **Hybrid** | Local 7B for fast, API for strong |

With a 5080, you're better off using the GPU for **embeddings** (fast) and paying for **LLM API** (quality). The combination gives you speed + quality at reasonable cost.
