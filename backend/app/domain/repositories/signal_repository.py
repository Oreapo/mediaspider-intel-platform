from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.signal import RiskLevel, Signal, SignalStatus, SignalType


class SignalRepository(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def count_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_signal(self, signal_id: str) -> Signal | None:
        raise NotImplementedError

    @abstractmethod
    def save_signal(self, signal: Signal) -> Signal:
        raise NotImplementedError

    @abstractmethod
    def delete_signal(self, signal_id: str) -> bool:
        raise NotImplementedError
