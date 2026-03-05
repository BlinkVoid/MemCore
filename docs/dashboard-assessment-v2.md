# MemCore Dashboard Assessment v2

## User Goals (Corrected Understanding)

**Primary Purpose:** Daily 5-minute trust-building health check
**Not For:** Deep content browsing (Obsidian handles that)
**Key Need:** "Is MemCore working correctly? What does it know?"

---

## Current Dashboard: Wrong Design

### Problem 1: Memory List is Centerpiece
- **Current:** Big memory list dominates the screen
- **Issue:** User doesn't need to browse memories here - they have Obsidian
- **Should be:** "What's the health/status?" summary

### Problem 2: No "Daily Digest" View
- **Missing:** "What happened today?" summary
- **Need:** Grouped timeline showing:
  - X new memories ingested today
  - Y consolidated into LTM
  - Z conflicts found
  - Last consolidation: N hours ago

### Problem 3: No Health Traffic Lights
- **Missing:** At-a-glance system health
- **Need:** Simple indicators:
  - Consolidation queue: 🟢🟡🔴
  - Storage health: 🟢🟡🔴
  - API status: 🟢🔴
  - Last successful operation timestamp

### Problem 4: Stats Don't Build Trust
- **Current:** Raw counts (Total memories: 234)
- **Need:** Trend indicators:
  - "+12 memories today" (with sparkline)
  - "Consolidation: 94% success rate (7 days)"
  - "Avg time to consolidate: 2.3 hours"

### Problem 5: Activity Log is Noise
- **Current:** Raw logs of every API call
- **Need:** Curated "What Changed" timeline:
  - Morning digest style
  - Grouped by day
  - Highlight anomalies (errors, conflicts)

---

## Recommended Redesign: "Daily Health Dashboard"

### Layout: Top-to-Bottom Priority

#### 1. HEALTH STATUS BAR (top, always visible)
```
┌─────────────────────────────────────────────────────────────┐
│ 🟢 System Healthy    🟢 Queue Clear    🟢 API Online       │
│ Last check: 2 min ago    Next consolidation: in 3 hours     │
└─────────────────────────────────────────────────────────────┘
```

#### 2. TODAY'S DIGEST (main focus)
```
┌─ TODAY (March 5) ──────────────────────────────────────────┐
│                                                             │
│  📥 Ingested: 5 memories     [=========>          ] +12%   │
│  🔄 Consolidated: 3          [================] Done        │
│  ⚠️  Conflicts: 1 (needs review)                           │
│                                                             │
│  Latest: "Application Security Guide" consolidated (14:32) │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3. TRUST METRICS (7-day trends)
```
┌─ Trust Indicators ─────────────────────────────────────────┐
│                                                             │
│  Consolidation Success Rate:  ████████████████████  94%    │
│  Avg Consolidation Time:      ▓▓▓▓▓▓▓▓░░░░░░░░░░░  2.3h   │
│  Orphaned Memories:           ░░░░░░░░░░░░░░░░░░░░  0 ✅    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 4. KNOWLEDGE OVERVIEW (what MemCore knows)
```
┌─ Knowledge Distribution ───────────────────────────────────┐
│                                                             │
│  Coding (45%)     ████████████████████ research (30%)      │
│  Personal (15%)   ███████ ai_instructions (10%)            │
│                                                             │
│  Top themes this week: #security, #python, #learning       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 5. ACTION REQUIRED (only if needed)
```
┌─ Attention Needed ─────────────────────────────────────────┐
│                                                             │
│  🔴 3 jobs failed (last error: API timeout)                │
│  🟡 12 memories untagged (may affect search)               │
│  🟡 2 conflicts detected (click to review)                 │
│                                                             │
│  [Retry Failed]  [Review Conflicts]  [Ignore]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 6. RECENT HISTORY (collapsed by default)
```
┌─ History ──────────────────────────────────────────────────┐
│  [+ Expand to see last 7 days]                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Missing Features

### 1. Daily Comparison
- "+5 memories vs yesterday" trend
- Sparklines for each quadrant
- Weekly/daily toggle

### 2. Anomaly Detection
- "Consolidation hasn't run in 12 hours" alert
- "API failures increased 400%" warning
- "Storage at 85%" warning

### 3. Quick Actions
- "Trigger consolidation now" button
- "Export today's changes"
- "Force health check"

### 4. Confidence Scores
- For each quadrant: "High confidence" vs "Needs review"
- Based on: tag coverage, consolidation rate, conflict count

### 5. Mobile-Friendly
- Single column layout
- Swipe between days
- Notification-style cards

---

## What to REMOVE

1. **Memory list** - Not needed for daily check
2. **Search bar** - User uses Obsidian
3. **Individual memory cards** - Too detailed
4. **Raw logs** - Too noisy
5. **Weight visualization** - Too technical

---

## New API Endpoints Needed

```python
# GET /api/daily-digest?date=2026-03-05
{
  "date": "2026-03-05",
  "ingested_count": 5,
  "ingested_change": +2,  # vs yesterday
  "consolidated_count": 3,
  "consolidation_success_rate": 0.94,
  "conflicts_count": 1,
  "last_consolidation": "2026-03-05T14:32:00",
  "next_consolidation": "2026-03-05T22:00:00",
  "health_status": "healthy",  # healthy, warning, critical
  "top_quadrants": [...],
  "top_tags": [...],
  "alerts": [...]
}

# GET /api/health
{
  "overall": "healthy",  # healthy, warning, critical
  "checks": {
    "consolidation_queue": {"status": "healthy", "pending": 0},
    "storage": {"status": "healthy", "used_percent": 45},
    "llm_api": {"status": "healthy", "last_success": "..."},
    "vault_sync": {"status": "healthy", "last_sync": "..."}
  },
  "last_check": "2026-03-05T00:05:00"
}

# GET /api/trends?days=7
{
  "daily": [
    {"date": "...", "ingested": 5, "consolidated": 3, "success_rate": 1.0},
    ...
  ],
  "averages": {...}
}
```

---

## Implementation Priority

### Phase 1: Health-First View (This Week)
1. Replace memory list with daily digest
2. Add health status bar
3. Add trend sparklines
4. Simplify to single-column layout

### Phase 2: Trust Building (Next Week)
1. Add 7-day comparison
2. Add anomaly alerts
3. Add "Action Required" section
4. Add confidence scores

### Phase 3: Polish (Later)
1. Mobile optimization
2. Daily email digest option
3. Dark/light theme
4. Custom date range selection
