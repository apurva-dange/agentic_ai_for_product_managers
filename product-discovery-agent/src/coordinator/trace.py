"""Coordinator-level event history, exportable to JSON.

This is the Module 2 analogue of Module 1's MessageHistory: an append-only
log of everything the coordinator did, so a run can be replayed and audited
after the fact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from coordinator.models import CoordinatorEvent, EventType, SubagentName, next_event_sequence


class CoordinatorTrace:
    """An append-only log of coordinator-level events for one run."""

    def __init__(self) -> None:
        self._events: list[CoordinatorEvent] = []

    @property
    def events(self) -> list[CoordinatorEvent]:
        return list(self._events)

    def record(
        self,
        event_type: EventType,
        detail: str,
        agent_name: Optional[SubagentName] = None,
        task_id: Optional[str] = None,
    ) -> CoordinatorEvent:
        event = CoordinatorEvent(
            sequence=next_event_sequence(),
            event_type=event_type,
            timestamp=CoordinatorEvent.now_iso(),
            detail=detail,
            agent_name=agent_name,
            task_id=task_id,
        )
        self._events.append(event)
        return event

    def render_trace(self) -> str:
        lines = ["=" * 72, "COORDINATOR EVENT TRACE", "=" * 72]
        for event in self._events:
            header = f"[{event.sequence:03d}] {event.event_type.value.upper()}"
            if event.agent_name:
                header += f" ({event.agent_name.value})"
            lines.append(header)
            lines.append(f"    {event.detail}")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_json_dict(self) -> list[dict]:
        return [json.loads(event.model_dump_json()) for event in self._events]

    def save_trace(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_json_dict(), indent=2))
        return output_path
