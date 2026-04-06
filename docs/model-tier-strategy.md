# MemCore Model Tier Strategy

## Current Implementation

The `tier` parameter is **explicitly chosen** based on task complexity:

| Tier | Cost | Latency | Used For |
|------|------|---------|----------|
| **fast** | Low | ~500ms | Simple classification, routing, quick queries |
| **strong** | Higher | ~2-5s | Complex extraction, consolidation, root cause analysis |

## Current Usage in Code

```python
# src/memcore/gatekeeper/router.py - Classification (simple task)
tier="fast"  # Claude 3.5 Haiku, Moonshot v1-8k, Gemini Flash

# src/memcore/memory/consolidation.py - Complex extraction
tier="strong"  # Claude 3.5 Sonnet, Moonshot v2.5-32k, Gemini Pro

# src/memcore/main.py - Document processing & RCA
tier="strong"  # Heavy lifting tasks
```

## How It Maps to Providers

| Provider | Fast Model | Strong Model |
|----------|------------|--------------|
| **Kimi** | `moonshot-v1-8k` | `moonshot-v2.5-32k` |
| **Bedrock** | `claude-3-5-haiku` | `claude-3-5-sonnet` |
| **Gemini** | `gemini-2.0-flash` | `gemini-2.0-pro` |
| **DeepSeek** | `deepseek-chat` | `deepseek-reasoner` |

## Is It Automatic?

**No** - It's intentionally explicit in code:
- Router decides WHICH quadrant → uses `fast` model
- Memory consolidation → uses `strong` model

This is a **design choice** - we trade some efficiency for predictability.

## Future Enhancement: Adaptive Tier Selection

Could implement automatic selection based on:

```python
async def adaptive_completion(self, messages, complexity_hint=None, **kwargs):
    """
    Automatically select tier based on:
    1. Input length (longer = more tokens = use fast)
    2. Task type (extraction vs summarization)
    3. Latency requirements (user waiting? use fast)
    4. Token budget remaining
    """
    if complexity_hint == "complex" or self._estimate_tokens(messages) > 4000:
        tier = "strong"
    else:
        tier = "fast"
    return await self.completion(messages, tier=tier, **kwargs)
```

But explicit tiers are clearer for now.
