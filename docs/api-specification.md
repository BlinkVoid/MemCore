# API Specification: MemCore MCP

This document defines the interface for interacting with the MemCore Gatekeeper via the Model Context Protocol (MCP).

## 1. Tool: `mem_request`
Used by agents to retrieve context for a specific task or query.

### Input Schema
```json
{
  "query": "string",
  "quadrant_hint": "string (optional: coding | personal | research | ai_instructions)",
  "context_limit": "integer (optional: max tokens or snippets)",
  "include_l2": "boolean (optional: default false)"
}
```

### Response Format
Returns a list of scored memory snippets (L0/L1) with their unique URIs for potential L2 fetching.
```json
{
  "quadrant": "coding",
  "memories": [
    {
      "id": "uuid-1",
      "summary": "Project structure for Strand SDK",
      "score": 0.95,
      "uri": "mem://coding/uuid-1"
    }
  ]
}
```

---

## 2. Tool: `mem_rem`
Used to store new information into the memory system.

### Input Schema
```json
{
  "content": "string (The full raw content)",
  "summary": "string (Brief gist)",
  "quadrants": ["string"],
  "metadata": {
    "source": "string",
    "importance_override": "float (0.0 - 1.0)"
  },
  "is_immediate_ltm": "boolean (If true, skips the 8h buffer)"
}
```

---

## 3. Tool: `fetch_detail`
Retrieves the L2 (Full Detail) of a specific memory entry.

### Input Schema
```json
{
  "memory_id": "string"
}
```

---

## 4. Tool: `submit_feedback`
Updates the graph weights and triggers RCA for inaccurate retrievals.

### Input Schema
```json
{
  "request_id": "uuid",
  "memory_id": "uuid",
  "rating": "integer (-1 for bad, 1 for good)",
  "feedback_text": "string (optional: why it was wrong)"
}
```
