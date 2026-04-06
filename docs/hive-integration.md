# Memcore × HIVE Integration Guide

**Date:** 2026-03-02
**Status:** Design Complete

Memcore serves as the **L2 Persistent Memory** layer for HIVE (an agent swarm orchestration framework).
This document describes the integration contract between the two systems.

---

## Overview

HIVE is an agent swarm orchestration framework. It coordinates multiple AI worker agents through
a declarative DAG engine with dynamic worker scaling and event-driven coordination. HIVE uses a
two-tier memory model:

| Tier | System | Scope | Description |
|------|--------|-------|-------------|
| L1 | HIVE DataPool | Per-execution | Fast in-memory KV store; workers share intermediate results within a single run |
| L2 | **Memcore** | Cross-execution | Persistent swarm intelligence; workers query past knowledge; swarm improves over time |

Memcore's role in HIVE is **swarm intelligence storage**. Every verified execution result is
committed to Memcore LTM. Every new execution begins by querying Memcore for relevant prior knowledge.
Over time, the swarm gets faster and more accurate without any explicit reprogramming.

---

## How HIVE Uses Memcore

### Three Integration Touchpoints

#### 1. Pre-Execution Recall (Workers query before executing)

Before dispatching workers for a new swarm execution, the HIVE orchestrator queries Memcore
to retrieve relevant memories. These are injected into each worker's task prompt.

**HIVE calls:**
```json
{
  "tool": "mem_request",
  "input": {
    "query": "<task description>",
    "quadrant_hint": "<capability_type>",
    "context_limit": 500,
    "include_l2": false
  }
}
```

HIVE then checks: for any memory with `score > 0.85`, it calls `fetch_detail` to get the full L2 content.
For memories with `score <= 0.85`, only the L1 summary is injected.

**Worker receives in its task prompt:**
```
Prior swarm knowledge (from Memcore):
[Score: 0.92] Previous analysis found service mesh bottleneck at ingress layer.
              Full detail: <L2 content fetched via fetch_detail>
[Score: 0.78] Pattern: fan-out synthesis worked well for microservice analysis tasks.
```

#### 2. Post-Execution Commit (Orchestrator writes learnings after convergence)

After the swarm converges and the orchestrator accepts the final outputs, HIVE commits the
execution result to Memcore as immediate LTM (bypassing the 8h STM buffer).

**HIVE calls:**
```json
{
  "tool": "mem_rem",
  "input": {
    "content": "<JSON of final_outputs + audit_summary>",
    "summary": "[HIVE:<pattern_name>] <one-line summary of what was produced>",
    "quadrants": ["<capability_type_quadrant>", "ai_instructions"],
    "metadata": {
      "source": "hive_swarm",
      "execution_id": "<uuid>",
      "pattern": "<pattern_name>",
      "iterations": 2,
      "workers_used": 4,
      "models_used": ["kimi-k2.5", "deepseek-r1"],
      "converged": true
    },
    "is_immediate_ltm": true,
    "importance_override": 0.9
  }
}
```

**Why `is_immediate_ltm: true`:**
HIVE execution results are verified, reviewed, and accepted by the orchestrator before being committed.
They represent the highest-quality knowledge the swarm has produced. There is no benefit to buffering
them in STM — they should be available to future executions immediately.

**Why `importance_override: 0.9`:**
Swarm execution outputs are always high-importance. Setting 0.9 ensures the Memcore gatekeeper
does not under-score them during consolidation. This keeps HIVE results near the top of retrieval
rankings for future similar queries.

#### 3. Feedback Reinforcement (Orchestrator reinforces retrieval quality)

After the orchestrator reviews a worker output and decides to accept or reject it, HIVE signals
Memcore so the graph weights on `FULFILLED_BY` edges are updated.

**On accept:**
```json
{
  "tool": "submit_feedback",
  "input": {
    "request_id": "<uuid of the mem_request call>",
    "memory_id": "<id of the memory that was injected>",
    "rating": 1,
    "feedback_text": ""
  }
}
```

**On reject (with reason):**
```json
{
  "tool": "submit_feedback",
  "input": {
    "request_id": "<uuid>",
    "memory_id": "<id>",
    "rating": -1,
    "feedback_text": "Memory was about v1 API but task needed v2 patterns"
  }
}
```

This creates a reinforcement learning loop: memories that consistently help HIVE workers produce
accepted outputs accumulate high graph weights and rank higher in future retrievals. Memories that
lead to rejected outputs are penalized.

---

## Quadrant Mapping

HIVE maps worker capability types to Memcore quadrants:

| HIVE Capability Type | Memcore Quadrant |
|---------------------|-----------------|
| `code` | `coding` |
| `research` | `research` |
| `analysis` | `research` |
| `synthesis` | `research` |
| `reasoning` | `research` |
| `instructions` | `ai_instructions` |
| `personal` | `personal` |
| *(default)* | `research` |

HIVE always adds `ai_instructions` as a second quadrant when committing execution results,
since swarm execution patterns are procedural knowledge useful to future orchestrations.

---

## Memcore Tiered Disclosure in HIVE Context

Memcore's L0/L1/L2 tiers map to specific HIVE use cases:

| Tier | HIVE Usage | Token Cost |
|------|-----------|-----------|
| **L0 (Index)** | Orchestrator scans available memory topics before deciding which to query | Minimal |
| **L1 (Snippet)** | Default injection into worker prompts — all memories from `mem_request` | Low |
| **L2 (Full Detail)** | Fetched only when `score > 0.85` — high-confidence prior art | Medium |

This keeps the worker's effective context cost low while ensuring high-relevance memories
get their full content injected.

---

## The Swarm Intelligence Feedback Loop

```
Execution 1: Cold Start
  ┌─────────────────────────────────────────────────────────┐
  │ mem_request → (empty or low-score results)               │
  │ Workers execute without prior context                     │
  │ Orchestrator reviews → accepts → converges               │
  │ mem_rem(final_outputs, is_immediate_ltm=True, imp=0.9)  │
  └─────────────────────────────────────────────────────────┘
                          │
                          ▼ (Memcore consolidates to LTM)

Execution 2: Warm Start (same/similar task)
  ┌─────────────────────────────────────────────────────────┐
  │ mem_request → returns Execution 1 output at score ~0.85 │
  │ Workers start with prior knowledge injected             │
  │ Better first-draft outputs                              │
  │ Fewer review iterations to convergence                  │
  │ submit_feedback(rating=1) → boosts graph weight         │
  └─────────────────────────────────────────────────────────┘
                          │
                          ▼ (Graph FULFILLED_BY weight increased)

Execution N: Experienced Swarm
  ┌─────────────────────────────────────────────────────────┐
  │ mem_request → returns highly-ranked, relevant memories  │
  │ Workers consistently receive actionable prior context   │
  │ Fastest path to convergence                             │
  │ Highest quality outputs                                 │
  │ Minimal retries                                         │
  └─────────────────────────────────────────────────────────┘
```

---

## Configuration

### Memcore Server (SSE mode — recommended for HIVE)

HIVE connects to Memcore via its SSE transport. Start Memcore before starting the HIVE manager:

```bash
# Start Memcore SSE server
cd /path/to/memcore
uv run src/memcore/main.py --mode sse
# Running at http://127.0.0.1:8080/sse
```

### HIVE Memcore Adapter Configuration

```python
# In HIVE's configuration
MEMCORE_SSE_URL = "http://127.0.0.1:8080/sse"
MEMCORE_HIGH_RELEVANCE_THRESHOLD = 0.85   # Fetch L2 for scores above this
MEMCORE_CONTEXT_BUDGET = 500              # Max tokens for pre-execution recall
MEMCORE_IMPORTANCE_SWARM = 0.9            # Importance override for committed swarm outputs
```

### MCP Client Config (for HIVE manager to connect to Memcore)

```json
{
  "mcpServers": {
    "memcore": {
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```

---

## Important Notes for Memcore Development

### What HIVE Writes to Memcore

All writes from HIVE are structured as:

```
summary: "[HIVE:<pattern_name>] <one-line description>"
quadrants: ["<task_quadrant>", "ai_instructions"]
metadata.source: "hive_swarm"
is_immediate_ltm: true
importance_override: 0.9
```

The `metadata.source = "hive_swarm"` tag allows Memcore queries to filter for (or exclude)
swarm-generated memories if needed.

### What Executions Look Like in Memcore LTM

Each completed HIVE execution leaves one LTM entry containing:
- `final_outputs`: The verified swarm output (JSON)
- `audit_summary`: Which steps ran, iterations count, models used, convergence status
- Metadata: pattern name, execution ID, worker count, model IDs used

These entries enable future executions to benefit from the full context of what worked before,
not just the output — including which models were used and how many iterations it took.

### Conflict Resolution Relevance

Memcore's built-in conflict resolution (temporal authority, consensus check) is valuable for
HIVE because:
- Different executions may produce conflicting findings (e.g., "API is fast" vs "API is slow")
- Memcore's `CONTRASTED_WITH` graph edge naturally tracks these conflicts
- The orchestrator can query conflicting memories and make an informed synthesis decision

### Memory Pruning Consideration

HIVE executions can generate large volumes of LTM entries over time. Consider:
- Setting `importance_override` lower (e.g., 0.6) for exploratory/experimental executions
- Using Memcore's consolidation pipeline to merge related execution summaries periodically
- Filtering by `metadata.pattern` when querying to keep results pattern-specific

---

## Related Documents

- Memcore Core Concepts: [core-concepts.md](./core-concepts.md)
- Memcore API Specification: [api-specification.md](./api-specification.md)
- Memcore Architecture: [research-memcore-architecture.md](./research-memcore-architecture.md)
