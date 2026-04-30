from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.case import Case, CaseLink, CaseNote


class CaseRepository(ABC):
    @abstractmethod
    def list_cases(self) -> list[Case]:
        raise NotImplementedError

    @abstractmethod
    def get_case(self, case_id: str) -> Case | None:
        raise NotImplementedError

    @abstractmethod
    def save_case(self, case: Case) -> Case:
        raise NotImplementedError

    @abstractmethod
    def delete_case(self, case_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_links(self, case_id: str | None = None) -> list[CaseLink]:
        raise NotImplementedError

    @abstractmethod
    def save_link(self, link: CaseLink) -> CaseLink:
        raise NotImplementedError

    @abstractmethod
    def delete_link(self, link_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_notes(self, case_id: str | None = None) -> list[CaseNote]:
        raise NotImplementedError

    @abstractmethod
    def save_note(self, note: CaseNote) -> CaseNote:
        raise NotImplementedError

    @abstractmethod
    def delete_note(self, note_id: str) -> bool:
        raise NotImplementedError
