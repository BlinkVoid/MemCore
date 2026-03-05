# MemCore Dashboard Stats Visualization Design

## Goal
Visual statistics to understand MemCore state at a glance - charts, diagrams, and data visualizations.

## Stats to Visualize

### 1. Quadrant Distribution (Donut Chart)
```
┌─ Knowledge by Quadrant ──────────────────────────┐
│                                                   │
│        ╭──────────╮                               │
│       ╱   45%    ╲       Coding: 45% (234)       │
│      │  Coding   │       Personal: 15% (78)      │
│       ╲   🔵    ╱        Research: 30% (156)     │
│        ╰──────────╯      AI Instructions: 10%    │
│                                                   │
└───────────────────────────────────────────────────┘
```

### 2. Tag Frequency (Bar Chart + Word Cloud)
```
┌─ Popular Tags ────────────────────────────────────┐
│                                                   │
│  python     ████████████████████████████  45     │
│  security   ████████████████████          32     │
│  learning   ██████████████                24     │
│  ai         ██████████                    18     │
│  ...                                      ...    │
│                                                   │
│  [python] [security] [learning] [ai] [dev]...   │
│    45       32        24        18    15         │
└───────────────────────────────────────────────────┘
```

### 3. Memory Type Breakdown (Pie Chart)
```
┌─ Memory Types ────────────────────────────────────┐
│                                                   │
│     Raw        ████████  60% (312)               │
│     Consol.    █████     35% (182)               │
│     Reflect.   █         5%  (26)                │
│                                                   │
│  [Raw 312] [Consolidated 182] [Reflections 26]   │
└───────────────────────────────────────────────────┘
```

### 4. Ingestion Timeline (Line/Area Chart)
```
┌─ Memories Added (Last 30 Days) ───────────────────┐
│                                                   │
│  20 │          ╱╲                                │
│  15 │    ╱╲   ╱  ╲    ╱╲                        │
│  10 │   ╱  ╲ ╱    ╲  ╱  ╲                       │
│   5 │  ╱    ╲╱      ╲╱    ╲                     │
│   0 └───────────────────────────────              │
│     Mar1  Mar5  Mar10  Mar15  Mar20              │
│                                                   │
│  Daily Avg: 8.5 │ Peak: 23 (Mar 12)              │
└───────────────────────────────────────────────────┘
```

### 5. Importance Distribution (Histogram)
```
┌─ Memory Importance ───────────────────────────────┐
│                                                   │
│  High (80-100%)   ████████████████████  45       │
│  Med (50-79%)     ███████████████████   120      │
│  Low (0-49%)      ████████████          85       │
│                                                   │
│  Avg Importance: 62%                             │
└───────────────────────────────────────────────────┘
```

### 6. Recency Heatmap (Calendar View)
```
┌─ Activity Heatmap ────────────────────────────────┐
│                                                   │
│  Mar 2026                                         │
│  Su Mo Tu We Th Fr Sa                             │
│   ·  ·  ·  1  2  3  4  ← Light (few memories)    │
│   5  6  7  8  9 10 11                             │
│  12 13 14 15 16 17 18  ← Darker = more active    │
│  19 20 21 22 23 24 25                             │
│  26 27 28 29 30 31  ·                             │
│                                                   │
│  Most Active: Mar 12 (23 memories)               │
└───────────────────────────────────────────────────┘
```

### 7. Tag-Quadrant Matrix (Heatmap)
```
┌─ Tags × Quadrants ────────────────────────────────┐
│                                                   │
│           Coding  Personal  Research  AI         │
│  python     ████      █        █       ░        │
│  security   ████      ░       ███      ░        │
│  learning    ██      ███      ███      █        │
│  ai         ████      ░        █      ████      │
│                                                   │
│  █ = High occurrence  ░ = Low/None               │
└───────────────────────────────────────────────────┘
```

### 8. Source Distribution
```
┌─ Memory Sources ──────────────────────────────────┐
│                                                   │
│  Obsidian Vault   ████████████████████████  85%  │
│  Direct Input     ████                      10%  │
│  API/Integrations ██                        5%   │
│                                                   │
│  Top Files:                                      │
│  1. Security Guide.md (45 memories)              │
│  2. Learning Notes.md (32 memories)              │
│  3. Project Ideas.md (28 memories)               │
└───────────────────────────────────────────────────┘
```

## New API Endpoints

```python
# GET /api/stats/detailed
{
  "quadrants": {
    "coding": {"count": 234, "percent": 45},
    "personal": {"count": 78, "percent": 15},
    "research": {"count": 156, "percent": 30},
    "ai_instructions": {"count": 52, "percent": 10}
  },
  "tags": {
    "python": 45,
    "security": 32,
    "learning": 24,
    # ... top 50
  },
  "types": {
    "raw": 312,
    "consolidated": 182,
    "reflection": 26
  },
  "importance": {
    "high": 45,    # 80-100%
    "medium": 120, # 50-79%
    "low": 85      # 0-49%
  },
  "timeline": [
    {"date": "2026-03-01", "count": 5},
    {"date": "2026-03-02", "count": 12},
    # ... last 30 days
  ],
  "sources": {
    "obsidian": {"count": 450, "percent": 85},
    "direct": {"count": 53, "percent": 10},
    "api": {"count": 26, "percent": 5}
  },
  "tag_quadrant_matrix": {
    "python": {"coding": 40, "personal": 2, "research": 3, "ai": 0},
    # ...
  }
}
```

## Implementation Plan

### Phase 1: Core Charts
1. Add Chart.js CDN to dashboard
2. Create `/api/stats/detailed` endpoint
3. Add quadrant donut chart
4. Add tag bar chart
5. Add type pie chart

### Phase 2: Timeline & Activity
1. Add ingestion timeline chart
2. Add importance histogram
3. Add activity heatmap

### Phase 3: Advanced
1. Add tag-quadrant matrix
2. Add source distribution
3. Add top files list

## Layout (New Tab: "Analytics")

```
┌─ MemCore Dashboard ──────────────────────────────┐
│                                                   │
│  [Overview] [Memories] [Analytics] [Logs]        │
│                                                   │
├─ Analytics ──────────────────────────────────────┤
│                                                   │
│  ROW 1: [Quadrant Donut] [Type Pie]              │
│                                                   │
│  ROW 2: [Tag Bar Chart]                          │
│                                                   │
│  ROW 3: [Timeline Chart] [Importance Histogram]  │
│                                                   │
│  ROW 4: [Activity Heatmap]                       │
│                                                   │
│  ROW 5: [Tag-Quadrant Matrix]                    │
│                                                   │
│  ROW 6: [Source Distribution] [Top Files]        │
│                                                   │
└───────────────────────────────────────────────────┘
```
