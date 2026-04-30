from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.signal import Signal
from ...domain.repositories.signal_repository import SignalRepository


class JsonSignalRepository(SignalRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_signals(self) -> list[Signal]:
        return sorted(self._load_all(), key=lambda signal: signal.updated_at, reverse=True)

    def get_signal(self, signal_id: str) -> Signal | None:
        for signal in self._load_all():
            if signal.id == signal_id:
                return signal
        return None

    def save_signal(self, signal: Signal) -> Signal:
        signals = self._load_all()
        replaced = False
        for index, existing in enumerate(signals):
            if existing.id == signal.id:
                signals[index] = signal
                replaced = True
                break
        if not replaced:
            signals.append(signal)
        self._save_all(signals)
        return signal

    def delete_signal(self, signal_id: str) -> bool:
        signals = self._load_all()
        filtered = [signal for signal in signals if signal.id != signal_id]
        if len(filtered) == len(signals):
            return False
        self._save_all(filtered)
        return True

    def _load_all(self) -> list[Signal]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        signals: list[Signal] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                signals.append(Signal.model_validate(item))
            except Exception:
                continue
        return signals

    def _save_all(self, signals: list[Signal]) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([signal.model_dump(mode="json") for signal in signals], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
