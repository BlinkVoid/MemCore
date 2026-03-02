# TODO for Tomorrow - MemCore

**Date:** 2026-03-03  
**Status:** Ready to test and continue development

---

## ✅ Completed Today

### 1. Stateful Consolidation Queue (Major Feature)
- **File:** `src/memcore/storage/queue.py` - New SQLite-backed job queue
- **Features:**
  - Jobs survive process restarts
  - Crash recovery (resets 'processing' → 'pending' on startup)
  - Retry mechanism (3 attempts before marking failed)
  - Job history tracking
  - Batch enqueue/dequeue

- **Integration:**
  - `src/memcore/memory/consolidation.py` - Updated to use queue
  - `src/memcore/main.py` - Queue lifecycle integrated
  - `src/memcore/utils/reporter.py` - Queue stats on dashboard

### 2. DeepSeek Provider (Cost Optimization)
- **Configured:** `.env` now uses `LLM_PROVIDER=deepseek`
- **Models:**
  - Fast: `deepseek/deepseek-chat`
  - Strong: `deepseek/deepseek-reasoner`
- **Cost:** ~60% cheaper than Kimi
- **Action Required:** Add your DeepSeek API key to `.env`

### 3. Ollama Support (Local LLM Option)
- Added Ollama as provider option
- Created documentation in `docs/local-llm-setup.md`
- Created GPU model guide in `docs/gpu-model-guide.md`

---

## 🚀 Next Steps (TODO)

### Priority 1: Test DeepSeek Integration
```bash
# 1. Add your DeepSeek API key to .env
# Get key from: https://platform.deepseek.com/

# 2. Verify configuration
uv run scripts/verify_config.py

# 3. Test consolidation queue
uv run python -c "
from src.memcore.storage.queue import ConsolidationQueue
q = ConsolidationQueue()
print('Pending jobs:', q.get_pending_count())
print('Queue stats:', q.get_stats())
"
```

### Priority 2: Remaining Implementation Plan Items

From `docs/implementation-plan.md`:

#### Phase 2: Memory Intelligence (Not Started)
- [ ] **Advanced Tiered Retrieval** - Refine L0 → L1 → L2 loop for token efficiency
- [ ] **Dynamic Relevancy** - Use graph edge weights to boost memory scores
- [ ] **Instruction Extraction** - Specialized pipeline for `ai_instructions` quadrant

#### Phase 3: Autonomous Consolidation (Partial)
- [x] **Stateful Queue** - ✅ DONE
- [ ] **Fact Synthesis** - LLM-driven deduplication and "Reflection" generation
- [ ] **Conflict Resolution** - Hierarchy-based logic for contradictory memories

#### Phase 4: Feedback & Optimization (Not Started)
- [ ] **Root Cause Analysis** - Expand the "Why was this retrieval wrong?" loop
- [ ] **Global Score Adjustment** - Auto-tune weights ($W_{rel}$, $W_{rec}$, $W_{imp}$)

---

## 🔧 Quick Commands for Tomorrow

```bash
# Verify everything is working
uv run scripts/verify_config.py

# Check queue status
uv run python -c "
from src.memcore.storage.queue import ConsolidationQueue
q = ConsolidationQueue()
stats = q.get_stats()
print(f'Queue: {stats[\"pending\"]} pending, {stats[\"processing\"]} processing, {stats[\"completed\"]} completed')
"

# Start the server
.\start-memcore.ps1

# Or manually
uv run src/memcore/main.py --mode sse --port 8080

# Check health
curl http://127.0.0.1:8080/health

# View status dashboard
start http://127.0.0.1:8080/status
```

---

## 📊 Current System State

| Component | Status | Notes |
|-----------|--------|-------|
| Vector DB (Qdrant) | ✅ Ready | Local storage in `dataCrystal/qdrant_storage` |
| Graph DB (SQLite) | ✅ Ready | Local storage in `dataCrystal/memcore_graph.db` |
| Consolidation Queue | ✅ Ready | SQLite-backed, survives restarts |
| LLM Provider | ⚠️ Configured | DeepSeek selected, needs API key |
| Embeddings | ✅ Ready | Local multilingual-e5-large |
| MCP Server | ✅ Ready | Tools defined, SSE transport ready |
| HTML Dashboard | ✅ Ready | Auto-refreshes every hour |

---

## 🎯 Suggested Tomorrow's Plan

1. **Morning (15 min):**
   - Add DeepSeek API key to `.env`
   - Run `uv run scripts/verify_config.py`
   - Test basic query/save operations

2. **Development Session:**
   - Pick one item from Phase 2 or 3
   - Implement and test
   - Update `docs/implementation-plan.md`

3. **End of Day:**
   - Verify queue is processing jobs
   - Check dashboard for stats
   - Document any issues

---

## 📁 New Files Created Today

| File | Purpose |
|------|---------|
| `src/memcore/storage/queue.py` | Stateful consolidation queue |
| `docs/RUST_PYTHON_COMPARISON.md` | Architecture decision doc |
| `docs/local-llm-setup.md` | Ollama setup guide |
| `docs/gpu-model-guide.md` | 16GB VRAM model recommendations |
| `docs/TODO-TOMORROW.md` | This file |

---

## 📝 Notes

- **DeepSeek is configured** but needs your API key to work
- **Queue is persistent** - any jobs you create today will be there tomorrow
- **Dashboard shows queue stats** - check `/status` endpoint
- **No breaking changes** - all existing data is compatible

---

Good luck tomorrow! 🧠🚀
