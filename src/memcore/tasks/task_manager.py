"""
Task Management System for MemCore

Provides todo/task tracking with priority weighting and intelligent reminders.
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class TaskPriority(Enum):
    """Task priority levels with weight values."""
    CRITICAL = "critical"  # Weight: 1.0 - Must be done ASAP
    HIGH = "high"          # Weight: 0.8 - Important, soon
    MEDIUM = "medium"      # Weight: 0.5 - Normal priority
    LOW = "low"            # Weight: 0.3 - Can wait
    BACKLOG = "backlog"    # Weight: 0.1 - Nice to have


class TaskStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a single task."""
    id: str
    title: str
    description: str
    priority: str
    status: str
    created_at: str
    updated_at: str
    due_date: Optional[str] = None
    tags: List[str] = None
    estimated_minutes: Optional[int] = None
    context: str = ""  # When/where this task should surface
    reminder_frequency: str = "auto"  # "auto", "daily", "weekly", "none"
    completed_at: Optional[str] = None
    completion_notes: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class TaskManager:
    """
    Manages tasks/todos with priority weighting and intelligent reminders.

    Tasks are stored in SQLite for fast querying, with optional
    sync to vector store for semantic search.
    """

    PRIORITY_WEIGHTS = {
        TaskPriority.CRITICAL.value: 1.0,
        TaskPriority.HIGH.value: 0.8,
        TaskPriority.MEDIUM.value: 0.5,
        TaskPriority.LOW.value: 0.3,
        TaskPriority.BACKLOG.value: 0.1,
    }

    def __init__(self, data_dir: str, vector_store=None):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "tasks.db"
        self.vector_store = vector_store

        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for tasks."""
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                updated_at TEXT,
                due_date TEXT,
                tags TEXT,  -- JSON array
                estimated_minutes INTEGER,
                context TEXT,
                reminder_frequency TEXT DEFAULT 'auto',
                completed_at TEXT,
                completion_notes TEXT
            )
        """)

        # Index for efficient queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON tasks(due_date)")

        conn.commit()
        conn.close()

    async def add_task(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
        estimated_minutes: Optional[int] = None,
        context: str = "",
        reminder_frequency: str = "auto"
    ) -> Dict[str, Any]:
        """
        Add a new task.

        Args:
            title: Task title/summary
            description: Detailed description
            priority: critical/high/medium/low/backlog
            due_date: ISO format date string (optional)
            tags: List of tags
            estimated_minutes: Time estimate
            context: Context for when to surface this task
            reminder_frequency: How often to remind
        """
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.PENDING.value,
            created_at=now,
            updated_at=now,
            due_date=due_date,
            tags=tags or [],
            estimated_minutes=estimated_minutes,
            context=context,
            reminder_frequency=reminder_frequency
        )

        # Save to SQLite
        self._save_task_to_db(task)

        # Also save to vector store for semantic search (optional)
        if self.vector_store:
            await self._index_task_in_vector_store(task)

        return {
            "success": True,
            "task_id": task_id,
            "task": asdict(task)
        }

    def _save_task_to_db(self, task: Task):
        """Save task to SQLite database."""
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO tasks VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            task.id,
            task.title,
            task.description,
            task.priority,
            task.status,
            task.created_at,
            task.updated_at,
            task.due_date,
            json.dumps(task.tags),
            task.estimated_minutes,
            task.context,
            task.reminder_frequency,
            task.completed_at,
            task.completion_notes
        ))

        conn.commit()
        conn.close()

    async def _index_task_in_vector_store(self, task: Task):
        """Index task in vector store for semantic search."""
        # This enables searching tasks by content
        # Implementation depends on vector store interface
        pass

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a single task by ID."""
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_task(row)
        return None

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        due_before: Optional[str] = None,
        due_after: Optional[str] = None,
        limit: int = 50
    ) -> List[Task]:
        """
        List tasks with optional filtering.
        """
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        else:
            # Default: show pending and in_progress
            query += " AND status IN ('pending', 'in_progress', 'blocked')"

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        if due_before:
            query += " AND due_date <= ?"
            params.append(due_before)

        if due_after:
            query += " AND due_date >= ?"
            params.append(due_after)

        query += """ ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                WHEN 'backlog' THEN 5
            END,
            CASE
                WHEN due_date IS NULL THEN 1
                ELSE 0
            END,
            due_date
        """
        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        tasks = [self._row_to_task(row) for row in rows]

        # Filter by tags in Python (since tags are JSON)
        if tags:
            tasks = [
                t for t in tasks
                if any(tag in t.tags for tag in tags)
            ]

        return tasks

    async def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
        completion_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a task."""
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        # Update fields
        if title:
            task.title = title
        if description:
            task.description = description
        if priority:
            task.priority = priority
        if status:
            task.status = status
            if status == TaskStatus.COMPLETED.value:
                task.completed_at = datetime.now().isoformat()
        if due_date:
            task.due_date = due_date
        if tags:
            task.tags = tags
        if completion_notes:
            task.completion_notes = completion_notes

        task.updated_at = datetime.now().isoformat()

        self._save_task_to_db(task)

        return {
            "success": True,
            "task": asdict(task)
        }

    async def complete_task(
        self,
        task_id: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Mark a task as completed."""
        return await self.update_task(
            task_id,
            status=TaskStatus.COMPLETED.value,
            completion_notes=notes
        )

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            return {"success": True, "message": "Task deleted"}
        return {"success": False, "error": "Task not found"}

    def get_tasks_needing_attention(
        self,
        max_results: int = 5,
        context_hint: Optional[str] = None
    ) -> List[Tuple[Task, float]]:
        """
        Get tasks that need attention, scored by urgency.

        Returns tasks with urgency scores, sorted by score.
        """
        # Get pending tasks
        tasks = self.list_tasks(status="pending", limit=100)
        tasks.extend(self.list_tasks(status="in_progress", limit=100))

        scored_tasks = []
        now = datetime.now()

        for task in tasks:
            score = self._calculate_urgency_score(task, now, context_hint)
            scored_tasks.append((task, score))

        # Sort by score descending
        scored_tasks.sort(key=lambda x: x[1], reverse=True)

        return scored_tasks[:max_results]

    def _calculate_urgency_score(
        self,
        task: Task,
        now: datetime,
        context_hint: Optional[str] = None
    ) -> float:
        """
        Calculate urgency score (0-1) for a task.

        Factors:
        - Priority weight (base)
        - Due date proximity (overdue = max)
        - Context match (if context_hint provided)
        - Age (older pending tasks get boost)
        """
        # Base priority weight
        score = self.PRIORITY_WEIGHTS.get(task.priority, 0.5)

        # Due date factor
        if task.due_date:
            try:
                due = datetime.fromisoformat(task.due_date.replace('Z', '+00:00'))
                days_until_due = (due - now).days

                if days_until_due < 0:
                    # Overdue - maximum urgency
                    score += 0.5
                elif days_until_due == 0:
                    # Due today
                    score += 0.3
                elif days_until_due <= 2:
                    # Due within 2 days
                    score += 0.2
                elif days_until_due <= 7:
                    # Due within week
                    score += 0.1
            except:
                pass

        # Context match boost
        if context_hint and task.context:
            if context_hint.lower() in task.context.lower():
                score += 0.1

        # Age boost (tasks pending for weeks)
        try:
            created = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))
            days_old = (now - created).days
            if days_old > 14:
                score += 0.1  # Boost old tasks
        except:
            pass

        return min(score, 1.0)  # Cap at 1.0

    def get_stats(self) -> Dict[str, Any]:
        """Get task statistics."""
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM tasks
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())

        # Count by priority
        cursor.execute("""
            SELECT priority, COUNT(*) FROM tasks
            WHERE status IN ('pending', 'in_progress')
            GROUP BY priority
        """)
        priority_counts = dict(cursor.fetchall())

        # Overdue count
        today = datetime.now().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE status IN ('pending', 'in_progress')
            AND due_date < ?
        """, (today,))
        overdue = cursor.fetchone()[0]

        conn.close()

        return {
            "total": sum(status_counts.values()),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "overdue": overdue,
            "pending": status_counts.get('pending', 0) + status_counts.get('in_progress', 0)
        }

    def _row_to_task(self, row) -> Task:
        """Convert database row to Task object."""
        return Task(
            id=row[0],
            title=row[1],
            description=row[2],
            priority=row[3],
            status=row[4],
            created_at=row[5],
            updated_at=row[6],
            due_date=row[7],
            tags=json.loads(row[8]) if row[8] else [],
            estimated_minutes=row[9],
            context=row[10] or "",
            reminder_frequency=row[11] or "auto",
            completed_at=row[12],
            completion_notes=row[13] or ""
        )
