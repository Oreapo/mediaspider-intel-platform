from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.case import Case, CaseLink, CaseNote
from ...domain.repositories.case_repository import CaseRepository


class JsonCaseRepository(CaseRepository):
    def __init__(self, cases_file: Path, links_file: Path, notes_file: Path):
        self.cases_file = cases_file
        self.links_file = links_file
        self.notes_file = notes_file

    def list_cases(self) -> list[Case]:
        return sorted(self._load_cases(), key=lambda case: case.updated_at, reverse=True)

    def get_case(self, case_id: str) -> Case | None:
        for case in self._load_cases():
            if case.id == case_id:
                return case
        return None

    def save_case(self, case: Case) -> Case:
        cases = self._load_cases()
        replaced = False
        for index, existing in enumerate(cases):
            if existing.id == case.id:
                cases[index] = case
                replaced = True
                break
        if not replaced:
            cases.append(case)
        self._save_cases(cases)
        return case

    def delete_case(self, case_id: str) -> bool:
        cases = self._load_cases()
        filtered = [case for case in cases if case.id != case_id]
        if len(filtered) == len(cases):
            return False
        self._save_cases(filtered)
        self._save_links([link for link in self._load_links() if link.case_id != case_id])
        self._save_notes([note for note in self._load_notes() if note.case_id != case_id])
        return True

    def list_links(self, case_id: str | None = None) -> list[CaseLink]:
        links = self._load_links()
        if case_id is not None:
            links = [link for link in links if link.case_id == case_id]
        return sorted(links, key=lambda link: link.created_at)

    def save_link(self, link: CaseLink) -> CaseLink:
        links = self._load_links()
        replaced = False
        for index, existing in enumerate(links):
            if existing.id == link.id:
                links[index] = link
                replaced = True
                break
        if not replaced:
            links.append(link)
        self._save_links(links)
        return link

    def delete_link(self, link_id: str) -> bool:
        links = self._load_links()
        filtered = [link for link in links if link.id != link_id]
        if len(filtered) == len(links):
            return False
        self._save_links(filtered)
        return True

    def list_notes(self, case_id: str | None = None) -> list[CaseNote]:
        notes = self._load_notes()
        if case_id is not None:
            notes = [note for note in notes if note.case_id == case_id]
        return sorted(notes, key=lambda note: note.created_at)

    def save_note(self, note: CaseNote) -> CaseNote:
        notes = self._load_notes()
        replaced = False
        for index, existing in enumerate(notes):
            if existing.id == note.id:
                notes[index] = note
                replaced = True
                break
        if not replaced:
            notes.append(note)
        self._save_notes(notes)
        return note

    def delete_note(self, note_id: str) -> bool:
        notes = self._load_notes()
        filtered = [note for note in notes if note.id != note_id]
        if len(filtered) == len(notes):
            return False
        self._save_notes(filtered)
        return True

    def _load_cases(self) -> list[Case]:
        return self._load_model_list(self.cases_file, Case)

    def _load_links(self) -> list[CaseLink]:
        return self._load_model_list(self.links_file, CaseLink)

    def _load_notes(self) -> list[CaseNote]:
        return self._load_model_list(self.notes_file, CaseNote)

    def _load_model_list(self, path: Path, model_class):
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        items = []
        for item in raw if isinstance(raw, list) else []:
            try:
                items.append(model_class.model_validate(item))
            except Exception:
                continue
        return items

    def _save_cases(self, cases: list[Case]) -> None:
        self._save_model_list(self.cases_file, cases)

    def _save_links(self, links: list[CaseLink]) -> None:
        self._save_model_list(self.links_file, links)

    def _save_notes(self, notes: list[CaseNote]) -> None:
        self._save_model_list(self.notes_file, notes)

    def _save_model_list(self, path: Path, items: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
