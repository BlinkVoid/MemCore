"""
Reminder Scheduler for Task Management

Automatically surfaces tasks based on:
- Priority and urgency scores
- User activity patterns
- Natural conversation gaps
- Time of day (optional)
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


@dataclass
class ReminderConfig:
    """Configuration for reminder behavior."""
    enabled: bool = True
    check_interval_minutes: int = 30
    min_urgency_score: float = 0.7  # Only remind if score >= this
    max_reminders_per_session: int = 3
    cooldown_minutes: int = 60  # Don't repeat same reminder
    respect_focus_mode: bool = True  # Don't interrupt if user is coding
    preferred_times: Optional[List[int]] = None  # Hours of day (0-23)


class ReminderScheduler:
    """
    Schedules automatic task reminders.

    Integrates with the conversation flow to surface
    high-priority tasks at appropriate moments.
    """

    def __init__(
        self,
        task_manager,
        llm=None,
        config: Optional[ReminderConfig] = None
    ):
        self.task_manager = task_manager
        self.llm = llm
        self.config = config or ReminderConfig()

        self.scheduler = AsyncIOScheduler()
        self._reminder_callback: Optional[Callable] = None
        self._last_reminder_time: Optional[datetime] = None
        self._reminded_task_ids: set = set()
        self._user_activity_history: List[Dict[str, Any]] = []

    def start(self):
        """Start the reminder scheduler."""
        if not self.config.enabled:
            return

        # Add periodic check job
        self.scheduler.add_job(
            self._check_and_remind,
            IntervalTrigger(minutes=self.config.check_interval_minutes),
            id='task_reminder_check',
            replace_existing=True
        )

        self.scheduler.start()

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()

    def set_reminder_callback(self, callback: Callable[[str], None]):
        """
        Set callback function for when reminders should be shown.

        The callback receives the reminder text to display.
        """
        self._reminder_callback = callback

    def record_user_activity(self, activity_type: str, context: str = ""):
        """
        Record user activity for context-aware reminders.

        Args:
            activity_type: 'coding', 'researching', 'planning', etc.
            context: Additional context
        """
        self._user_activity_history.append({
            "type": activity_type,
            "context": context,
            "timestamp": datetime.now().isoformat()
        })

        # Keep last 20 activities
        self._user_activity_history = self._user_activity_history[-20:]

    async def _check_and_remind(self):
        """Periodic check for tasks needing attention."""
        if not self._reminder_callback:
            return

        # Check if it's an appropriate time
        if not self._is_appropriate_time():
            return

        # Check if user is in focus mode
        if self.config.respect_focus_mode and self._user_in_focus_mode():
            return

        # Get tasks needing attention
        tasks_with_scores = self.task_manager.get_tasks_needing_attention(
            max_results=self.config.max_reminders_per_session
        )

        # Filter by urgency score and cooldown
        now = datetime.now()
        reminders = []

        for task, score in tasks_with_scores:
            # Skip if below threshold
            if score < self.config.min_urgency_score:
                continue

            # Skip if reminded recently
            if task.id in self._reminded_task_ids:
                if self._last_reminder_time:
                    minutes_since = (now - self._last_reminder_time).total_seconds() / 60
                    if minutes_since < self.config.cooldown_minutes:
                        continue

            reminders.append((task, score))

        # Send reminders
        if reminders and self._reminder_callback:
            reminder_text = self._format_reminder(reminders)
            self._reminder_callback(reminder_text)

            self._last_reminder_time = now
            for task, _ in reminders:
                self._reminded_task_ids.add(task.id)

    def _is_appropriate_time(self) -> bool:
        """Check if current time is appropriate for reminders."""
        if self.config.preferred_times is None:
            return True

        current_hour = datetime.now().hour
        return current_hour in self.config.preferred_times

    def _user_in_focus_mode(self) -> bool:
        """Check if user appears to be in deep focus."""
        if not self._user_activity_history:
            return False

        # Check recent activity
        recent = self._user_activity_history[-3:]

        # If last 3 activities were coding with short gaps, user is focused
        coding_count = sum(1 for a in recent if a["type"] == "coding")

        return coding_count >= 2

    def _format_reminder(self, reminders: List[tuple]) -> str:
        """Format reminder text for display."""
        if len(reminders) == 1:
            task, score = reminders[0]
            urgency = "🔴" if score > 0.9 else "🟠" if score > 0.75 else "🟡"

            text = f"""{urgency} Task Reminder

**{task.title}**
Priority: {task.priority.upper()}
"""
            if task.due_date:
                due = datetime.fromisoformat(task.due_date.replace('Z', '+00:00'))
                days_until = (due - datetime.now()).days
                if days_until < 0:
                    text += f"⚠️ OVERDUE by {abs(days_until)} days\n"
                elif days_until == 0:
                    text += "⏰ Due today\n"
                else:
                    text += f"📅 Due in {days_until} days\n"

            if task.description:
                text += f"\n{task.description[:200]}..."

            text += "\n\n💡 Say 'show my tasks' to see all or 'complete <task_id>' to mark done."

            return text

        # Multiple reminders
        text = "📋 You have several tasks needing attention:\n\n"

        for i, (task, score) in enumerate(reminders, 1):
            urgency = "🔴" if score > 0.9 else "🟠" if score > 0.75 else "🟡"
            text += f"{urgency} {i}. {task.title} ({task.priority.upper()})\n"

        text += "\n💡 Say 'show my tasks' to see details or complete them."

        return text

    async def manual_reminder_check(self, context: str = "") -> Optional[str]:
        """
        Manually check for reminders (can be called during conversation).

        Args:
            context: Current conversation context for relevance matching

        Returns:
            Reminder text or None if no urgent tasks
        """
        tasks_with_scores = self.task_manager.get_tasks_needing_attention(
            max_results=3,
            context_hint=context
        )

        # Filter by score
        reminders = [
            (t, s) for t, s in tasks_with_scores
            if s >= self.config.min_urgency_score
        ]

        if not reminders:
            return None

        return self._format_reminder(reminders)

    def clear_reminder_history(self, task_id: Optional[str] = None):
        """
        Clear reminder history.

        Args:
            task_id: Clear history for specific task, or all if None
        """
        if task_id:
            self._reminded_task_ids.discard(task_id)
        else:
            self._reminded_task_ids.clear()
            self._last_reminder_time = None

    def get_config(self) -> Dict[str, Any]:
        """Get current reminder configuration."""
        return {
            "enabled": self.config.enabled,
            "check_interval_minutes": self.config.check_interval_minutes,
            "min_urgency_score": self.config.min_urgency_score,
            "max_reminders_per_session": self.config.max_reminders_per_session,
            "cooldown_minutes": self.config.cooldown_minutes,
            "respect_focus_mode": self.config.respect_focus_mode,
            "last_reminder": self._last_reminder_time.isoformat() if self._last_reminder_time else None,
            "reminded_count": len(self._reminded_task_ids)
        }

    async def update_config(self, **kwargs):
        """Update reminder configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # Restart scheduler if interval changed
        if 'check_interval_minutes' in kwargs:
            self.scheduler.reschedule_job(
                'task_reminder_check',
                trigger=IntervalTrigger(minutes=self.config.check_interval_minutes)
            )
