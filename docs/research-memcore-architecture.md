# MemCore Architecture: Two-Prone Context & Memory Management

This document outlines the architecture for **MemCore**, a standalone memory management system for AI agents. The design focuses on two main pillars: **Precision Context Revelation** and **Gatekept Memory Retrieval**.

---

## 1. Pillar I: Precision Context Revelation
The goal is to ensure the LLM receives the "perfect" amount of context—enough to be useful, but sparse enough to minimize token costs and noise.

### A. Tiered Context Disclosure (The "On-Demand" Paging)
Inspired by OpenViking and MemGPT, MemCore uses a tiered approach:
- **L0 (Index/Summary):** A high-level map of available memories. The agent sees "what it knows" without seeing the full details.
- **L1 (Snippet/Overview):** Brief summaries of relevant memory clusters.
- **L2 (Full Detail):** The raw memory/document, revealed only when the agent explicitly requests it via a `fetch_detail(uri)` tool.

### B. Dynamic Context Window Scaling
MemCore calculates the "Context Budget" based on the underlying model's limits (e.g., Kimi K2.5 vs. local Llama 3). It uses a **Virtual Memory Paging** mechanism to swap L2 details in and out of the active window while keeping L0/L1 persistent.

---

## 2. Pillar II: Gatekept Memory Retrieval & Consolidation
The **Strand Agent** acts as the gatekeeper, managing the lifecycle of memories and resolving conflicts.

### A. The Importance Equation
To prioritize memory retrieval and resolve conflicts, MemCore uses a multi-factor scoring formula:

$$Score = (W_{rel} \cdot Relevance) + (W_{rec} \cdot Recency) + (W_{imp} \cdot Importance)$$

-   **Relevance ($Relevance$):** Semantic similarity (Cosine Similarity) + Keyword matching (BM25).
-   **Recency ($Recency$):** Exponential decay based on the **Ebbinghaus Forgetting Curve**:
    $$Recency = e^{-\frac{\Delta t}{S}}$$
    *(Where $\Delta t$ is time since last access and $S$ is the "strength" of the memory).*
-   **Importance ($Importance$):** An intrinsic score (0.0 - 1.0) assigned by the Gatekeeper LLM during the consolidation phase.

### B. Conflict Resolution Logic
When retrieved memories contradict each other (e.g., "User's favorite color is Red" vs. "User's favorite color is Blue"), the Gatekeeper applies the following hierarchy:
1.  **Temporal Authority:** If one memory is significantly more recent and has a higher "strength" ($S$), it overrides the older one.
2.  **Consensus Check:** The Gatekeeper may query the LTM to see if there are other supporting memories for either claim.
3.  **Explicit Verification:** If the conflict persists, the Gatekeeper can trigger an MCP tool to ask the user for clarification.
4.  **Reflective Synthesis:** The LLM synthesizes a "consensus" view, marking the old memories as `deprecated` and creating a new `consolidated` memory.

---

## 3. Memory Consolidation Workflow (STM to LTM)
The Strand Agent runs as a background process to perform "Sleep Phase" consolidation:

1.  **Buffer Analysis:** Every $N$ interactions, the agent scans the STM (Short-Term Memory) buffer.
2.  **Fact Extraction:** The LLM extracts key facts, preferences, and procedural "skills" from the raw dialogue.
3.  **Deduplication & Conflict Check:** Extracted facts are compared against the existing LTM (Long-Term Memory).
4.  **Importance Assignment:** The LLM assigns an $Importance$ score based on utility (e.g., "User's name" = 1.0, "Weather today" = 0.1).
5.  **LTM Write:** Validated and scored facts are written to the permanent Vector DB / Graph Store.
6.  **Buffer Pruning:** The raw STM is summarized and cleared to free up context.

---

## 4. MCP Interface (The Gatekeeper's Tools)
MemCore exposes its capabilities via MCP:
- `query_memory(query)`: Returns L0/L1 context.
- `fetch_detail(uri)`: Returns L2 full detail.
- `consolidate_now()`: Manually triggers the STM -> LTM pipeline.
- `resolve_conflict(id1, id2)`: Explicitly handles two conflicting memory IDs.
