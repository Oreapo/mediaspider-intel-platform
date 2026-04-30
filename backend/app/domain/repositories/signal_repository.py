from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.signal import Signal


class SignalRepository(ABC):
    @abstractmethod
    def list_signals(self) -> list[Signal]:
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
