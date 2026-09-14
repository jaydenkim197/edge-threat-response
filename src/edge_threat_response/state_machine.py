from __future__ import annotations

from dataclasses import dataclass

from .domain import AlertState


@dataclass(frozen=True)
class StateTransition:
    before: AlertState
    after: AlertState
    candidate: bool
    confirmed: bool
    entered_confirmed: bool
    exited_confirmed: bool
    rearm_clear_streak: int


class AlertStateMachine:
    def __init__(self, *, rearm_clear_frames: int) -> None:
        if (
            isinstance(rearm_clear_frames, bool)
            or not isinstance(rearm_clear_frames, int)
            or rearm_clear_frames < 1
        ):
            raise ValueError("rearm_clear_frames must be a positive integer.")
        self.rearm_clear_frames = rearm_clear_frames
        self.state = AlertState.CLEAR
        self._clear_streak = 0

    def update(self, *, candidate: bool, confirmed: bool) -> StateTransition:
        if not isinstance(candidate, bool) or not isinstance(confirmed, bool):
            raise TypeError("candidate and confirmed must be bool.")
        if confirmed and not candidate:
            raise ValueError("confirmed evidence must also be candidate evidence.")

        before = self.state
        if before in {AlertState.CLEAR, AlertState.CANDIDATE}:
            if confirmed:
                after = AlertState.CONFIRMED
            elif candidate:
                after = AlertState.CANDIDATE
            else:
                after = AlertState.CLEAR
            self._clear_streak = 0
        elif before is AlertState.CONFIRMED:
            if confirmed:
                after = AlertState.CONFIRMED
                self._clear_streak = 0
            else:
                after = AlertState.COOLDOWN
                # Enter COOLDOWN first. Rearm counting starts with subsequent samples,
                # so every confirmed event has an observable cooldown boundary.
                self._clear_streak = 0
        else:
            if candidate or confirmed:
                after = AlertState.COOLDOWN
                self._clear_streak = 0
            else:
                self._clear_streak += 1
                if self._clear_streak >= self.rearm_clear_frames:
                    after = AlertState.CLEAR
                    self._clear_streak = 0
                else:
                    after = AlertState.COOLDOWN

        self.state = after
        return StateTransition(
            before=before,
            after=after,
            candidate=candidate,
            confirmed=confirmed,
            entered_confirmed=(
                before is not AlertState.CONFIRMED and after is AlertState.CONFIRMED
            ),
            exited_confirmed=(
                before is AlertState.CONFIRMED and after is not AlertState.CONFIRMED
            ),
            rearm_clear_streak=self._clear_streak,
        )
