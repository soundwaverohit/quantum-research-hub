"""Minimal in-process task queue.

The MVP runs agents synchronously in a fixed pipeline, but routing them through
a queue keeps the seam for a future worker model (Celery/RQ, per ARCHITECTURE
§15) without changing callers.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    def __init__(self, tasks: Iterable[Task] | None = None) -> None:
        self._q: deque[Task] = deque(tasks or [])

    def enqueue(self, task: Task) -> None:
        self._q.append(task)

    def dequeue(self) -> Task | None:
        return self._q.popleft() if self._q else None

    def __len__(self) -> int:
        return len(self._q)

    def __bool__(self) -> bool:
        return bool(self._q)

class TaskIterator:
    def __init__(self, task_queue: TaskQueue) -> None:
        self._task_queue = task_queue

    def __iter__(self) -> TaskIterator:
        return self

    def __next__(self) -> Task:
        task = self._task_queue.dequeue()
        if task is None:
            raise StopIteration
        return task
    
class TaskProcessor:
    def __init__(self, task_queue: TaskQueue) -> None:
        self._task_queue = task_queue

    def process_tasks(self) -> None:
        for task in TaskIterator(self._task_queue):
            self.process_task(task)

    def process_task(self, task: Task) -> None:
        # Placeholder for actual task processing logic
        print(f"Processing task: {task.name} with payload: {task.payload}")

    