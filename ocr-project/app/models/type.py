from enum import Enum, auto
from typing import Any


class TaskStatus(Enum):
    def _generate_next_value_(
        self,
        name: str,
        _start: int,
        _count: int,
        _last_values: list[Any],
    ) -> str:
        return name.lower()

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
