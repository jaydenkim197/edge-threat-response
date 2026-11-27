"""An explicitly configured Jetson 40-pin header alarm output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import FrameDetections, ThreatEvent


class JetsonGpioAlarm:
    def __init__(self, pins: dict[int, bool], *, gpio: Any = None) -> None:
        if not pins or any(
            type(pin) is not int or not 1 <= pin <= 40 or type(active_low) is not bool
            for pin, active_low in pins.items()
        ):
            raise ValueError("Provide BOARD pins from 1 to 40 and a boolean active_low for each.")
        self._pins = dict(pins)
        self._gpio = gpio
        self._configured: list[int] = []

    @classmethod
    def load(cls, path: Path) -> JetsonGpioAlarm:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
                or payload["schema_version"] != 1):
            raise ValueError("GPIO alarm config requires schema_version 1.")
        rows = payload.get("outputs")
        if not isinstance(rows, list) or not rows or any(
            not isinstance(row, dict) or row.keys() != {"board_pin", "active_low"}
            or type(row["board_pin"]) is not int for row in rows
        ):
            raise ValueError("Configure one or more outputs with board_pin and active_low.")
        pins = {row["board_pin"]: row["active_low"] for row in rows}
        if len(pins) != len(rows):
            raise ValueError("GPIO alarm BOARD pins must be unique.")
        return cls(pins)

    def __enter__(self) -> JetsonGpioAlarm:
        if self._configured:
            raise RuntimeError("GPIO alarm is already open.")
        if self._gpio is None:
            import Jetson.GPIO as gpio

            self._gpio = gpio
        gpio = self._gpio
        if gpio.getmode() not in {None, gpio.BOARD}:
            raise RuntimeError("GPIO alarm requires BOARD pin numbering.")
        gpio.setmode(gpio.BOARD)
        try:
            for pin in self._pins:
                gpio.setup(pin, gpio.OUT, initial=self._value(pin, False))
                self._configured.append(pin)
        except BaseException:
            self._close()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._close()

    def set_active(
        self, active: bool, frame: FrameDetections, event: ThreatEvent | None
    ) -> None:
        if not self._configured:
            raise RuntimeError("GPIO alarm is closed.")
        try:
            pins = tuple(self._configured)
            self._gpio.output(pins, tuple(self._value(pin, active) for pin in pins))
        except Exception:
            self._close()
            raise

    def _value(self, pin: int, active: bool) -> Any:
        return self._gpio.HIGH if active != self._pins[pin] else self._gpio.LOW

    def _close(self) -> None:
        errors: list[Exception] = []
        for pin in self._configured:
            try:
                self._gpio.output(pin, self._value(pin, False))
            except Exception as error:
                errors.append(error)
            try:
                self._gpio.cleanup(pin)
            except Exception as error:
                errors.append(error)
        self._configured.clear()
        if errors:
            raise RuntimeError("GPIO alarm could not clear and release every configured output.") from errors[0]
