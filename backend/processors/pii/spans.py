"""Tipo compartido entre el detector de patrones y el motor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """Un fragmento de texto identificado como sensible.

    ``start``/``end`` son offsets sobre el texto de la unidad analizada.
    ``priority`` decide quien gana cuando dos spans se solapan.
    ``source`` es informativo: "regex", "ner" o "gazetteer".
    """
    start: int
    end: int
    kind: str
    text: str
    priority: int
    source: str = "regex"

    @property
    def length(self) -> int:
        return self.end - self.start
