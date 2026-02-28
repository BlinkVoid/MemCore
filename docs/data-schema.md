# Data Schema: MemCore Storage

MemCore uses a hybrid storage approach combining Vector search for semantic retrieval and Graph relationships for contextual associations.

## 1. Vector Store (Qdrant)
**Collection:** `memcore_memories`

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key |
| `vector` | float[1536] | OpenAI/DeepSeek Embeddings |
| `payload.summary` | string | **L0:** The high-level index entry |
| `payload.overview` | string | **L1:** The brief context snippet |
| `payload.content` | string | **L2:** The full raw data |
| `payload.quadrants`| list[str] | Semantic tags |
| `payload.importance`| float | Intrinsic importance score |
| `payload.timestamp` | ISO8601 | For recency calculation |
| `payload.type` | enum | `raw` (STM) \| `consolidated` (LTM) \| `instruction` |

## 2. Graph Store (SQLite + NetworkX)
The graph tracks the "Experience Map" of the agent.

### Nodes
- **MemoryNode:** Links to a Vector ID. Attributes: `type='memory'`, `summary`.
- **RequestNode:** A historical `mem_request`. Attributes: `type='request'`, `query`, `timestamp`.
- **InstructionNode:** Specialized SOPs. Attributes: `type='instruction'`.
- **EntityNode:** Extracted entities (User, Project Name).

### Edges
- `FULFILLED_BY`: Connects `RequestNode` -> `MemoryNode`. Has a `weight` attribute that evolves with feedback.
- `CONTRASTED_WITH`: Connects two `MemoryNode`s that contain conflicting info.
- `ASSOCIATED_WITH`: Temporal or semantic connection between memories.
- `FOLLOW_UP_TO`: Connects a sequence of `RequestNode`s in a session.

## 3. The Relevancy Update Loop
1. `mem_request` is received.
2. Vector store returns Top-K candidates.
3. Graph store is queried for the same candidates.
4. If a candidate has a high `weight` on a `FULFILLED_BY` edge for a similar historical request, its score is boosted.
5. If feedback is negative, the `weight` is decreased.
