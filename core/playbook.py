"""The playbook as a document, not just a prompt.

`core.config.playbook()` returns the whole file, which is what every agent
prefix needs. This module splits it into numbered sections so that:

  - the Coach Resources page can show a table of contents and let a new coach
    read the methodology without asking anyone;
  - the methodology agent can cite "§3. The shots" and be checked on it;
  - an admin can edit one section without retyping five thousand words.

Sections are the `## N. Title` headings. Anything before the first one is the
preamble.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.config import PLAYBOOK_PATH, playbook

HEADING = re.compile(r"^## (\d+)\.\s+(.+)$", re.M)


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    body: str

    @property
    def ref(self) -> str:
        return f"§{self.number}"

    @property
    def label(self) -> str:
        return f"§{self.number}. {self.title}"

    @property
    def words(self) -> int:
        return len(self.body.split())


def sections(text: str | None = None) -> list[Section]:
    text = text if text is not None else playbook()
    marks = list(HEADING.finditer(text))
    out = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append(Section(
            number=int(mark.group(1)),
            title=mark.group(2).strip(),
            body=text[mark.start():end].strip(),
        ))
    return out


def section(number: int) -> Section | None:
    return next((s for s in sections() if s.number == number), None)


def contents() -> str:
    """The table of contents, for a prompt. Tells the agent what it may cite."""
    return "\n".join(f"  {s.label}" for s in sections())


def valid_refs() -> set[str]:
    return {s.ref for s in sections()}


def replace_section(number: int, new_body: str) -> None:
    """Swap one section's text. Admin-only — the caller enforces that.

    Writes the whole file back and clears the cached read, so the next agent
    run picks the change up. There is no partial-write path: either the file
    is replaced or it is not.
    """
    current = playbook()
    target = next((s for s in sections(current) if s.number == number), None)
    if target is None:
        raise ValueError(f"no section {number}")
    updated = current.replace(target.body, new_body.strip(), 1)
    PLAYBOOK_PATH.write_text(updated, encoding="utf-8")
    playbook.cache_clear()


def stats() -> dict:
    found = sections()
    text = playbook()
    return {
        "sections": len(found),
        "words": len(text.split()),
        "approx_tokens": len(text) // 4,
    }
