"""
MemCore Status Reporter - Generates beautiful HTML reports of memory statistics.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class HTMLReporter:
    """Generates beautiful HTML status reports for MemCore."""
    
    def __init__(self, output_dir: str = "dataCrystal/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.history_file = os.path.join(output_dir, "history.json")
        self._load_history()
    
    def _load_history(self):
        """Load historical data for charts."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            except:
                self.history = []
        else:
            self.history = []
    
    def _save_history(self, vector_stats: Dict[str, Any], graph_stats: Dict[str, Any]):
        """Save current stats to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "total_memories": vector_stats.get("total_memories", 0),
            "total_nodes": graph_stats.get("total_nodes", 0),
            "total_edges": graph_stats.get("total_edges", 0)
        }
        self.history.append(entry)
        # Keep only last 24 entries (24 hours)
        self.history = self.history[-24:]
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)
    
    def _generate_chart_svg(self, data: List[Dict], key: str, color: str) -> str:
        """Generate a sparkline SVG chart."""
        if len(data) < 2:
            return ""
        
        values = [d[key] for d in data]
        max_val = max(values) if max(values) > 0 else 1
        min_val = min(values)
        
        width = 200
        height = 60
        padding = 5
        
        # Generate points
        points = []
        for i, val in enumerate(values):
            x = padding + (i / (len(values) - 1)) * (width - 2 * padding)
            y = height - padding - ((val - min_val) / (max_val - min_val)) * (height - 2 * padding) if max_val != min_val else height / 2
            points.append(f"{x},{y}")
        
        path_d = f"M{points[0]} " + " ".join([f"L{p}" for p in points[1:]])
        
        # Create area path
        area_d = f"M{padding},{height-padding} L{points[0]} " + " ".join([f"L{p}" for p in points[1:]]) + f" L{width-padding},{height-padding} Z"
        
        return f'''<svg viewBox="0 0 {width} {height}" class="sparkline">
            <defs>
                <linearGradient id="grad_{key}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:{color};stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:{color};stop-opacity:0" />
                </linearGradient>
            </defs>
            <path d="{area_d}" fill="url(#grad_{key})" />
            <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <circle cx="{points[-1].split(',')[0]}" cy="{points[-1].split(',')[1]}" r="3" fill="{color}" />
        </svg>'''
    
    def _get_quadrant_icon(self, quadrant: str) -> str:
        """Get SVG icon for quadrant."""
        icons = {
            "coding": "<path d='M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z'/>",
            "personal": "<path d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/>",
            "research": "<path d='M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z'/>",
            "ai_instructions": "<path d='M21 11.18V9.72c0-1.74-1.1-3.3-2.75-3.87l-1.9-.64c-.66-.22-1.12-.83-1.12-1.53V3c0-1.1-.9-2-2-2H9.99c-1.1 0-2 .9-2 2v.68c0 .7-.46 1.31-1.12 1.53l-1.9.64C3.1 6.42 2 7.98 2 9.72v1.46c0 1.38.78 2.66 2.03 3.28l1.1.55c.68.34 1.11 1.04 1.11 1.8v.18c0 1.66 1.34 3 3 3h5c1.66 0 3-1.34 3-3v-.18c0-.76.43-1.46 1.11-1.8l1.1-.55c1.25-.62 2.03-1.9 2.03-3.28zM12 7c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3z'/><path d='M12 14c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zm0 8c-1.65 0-3-1.35-3-3s1.35-3 3-3 3 1.35 3 3-1.35 3-3 3z'/>",
            "general": "<path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z'/>"
        }
        return icons.get(quadrant, icons["general"])
    
    def _get_memory_type_icon(self, mem_type: str) -> str:
        """Get icon for memory type."""
        icons = {
            "raw": "📝",
            "archived_raw": "📦",
            "consolidated": "🧠",
            "fact": "📚",
            "sop": "📋",
            "unknown": "❓"
        }
        return icons.get(mem_type, "📄")
    
    def generate_report(self, vector_stats: Dict[str, Any], graph_stats: Dict[str, Any], 
                        queue_stats: Optional[Dict[str, Any]] = None) -> str:
        """Generate beautiful HTML report with memory statistics."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to history for charts
        self._save_history(vector_stats, graph_stats)
        queue_stats = queue_stats or {}
        
        # Build quadrant breakdown with progress bars
        total_memories = vector_stats.get("total_memories", 0) or 1  # Avoid division by zero
        quadrant_data = sorted(vector_stats.get("by_quadrant", {}).items(), key=lambda x: x[1], reverse=True)
        quadrant_colors = {
            "coding": "#3b82f6",
            "personal": "#ec4899", 
            "research": "#8b5cf6",
            "ai_instructions": "#10b981",
            "general": "#6b7280"
        }
        
        quadrant_html = ""
        for quad, count in quadrant_data:
            percentage = (count / total_memories) * 100
            color = quadrant_colors.get(quad, "#6b7280")
            icon = self._get_quadrant_icon(quad)
            quadrant_html += f'''
            <div class="stat-row">
                <div class="stat-icon" style="background: {color}20; color: {color}">
                    <svg viewBox="0 0 24 24" width="20" height="20">{icon}</svg>
                </div>
                <div class="stat-info">
                    <div class="stat-header">
                        <span class="stat-label">{quad}</span>
                        <span class="stat-value">{count}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {percentage:.1f}%; background: {color}"></div>
                    </div>
                </div>
            </div>'''
        
        # Build memory type breakdown
        type_data = sorted(vector_stats.get("by_type", {}).items(), key=lambda x: x[1], reverse=True)
        type_colors = {"raw": "#f59e0b", "archived_raw": "#6b7280", "consolidated": "#10b981", "fact": "#3b82f6", "sop": "#8b5cf6"}
        
        type_html = ""
        for mem_type, count in type_data:
            percentage = (count / total_memories) * 100
            color = type_colors.get(mem_type, "#6b7280")
            icon = self._get_memory_type_icon(mem_type)
            type_html += f'''
            <div class="stat-row">
                <div class="stat-icon" style="background: {color}20; color: {color}; font-size: 1.2rem;">{icon}</div>
                <div class="stat-info">
                    <div class="stat-header">
                        <span class="stat-label">{mem_type}</span>
                        <span class="stat-value">{count}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {percentage:.1f}%; background: {color}"></div>
                    </div>
                </div>
            </div>'''
        
        # Build graph node breakdown
        node_data = sorted(graph_stats.get("nodes_by_type", {}).items(), key=lambda x: x[1], reverse=True)
        node_html = ""
        node_icons = {"memory": "🧠", "request": "📨", "fact": "📚", "sop": "📋"}
        for node_type, count in node_data:
            icon = node_icons.get(node_type, "📍")
            node_html += f'''
            <div class="mini-stat">
                <span class="mini-icon">{icon}</span>
                <span class="mini-label">{node_type}</span>
                <span class="mini-value">{count}</span>
            </div>'''
        
        # Calculate stats
        total_memories = vector_stats.get("total_memories", 0)
        total_nodes = graph_stats.get("total_nodes", 0)
        total_edges = graph_stats.get("total_edges", 0)
        dimension = vector_stats.get("dimension", "N/A")
        collection = vector_stats.get("collection_name", "N/A")
        last_consolidation = graph_stats.get("last_consolidation", "Never")
        db_path = graph_stats.get("db_path", "N/A")
        
        # Format last consolidation
        if last_consolidation != "Never":
            try:
                last_dt = datetime.fromisoformat(last_consolidation.replace('Z', '+00:00'))
                hours_ago = (datetime.now() - last_dt.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago < 1:
                    last_consolidation_fmt = "Just now"
                elif hours_ago < 24:
                    last_consolidation_fmt = f"{int(hours_ago)}h ago"
                else:
                    last_consolidation_fmt = f"{int(hours_ago/24)}d ago"
            except:
                last_consolidation_fmt = last_consolidation
        else:
            last_consolidation_fmt = "Never"
        
        # Generate sparkline charts
        memories_chart = self._generate_chart_svg(self.history, "total_memories", "#6366f1")
        nodes_chart = self._generate_chart_svg(self.history, "total_nodes", "#8b5cf6")
        
        # Calculate growth rates
        if len(self.history) >= 2:
            prev = self.history[-2]
            curr = self.history[-1]
            mem_growth = curr["total_memories"] - prev["total_memories"]
            growth_indicator = f"<span class='trend {'up' if mem_growth >= 0 else 'down'}'>{'+' if mem_growth >= 0 else ''}{mem_growth} since last hour</span>"
        else:
            growth_indicator = "<span class='trend'>No historical data yet</span>"
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemCore Dashboard</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        :root {{
            --bg-primary: #0f0f1a;
            --bg-secondary: rgba(30, 30, 50, 0.6);
            --bg-card: rgba(40, 40, 60, 0.4);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-tertiary: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: rgba(255, 255, 255, 0.08);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 20% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(236, 72, 153, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(139, 92, 246, 0.08) 0%, transparent 60%);
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* Header */
        header {{
            margin-bottom: 2.5rem;
            padding: 2rem;
            background: var(--bg-secondary);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            border: 1px solid var(--border);
            position: relative;
            overflow: hidden;
        }}
        
        header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        }}
        
        .header-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
        }}
        
        .brand {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .logo {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-tertiary));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            box-shadow: 0 8px 32px rgba(99, 102, 241, 0.3);
        }}
        
        .brand-text h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--accent-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .brand-text p {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }}
        
        .header-meta {{
            text-align: right;
        }}
        
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border-radius: 100px;
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }}
        
        .status-badge::before {{
            content: '';
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .timestamp {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        
        /* Grid Layout */
        .grid {{
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 1.5rem;
        }}
        
        .card {{
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            border: 1px solid var(--border);
            padding: 1.5rem;
            transition: all 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }}
        
        .card-title {{
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }}
        
        .card-icon {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}
        
        /* Big Number Cards */
        .metric-card {{
            grid-column: span 4;
        }}
        
        .metric-card.primary {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
        }}
        
        .metric-card.secondary {{
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(236, 72, 153, 0.1));
        }}
        
        .metric-card.tertiary {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.1));
        }}
        
        .big-number {{
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--accent-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1;
            margin-bottom: 0.5rem;
        }}
        
        .metric-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
        }}
        
        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .trend {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        .trend.up {{
            color: var(--success);
        }}
        
        .trend.down {{
            color: var(--error);
        }}
        
        /* Sparkline */
        .sparkline-container {{
            margin-top: 1rem;
            height: 60px;
            opacity: 0.7;
        }}
        
        .sparkline {{
            width: 100%;
            height: 100%;
        }}
        
        /* List Cards */
        .list-card {{
            grid-column: span 4;
            min-height: 320px;
        }}
        
        .stat-row {{
            display: flex;
            align-items: center;
            gap: 0.875rem;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .stat-row:last-child {{
            border-bottom: none;
        }}
        
        .stat-icon {{
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}
        
        .stat-info {{
            flex: 1;
            min-width: 0;
        }}
        
        .stat-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.375rem;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
            text-transform: capitalize;
        }}
        
        .stat-value {{
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .progress-bar {{
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.6s ease;
        }}
        
        /* Mini Stats Grid */
        .mini-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
            margin-top: 0.5rem;
        }}
        
        .mini-stat {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            font-size: 0.85rem;
        }}
        
        .mini-icon {{
            font-size: 1.1rem;
        }}
        
        .mini-label {{
            color: var(--text-secondary);
            flex: 1;
            text-transform: capitalize;
        }}
        
        .mini-value {{
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* Info Card */
        .info-card {{
            grid-column: span 4;
        }}
        
        .info-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .info-item:last-child {{
            border-bottom: none;
        }}
        
        .info-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .info-value {{
            font-family: 'SF Mono', monospace;
            font-size: 0.85rem;
            color: var(--accent-primary);
            background: rgba(99, 102, 241, 0.1);
            padding: 0.25rem 0.75rem;
            border-radius: 6px;
        }}
        
        /* Auto-refresh banner */
        .refresh-banner {{
            grid-column: span 12;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            padding: 1rem;
            background: linear-gradient(90deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1), rgba(236, 72, 153, 0.1));
            border-radius: 12px;
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
        }}
        
        .refresh-icon {{
            animation: spin 8s linear infinite;
        }}
        
        @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Footer */
        footer {{
            margin-top: 3rem;
            padding: 2rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
            border-top: 1px solid var(--border);
        }}
        
        footer p {{
            margin: 0.25rem 0;
        }}
        
        .footer-links {{
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin-top: 1rem;
        }}
        
        .footer-links a {{
            color: var(--accent-primary);
            text-decoration: none;
            transition: color 0.2s;
        }}
        
        .footer-links a:hover {{
            color: var(--accent-tertiary);
        }}
        
        /* Responsive */
        @media (max-width: 1024px) {{
            .metric-card, .list-card, .info-card {{
                grid-column: span 6;
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}
            
            .metric-card, .list-card, .info-card {{
                grid-column: span 12;
            }}
            
            .header-content {{
                flex-direction: column;
                text-align: center;
            }}
            
            .header-meta {{
                text-align: center;
            }}
            
            .big-number {{
                font-size: 2.5rem;
            }}
        }}
        
        /* Empty state */
        .empty-state {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
        }}
        
        .empty-state-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            opacity: 0.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <div class="brand">
                    <div class="logo">🧠</div>
                    <div class="brand-text">
                        <h1>MemCore Dashboard</h1>
                        <p>Agentic Memory Management System</p>
                    </div>
                </div>
                <div class="header-meta">
                    <div class="status-badge">System Online</div>
                    <div class="timestamp">Last Updated: {timestamp}</div>
                </div>
            </div>
        </header>
        
        <div class="grid">
            <!-- Main Metrics -->
            <div class="card metric-card primary">
                <div class="card-header">
                    <span class="card-title">Total Memories</span>
                    <div class="card-icon" style="background: rgba(99, 102, 241, 0.2);">💎</div>
                </div>
                <div class="big-number">{total_memories:,}</div>
                <div class="metric-meta">
                    <span class="metric-label">Stored vectors</span>
                    {growth_indicator}
                </div>
                <div class="sparkline-container">{memories_chart}</div>
            </div>
            
            <div class="card metric-card secondary">
                <div class="card-header">
                    <span class="card-title">Graph Nodes</span>
                    <div class="card-icon" style="background: rgba(139, 92, 246, 0.2);">🕸️</div>
                </div>
                <div class="big-number">{total_nodes:,}</div>
                <div class="metric-meta">
                    <span class="metric-label">Connected entities</span>
                </div>
                <div class="sparkline-container">{nodes_chart}</div>
            </div>
            
            <div class="card metric-card tertiary">
                <div class="card-header">
                    <span class="card-title">Relationships</span>
                    <div class="card-icon" style="background: rgba(16, 185, 129, 0.2);">🔗</div>
                </div>
                <div class="big-number">{total_edges:,}</div>
                <div class="metric-meta">
                    <span class="metric-label">Graph edges</span>
                </div>
            </div>
            
            <!-- Queue Stats -->
            <div class="card metric-card" style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(239, 68, 68, 0.1));">
                <div class="card-header">
                    <span class="card-title">Queue Status</span>
                    <div class="card-icon" style="background: rgba(245, 158, 11, 0.2);">⏳</div>
                </div>
                <div class="big-number" style="font-size: 2.5rem;">{queue_stats.get('pending', 0)}</div>
                <div class="metric-meta">
                    <span class="metric-label">Pending jobs</span>
                    <span class="trend">{queue_stats.get('processing', 0)} processing</span>
                </div>
                <div class="mini-stats" style="margin-top: 0.75rem; grid-template-columns: repeat(3, 1fr);">
                    <div class="mini-stat">
                        <span class="mini-icon">✅</span>
                        <span class="mini-value" style="color: var(--success);">{queue_stats.get('completed', 0)}</span>
                    </div>
                    <div class="mini-stat">
                        <span class="mini-icon">❌</span>
                        <span class="mini-value" style="color: var(--error);">{queue_stats.get('failed', 0)}</span>
                    </div>
                    <div class="mini-stat">
                        <span class="mini-icon">🔄</span>
                        <span class="mini-value" style="color: var(--warning);">{queue_stats.get('retrying', 0)}</span>
                    </div>
                </div>
            </div>
            
            <!-- Quadrant Breakdown -->
            <div class="card list-card">
                <div class="card-header">
                    <span class="card-title">By Quadrant</span>
                    <div class="card-icon" style="background: rgba(59, 130, 246, 0.2);">🎯</div>
                </div>
                {quadrant_html or '<div class="empty-state"><div class="empty-state-icon">📭</div><p>No quadrant data</p></div>'}
            </div>
            
            <!-- Memory Types -->
            <div class="card list-card">
                <div class="card-header">
                    <span class="card-title">Memory Types</span>
                    <div class="card-icon" style="background: rgba(245, 158, 11, 0.2);">📚</div>
                </div>
                {type_html or '<div class="empty-state"><div class="empty-state-icon">📭</div><p>No type data</p></div>'}
            </div>
            
            <!-- Graph Node Types -->
            <div class="card list-card">
                <div class="card-header">
                    <span class="card-title">Graph Structure</span>
                    <div class="card-icon" style="background: rgba(236, 72, 153, 0.2);">🕸️</div>
                </div>
                <div class="mini-stats">
                    {node_html or '<div class="empty-state" style="grid-column: span 2;"><div class="empty-state-icon">📭</div><p>No graph data</p></div>'}
                </div>
            </div>
            
            <!-- System Info -->
            <div class="card info-card">
                <div class="card-header">
                    <span class="card-title">System Configuration</span>
                    <div class="card-icon" style="background: rgba(16, 185, 129, 0.2);">⚙️</div>
                </div>
                <div class="info-item">
                    <span class="info-label">Vector Dimension</span>
                    <span class="info-value">{dimension}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Collection</span>
                    <span class="info-value">{collection}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Last Consolidation</span>
                    <span class="info-value">{last_consolidation_fmt}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Database</span>
                    <span class="info-value" style="font-size: 0.7rem; max-width: 150px; overflow: hidden; text-overflow: ellipsis;">{os.path.basename(db_path) if db_path else "N/A"}</span>
                </div>
            </div>
            
            <div class="card info-card">
                <div class="card-header">
                    <span class="card-title">Quick Links</span>
                    <div class="card-icon" style="background: rgba(99, 102, 241, 0.2);">🔗</div>
                </div>
                <div class="info-item">
                    <span class="info-label">Health Check</span>
                    <a href="/health" class="info-value" style="text-decoration: none;">/health →</a>
                </div>
                <div class="info-item">
                    <span class="info-label">MCP Endpoint</span>
                    <a href="/mcp" class="info-value" style="text-decoration: none;">/mcp →</a>
                </div>
            </div>
            
            <div class="card info-card">
                <div class="card-header">
                    <span class="card-title">Documentation</span>
                    <div class="card-icon" style="background: rgba(139, 92, 246, 0.2);">📖</div>
                </div>
                <div class="info-item">
                    <span class="info-label">API Reference</span>
                    <a href="docs/api-specification.md" class="info-value" style="text-decoration: none;">View →</a>
                </div>
                <div class="info-item">
                    <span class="info-label">Core Concepts</span>
                    <a href="docs/core-concepts.md" class="info-value" style="text-decoration: none;">View →</a>
                </div>
                <div class="info-item">
                    <span class="info-label">Architecture</span>
                    <a href="docs/research-memcore-architecture.md" class="info-value" style="text-decoration: none;">View →</a>
                </div>
            </div>
            
            <!-- Refresh Banner -->
            <div class="refresh-banner">
                <span class="refresh-icon">🔄</span>
                <span>Auto-refreshes every hour • Historical data tracked for 24 hours</span>
            </div>
        </div>
        
        <footer>
            <p><strong>MemCore</strong> — Agentic Memory Management System</p>
            <p>Vector Store: {collection} • Graph: SQLite</p>
            <div class="footer-links">
                <a href="https://github.com/memcore" target="_blank">GitHub</a>
                <a href="docs/README.md">Documentation</a>
                <a href="#" onclick="window.location.reload();">Refresh Now</a>
            </div>
        </footer>
    </div>
    
    <script>
        // Auto-refresh every hour
        setTimeout(() => {{
            window.location.reload();
        }}, 60 * 60 * 1000);
        
        // Animate progress bars on load
        document.addEventListener('DOMContentLoaded', () => {{
            const progressBars = document.querySelectorAll('.progress-fill');
            progressBars.forEach(bar => {{
                const width = bar.style.width;
                bar.style.width = '0';
                setTimeout(() => {{
                    bar.style.width = width;
                }}, 100);
            }});
        }});
    </script>
</body>
</html>'''
        return html
    
    def save_report(self, vector_stats: Dict[str, Any], graph_stats: Dict[str, Any],
                    queue_stats: Optional[Dict[str, Any]] = None) -> str:
        """Generate and save HTML report. Returns the file path."""
        html = self.generate_report(vector_stats, graph_stats, queue_stats)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memcore_status_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)
        latest_path = os.path.join(self.output_dir, "latest.html")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        with open(latest_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"[Reporter] Status report saved: {latest_path}")
        return latest_path
