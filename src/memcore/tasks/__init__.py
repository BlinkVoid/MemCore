"""
Task Management System for MemCore

Provides AI assistant-style task tracking with:
- Priority-based reminders
- Automatic task surfacing
- Deadline tracking
- Completion pattern learning
"""

from .task_manager import TaskManager, Task, TaskPriority, TaskStatus
from .reminder_scheduler import ReminderScheduler

__all__ = [
    "TaskManager",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "ReminderScheduler",
]
