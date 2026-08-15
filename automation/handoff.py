import asyncio
from dataclasses import dataclass
from typing import Optional

from automation.logging_utils import utc_now


@dataclass
class HandoffState:
    in_handoff: bool = False
    reason: Optional[str] = None
    requested_at: Optional[str] = None
    resumed_at: Optional[str] = None
    operator_note: Optional[str] = None


class HumanHandoff:
    def __init__(self):
        self.state = HandoffState()
        self._resume_event = asyncio.Event()

    async def request(
        self,
        reason: str,
    ) -> None:
        self.state.in_handoff = True
        self.state.reason = reason
        self.state.requested_at = utc_now()

        print("\n=== HUMAN INTERVENTION REQUIRED ===")
        print(f"Reason: {reason}")
        print("The browser will remain open.")
        print(
            "Take control of the live browser session manually."
        )
        print(
            "When finished, return to this terminal and press Enter."
        )

        await asyncio.to_thread(input)

        self.state.operator_note = (
            "Human operator manually reviewed/interacted "
            "with the live session."
        )

        self.state.in_handoff = False
        self.state.resumed_at = utc_now()

        self._resume_event.set()

    def to_dict(self):
        return {
            "in_handoff": self.state.in_handoff,
            "reason": self.state.reason,
            "requested_at": self.state.requested_at,
            "resumed_at": self.state.resumed_at,
            "operator_note": self.state.operator_note,
        }