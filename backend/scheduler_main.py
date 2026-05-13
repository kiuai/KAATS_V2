"""Scheduler container entry point."""
import asyncio

from app.scheduler.evaluator import ScheduleEvaluator

# SIGTERM / SIGINT handled inside ScheduleEvaluator._setup_signal_handlers()
if __name__ == "__main__":
    asyncio.run(ScheduleEvaluator().start())
