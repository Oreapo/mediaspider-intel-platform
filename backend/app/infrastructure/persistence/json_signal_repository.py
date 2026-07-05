from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.signal import RiskLevel, Signal, SignalStatus, SignalType
from ...domain.repositories.signal_repository import SignalRepository


class JsonSignalRepository(SignalRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Signal]:
        signals = self._filtered_signals(
            dataset_id=dataset_id,
            status=status,
            risk_level=risk_level,
            signal_type=signal_type,
            query=query,
        )
        if offset > 0:
            signals = signals[offset:]
        if limit is not None:
            signals = signals[:limit]
        return signals

    def count_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
    ) -> int:
        return len(
            self._filtered_signals(
                dataset_id=dataset_id,
                status=status,
                risk_level=risk_level,
                signal_type=signal_type,
                query=query,
            )
        )

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

    def delete_signals_for_dataset(self, dataset_id: str) -> int:
        normalized_dataset_id = dataset_id.strip()
        if not normalized_dataset_id:
            return 0
        signals = self._load_all()
        filtered = [signal for signal in signals if signal.dataset_id != normalized_dataset_id]
        deleted = len(signals) - len(filtered)
        if deleted:
            self._save_all(filtered)
        return deleted

    def _filtered_signals(
        self,
        *,
        dataset_id: str | None,
        status: SignalStatus | None,
        risk_level: RiskLevel | None,
        signal_type: SignalType | None,
        query: str,
    ) -> list[Signal]:
        signals = sorted(self._load_all(), key=lambda signal: signal.updated_at, reverse=True)
        if dataset_id:
            signals = [signal for signal in signals if signal.dataset_id == dataset_id]
        if status:
            signals = [signal for signal in signals if signal.status == status]
        if risk_level:
            signals = [signal for signal in signals if signal.risk_level == risk_level]
        if signal_type:
            signals = [signal for signal in signals if signal.signal_type == signal_type]
        needle = query.strip().lower()
        if needle:
            signals = [signal for signal in signals if self._matches_query(signal, needle)]
        return signals

    def _matches_query(self, signal: Signal, needle: str) -> bool:
        values = [
            signal.id,
            signal.dataset_id,
            signal.signal_type.value,
            signal.signal_source,
            signal.risk_level.value,
            signal.status.value,
            signal.summary,
        ]
        source_ref = signal.payload_json.get("source_ref")
        if isinstance(source_ref, dict):
            values.extend(str(value) for value in source_ref.values() if value is not None)
        return any(needle in str(value).lower() for value in values)

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
