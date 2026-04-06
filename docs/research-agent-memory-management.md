# AI Agent Memory Management Research

## Executive Summary
This document summarizes the current landscape of AI memory management, covering academic research (ArXiv), industry methodologies, and specific open-source tools like ByteDance's **OpenViking**. The goal is to provide a foundation for designing **MemCore**, a standalone memory management system.

---

## 1. Core Methodologies & Techniques

### A. Short-Term Memory (Working Memory)
Functions as a temporary storage system for ongoing interactions.
- **Context Window:** The immediate token buffer.
- **Sliding Window:** Retaining only the last $k$ interactions.
- **Summary Buffer:** Periodically summarizing older dialogue to preserve the "gist" while freeing up context space.

### B. Long-Term Memory (Persistent Knowledge)
Stored externally to the LLM, enabling persistence across sessions.
- **Retrieval-Augmented Generation (RAG):** Searching external databases (Vector DBs) and injecting relevant context into the prompt.
- **Knowledge Graphs:** Representing relationships between entities to allow for complex reasoning.
- **Semantic Search:** Using embeddings to find information based on meaning rather than keywords.

---

## 2. ArXiv & Academic Research Highlights

Recent papers focus on making memory more "agentic" and structured:
- **A-MEM (Agentic Memory):** Inspired by the **Zettelkasten method**, it dynamically organizes memories into interconnected knowledge networks rather than flat lists.
- **FluxMem:** Equips agents with multiple complementary memory structures and adaptively selects the best one based on the context.
- **MemoryOS:** An OS-inspired framework using a multi-tiered architecture (short-term, mid-term, long-term) with modules for storage, updates, retrieval, and generation.
- **Mem0:** A scalable architecture that uses LLMs to extract key facts and dynamically maintains consistency via `ADD`, `UPDATE`, and `DELETE` instructions.

---

## 3. Deep Dive: OpenViking (ByteDance)

**OpenViking** is a context database for AI Agents that treats memory through a **"file system paradigm."**

### Key Innovations:
- **Viking URI Protocol:** Information is organized under `viking://`, allowing agents to use deterministic commands like `ls` and `find`.
- **Layered Context Loading:**
    - **L0 (Summary):** High-level gist.
    - **L1 (Overview):** Structural information.
    - **L2 (Details):** Full content.
  *This drastically reduces token costs by loading only what is necessary.*
- **Recursive Directory Retrieval:** Combines intent analysis with hierarchical exploration of the "file system" to find relevant context.
- **Self-Evolving Intelligence:** Automatically analyzes session outcomes and feedback to update preferences and operational knowledge.

---

## 4. Theoretical & Advanced Architectures

### A. MemGPT: OS-Inspired Memory Management
MemGPT treats the LLM's context window as **Virtual Memory (RAM)** and external databases as **Disk Storage**.
- **Virtual Context Management:** Dynamically "pages" information in and out of the context window using function calls.
- **Interrupt Handling:** Uses an event loop to handle user inputs, document uploads, and internal processing triggers.
- **Self-Directed Edits:** The LLM itself decides when to update its "working context" or "archival storage," rather than relying on external heuristics.

### B. Generative Agents (Stanford/Smallville)
Introduced a "Memory Stream" and "Reflection" architecture for believable human-like agents.
- **Memory Stream:** A comprehensive, timestamped log of all experiences.
- **Retrieval Scoring:** Memories are retrieved based on a weighted sum of **Recency**, **Importance**, and **Relevance**.
- **Reflection:** Periodically, the agent pauses to synthesize "higher-level" thoughts from raw observations, forming a cohesive identity and understanding of relationships.

### C. Episodic & Procedural Memory Hierarchies
- **Episodic Memory:** Storing specific events and session-based trajectories (input-output pairs).
- **Procedural Memory:** Knowledge of *how* to perform tasks, often stored as code snippets or validated "tool-use" sequences.
- **H-MEM (Hierarchical Memory):** Organizes memory into semantically abstracted layers (Domain -> Category -> Episode) to avoid exhaustive semantic searches.

### D. Self-Evolving & Learnable Memory
- **MemSkill:** Replaces static memory operations with a "Skill Bank" that the agent evolves through interaction, learning how to better extract and prune information.
- **Memory-of-Thought (MoT):** LLMs pre-think on data and store high-confidence reasoning chains as external memory to be recalled during complex tasks.

---

## 5. Methodologies for MemCore

Based on the expanded research, MemCore should incorporate:

1.  **Virtual Paging (MemGPT style):** Allow the agent to "page" context via MCP tools, enabling it to manage its own limited local context.
2.  **Tiered Hierarchy (OpenViking + H-MEM):** Use a file-system-like URI (`mem://`) and tiered loading (Summary -> Detail) for efficiency.
3.  **Reflection & Consolidation:** Implement a "Background Process" (via Strand SDK) that periodically performs reflection and memory pruning, inspired by Generative Agents.
4.  **Recency/Importance/Relevance Retrieval:** Go beyond simple vector similarity by implementing a multi-factor scoring mechanism for memory recall.
5.  **Agentic "Skill" Management:** Store not just facts, but validated "procedural" tools and reasoning patterns that have worked in the past.

---

## References
- ByteDance OpenViking (Volcengine Viking Team).
- "A Survey on the Memory Mechanism of Large Language Model based Agents" (ArXiv).
- "Memory in the Age of AI Agents" (ArXiv).
- Mem0 & LangMem libraries.
