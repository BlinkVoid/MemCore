# Implementation Plan: MemCore

This document outlines the technical roadmap for building the MemCore standalone memory management system.

## 1. Technology Stack
- **Runtime:** Python 3.12+ (Managed via `uv`)
- **Agent Framework:** Strands Agents SDK (Watched process)
- **Interface:** Model Context Protocol (MCP)
- **Vector Storage:** Qdrant (Local storage for L0-L2 tiered context)
- **Graph Storage:** SQLite + NetworkX (Request-Answer mapping & entity relations)
- **LLM Integration:** LiteLLM (Supporting Kimi K2.5, Bedrock, and DeepSeek)
- **Scheduling:** APScheduler (For background consolidation/Sleep Phase)

## 2. Phase 1: Foundation (Current)
- [x] Project scaffolding with `uv`.
- [x] Implementation of core utility equations (Importance/Recency).
- [x] Basic Vector and Graph storage interfaces.
- [x] Gatekeeper Router (Quadrant classification).
- [x] Initial MCP interface (`mem_request`, `mem_rem`).

## 3. Phase 2: Memory Intelligence
- [x] **Advanced Tiered Retrieval:** Progressive L0 -> L1 with token budgeting; L2 on-demand via fetch_detail.
- [x] **Dynamic Relevancy:** Graph edge weights boost memory scores; feedback strengthens/weakens retrieval.
- [x] **Instruction Extraction:** Specialized pipeline with validation, types (constraint/standard/workflow/behavior/preference), override tracking.

## 4. Phase 3: Autonomous Consolidation (Sleep Phase) - COMPLETE
- [x] **Stateful Queue:** SQLite-backed job queue survives restarts with retry logic.
- [x] **Fact Synthesis:** LLM-driven deduplication and "Reflection" generation from related memories.
- [x] **Conflict Resolution:** Hierarchy-based resolution logic for contradictory memories implemented.

## 5. Phase 4: Feedback & Optimization
- [ ] **Root Cause Analysis:** Implement the "Why was this retrieval wrong?" loop.
- [ ] **Global Score Adjustment:** Logic to adjust weights ($W_{rel}$, $W_{rec}$, $W_{imp}$) based on historical accuracy.
