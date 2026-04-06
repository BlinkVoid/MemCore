# Core Concepts: MemCore

This document defines the foundational concepts and mathematical models driving the MemCore memory management system.

## 1. The Importance Equation (Memory Retrieval)
To prioritize memory retrieval and resolve conflicts, MemCore uses a multi-factor scoring formula to determine which memories are most relevant to the current context.

$$Score = (W_{rel} \cdot Relevance) + (W_{rec} \cdot Recency) + (W_{imp} \cdot Importance)$$

### Components:
- **Relevance ($Relevance$):** 
    - Calculated using a combination of Semantic Similarity (Cosine Similarity of embeddings) and Keyword matching (BM25).
    - Measures how closely a memory matches the current query or context.
- **Recency ($Recency$):** 
    - Based on the **Ebbinghaus Forgetting Curve** to simulate "fading" memory unless accessed.
    - $$Recency = e^{-\frac{\Delta t}{S}}$$
    - *$\Delta t$:* Time elapsed since last access.
    - *$S$:* Memory strength (increased by repeated access).
- **Importance ($Importance$):** 
    - An intrinsic score (0.0 to 1.0) assigned by the Gatekeeper LLM during the consolidation phase.
    - High importance is assigned to persistent facts (e.g., user identity, core preferences) and lower importance to transient data (e.g., weather, temporary status).

---

## 2. Tiered Context Disclosure (Precision Revelation)
MemCore manages the LLM's context window by disclosing information in layers, reducing noise and token costs.

- **L0 (Index/Summary):** A high-level directory of "what I know." Allows the agent to see memory topics without details.
- **L1 (Snippet/Overview):** Brief summaries of relevant memory clusters to help the agent decide what to investigate further.
- **L2 (Full Detail):** The raw memory or document, revealed only upon explicit request via the `fetch_detail(uri)` tool.

---

## 3. Memory Lifecycle & Consolidation
MemCore distinguishes between short-term interaction and long-term persistent knowledge.

### A. Short-Term Memory (STM)
- Acts as a buffer for current session raw dialogue.
- Limited by context window and time.

### B. Long-Term Memory (LTM)
- Persistent, vector-indexed storage.
- Contains "Reflected" and "Consolidated" facts.

### C. The Consolidation Pipeline (Sleep Phase)
1. **Extraction:** LLM extracts atomic facts and procedural skills from STM.
2. **Deduplication:** Compares new facts against LTM to prevent redundancy.
3. **Conflict Resolution:** Uses the Importance Equation and temporal authority to resolve contradictory information.
4. **Synthesis:** Merges related memories into cohesive "Reflections."

---

## 4. Agentic Gatekeeping (Strand SDK)
- **Standalone Process:** MemCore runs as a watched process using the Strand SDK.
- **MCP Gatekeeper:** All memory access (L0, L1, L2) and consolidation are exposed via the Model Context Protocol (MCP).
- **Self-Management:** The agent uses its own tools to manage its memory state, prune irrelevant data, and optimize its own context window.
