"""
Consolidate Export Skill - Export AI-generated knowledge to dataCrystal/consolidated/

This creates portable knowledge modules that can be shared with other MemCore instances.
Uses git to track how knowledge evolves over time.

Usage: /consolidate_export [--quadrant=coding] [--topic=python]
"""
import os
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path


class ConsolidateExportSkill:
    """
    Skill for exporting consolidated AI knowledge.

    Creates structured markdown files in dataCrystal/consolidated/
    with full git history tracking.

    Usage:
      /consolidate_export                    # Export all quadrants
      /consolidate_export --quadrant=coding  # Export only coding quadrant
      /consolidate_export --topic=python     # Export specific topic
    """

    def __init__(self, vector_store, graph_store, llm, data_dir: str):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm = llm
        self.data_dir = Path(data_dir)
        self.consolidated_dir = self.data_dir / "consolidated"

    async def execute(
        self,
        quadrant: Optional[str] = None,
        topic: Optional[str] = None,
        commit_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export consolidated knowledge.

        Args:
            quadrant: Filter to specific quadrant (coding/personal/research/ai_instructions)
            topic: Filter to specific topic
            commit_message: Custom git commit message
        """
        try:
            # Ensure consolidated directory exists
            self.consolidated_dir.mkdir(parents=True, exist_ok=True)

            # Initialize git if not present
            git_initialized = self._init_git()

            # Get reflections and consolidated memories
            memories = await self._get_consolidated_memories(quadrant, topic)

            if not memories:
                return {
                    "success": True,
                    "files_created": 0,
                    "message": "No consolidated memories found to export."
                }

            # Group by quadrant and theme
            grouped = self._group_by_theme(memories)

            # Generate files
            files_created = []
            for (quad, theme), items in grouped.items():
                file_path = await self._generate_markdown_file(quad, theme, items)
                files_created.append(str(file_path))

            # Git commit
            if git_initialized and files_created:
                commit_hash = self._git_commit(commit_message or f"Consolidated export {datetime.now().isoformat()}")
            else:
                commit_hash = None

            return {
                "success": True,
                "files_created": len(files_created),
                "file_paths": files_created,
                "git_commit": commit_hash,
                "git_initialized": git_initialized,
                "export_location": str(self.consolidated_dir),
                "message": f"Exported {len(files_created)} files to dataCrystal/consolidated/"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _init_git(self) -> bool:
        """Initialize git repo in consolidated directory if not present."""
        git_dir = self.consolidated_dir / ".git"

        if not git_dir.exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=self.consolidated_dir,
                    check=True,
                    capture_output=True
                )
                # Configure git (required for commits)
                subprocess.run(
                    ["git", "config", "user.email", "memcore@local"],
                    cwd=self.consolidated_dir,
                    check=True,
                    capture_output=True
                )
                subprocess.run(
                    ["git", "config", "user.name", "MemCore"],
                    cwd=self.consolidated_dir,
                    check=True,
                    capture_output=True
                )
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Git not available
                return False

        return True

    def _git_commit(self, message: str) -> Optional[str]:
        """Commit changes to git."""
        try:
            # Add all changes
            subprocess.run(
                ["git", "add", "."],
                cwd=self.consolidated_dir,
                check=True,
                capture_output=True
            )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.consolidated_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.consolidated_dir,
                    capture_output=True,
                    text=True
                )
                return hash_result.stdout.strip()[:8]

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    async def _get_consolidated_memories(
        self,
        quadrant: Optional[str],
        topic: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get consolidated/reflection memories from storage."""
        # Get all memories
        all_memories = self.vector_store.get_all_memories(limit=10000)

        # Filter to reflections and consolidated types
        consolidated = []
        for mem in all_memories:
            payload = mem.payload
            mem_type = payload.get("type", "raw")

            # Include reflections and consolidated memories
            if mem_type not in ["reflection", "consolidated", "instruction"]:
                continue

            # Filter by quadrant
            if quadrant:
                mem_quadrants = payload.get("quadrants", ["general"])
                if quadrant not in mem_quadrants:
                    continue

            # Filter by topic (simple keyword match)
            if topic:
                content = payload.get("content", "")
                summary = payload.get("summary", "")
                if topic.lower() not in (content + summary).lower():
                    continue

            consolidated.append({
                "id": str(mem.id),
                "type": mem_type,
                "summary": payload.get("summary", ""),
                "content": payload.get("content", ""),
                "quadrants": payload.get("quadrants", ["general"]),
                "importance": payload.get("importance", 0.5),
                "confidence": payload.get("confidence", "medium"),
                "created_at": payload.get("created_at"),
                "tags": payload.get("tags", []),
                "sources": self._get_source_memories(str(mem.id))
            })

        return consolidated

    def _get_source_memories(self, memory_id: str) -> List[str]:
        """Get source memories for a reflection."""
        # Query graph for DERIVED_FROM edges
        try:
            edges = self.graph_store.get_edges_from(memory_id, edge_type="DERIVED_FROM")
            return [edge["target"] for edge in edges]
        except:
            return []

    def _group_by_theme(self, memories: List[Dict[str, Any]]) -> Dict[tuple, List[Dict]]:
        """Group memories by quadrant and theme."""
        from collections import defaultdict
        grouped = defaultdict(list)

        for mem in memories:
            quadrant = mem["quadrants"][0] if mem["quadrants"] else "general"

            # Extract theme from tags or infer from content
            theme = self._extract_theme(mem)

            grouped[(quadrant, theme)].append(mem)

        return grouped

    def _extract_theme(self, memory: Dict[str, Any]) -> str:
        """Extract theme from memory tags or content."""
        # Use first relevant tag as theme
        tags = memory.get("tags", [])
        skip_tags = ["reflection", "consolidated", "instruction", "memory"]

        for tag in tags:
            if tag not in skip_tags:
                return tag

        # Infer from content keywords
        content = memory.get("content", "").lower()
        summary = memory.get("summary", "").lower()
        text = content + " " + summary

        # Simple keyword matching for themes
        theme_keywords = {
            "python": ["python", "py ", "pip", "django", "flask", "fastapi"],
            "javascript": ["javascript", "js", "node", "react", "vue", "angular"],
            "api": ["api", "rest", "graphql", "endpoint"],
            "database": ["database", "sql", "postgres", "mongodb", "redis"],
            "async": ["async", "await", "concurrent", "threading"],
            "testing": ["test", "pytest", "unittest", "mock"],
            "architecture": ["architecture", "pattern", "microservice", "design"],
            "devops": ["docker", "kubernetes", "ci/cd", "deploy", "aws"],
            "workflow": ["workflow", "process", "habit", "routine"],
            "learning": ["learn", "study", "course", "tutorial"]
        }

        for theme, keywords in theme_keywords.items():
            if any(kw in text for kw in keywords):
                return theme

        return "general"

    async def _generate_markdown_file(
        self,
        quadrant: str,
        theme: str,
        memories: List[Dict[str, Any]]
    ) -> Path:
        """Generate a consolidated markdown file."""
        # Create quadrant directory
        quad_dir = self.consolidated_dir / quadrant
        quad_dir.mkdir(exist_ok=True)

        # File path
        file_path = quad_dir / f"{theme}.md"

        # Generate content
        content_lines = ["---"]
        content_lines.append(f"type: consolidated")
        content_lines.append(f"quadrant: {quadrant}")
        content_lines.append(f"theme: {theme}")
        content_lines.append(f"generated_at: {datetime.now().isoformat()}")
        content_lines.append(f"memory_count: {len(memories)}")
        content_lines.append("---")
        content_lines.append("")
        content_lines.append(f"# {theme.replace('-', ' ').title()} - {quadrant.title()}")
        content_lines.append("")

        # Sort by importance
        sorted_mems = sorted(memories, key=lambda m: m["importance"], reverse=True)

        for mem in sorted_mems:
            content_lines.append(f"## {mem['summary']}")
            content_lines.append("")
            content_lines.append(f"{mem['content']}")
            content_lines.append("")

            # Provenance
            content_lines.append("### Provenance")
            content_lines.append(f"- **Type**: {mem['type']}")
            content_lines.append(f"- **Memory ID**: `{mem['id']}`")
            content_lines.append(f"- **Created**: {mem['created_at']}")
            content_lines.append(f"- **Importance**: {mem['importance']}")
            content_lines.append(f"- **Confidence**: {mem['confidence']}")

            if mem.get("tags"):
                content_lines.append(f"- **Tags**: {', '.join(mem['tags'])}")

            if mem.get("sources"):
                content_lines.append(f"- **Source Memories**: {', '.join(f'`{s}`' for s in mem['sources'])}")

            content_lines.append("")
            content_lines.append("---")
            content_lines.append("")

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))

        return file_path

    def get_help(self) -> str:
        return """
/consolidate_export [--quadrant=NAME] [--topic=KEYWORD] [--message="commit msg"]

Export AI-generated consolidated knowledge to dataCrystal/consolidated/
for portability to other MemCore instances.

Creates structured markdown with full provenance and git history.

Options:
  --quadrant  Filter to specific quadrant (coding/personal/research/ai_instructions)
  --topic     Filter to specific topic/keyword
  --message   Custom git commit message

Examples:
  /consolidate_export
  /consolidate_export --quadrant=coding
  /consolidate_export --topic=python
  /consolidate_export --quadrant=coding --topic=async
"""
