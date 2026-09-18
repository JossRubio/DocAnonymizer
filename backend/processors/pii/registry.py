"""Registro de entidades: garantiza que un mismo dato reciba siempre el mismo marcador.

El problema que resuelve no es solo de consistencia visual. Si "Juan Miguel
Correa" fuese [NOMBRE_1] en un parrafo y [NOMBRE_7] en otro, el documento
anonimizado perderia la informacion de que ambas menciones son la misma persona,
que suele ser justo lo que hace util el documento.

El caso delicado son los nombres parciales: "Correa" o "R. Andrade" deben
resolverse a la persona ya vista. Se hace por inclusion de conjuntos de tokens,
y solo cuando la resolucion es inequivoca: si dos personas distintas encajan, el
nombre parcial recibe su propio marcador. Colapsar dos personas en una seria un
error mucho peor que separar en dos lo que es una sola.
"""

import re
import unicodedata
from typing import Dict, List, Set, Tuple

from .markers import format_marker

# Tratamientos y titulos que no forman parte del nombre.
_TITLES = re.compile(
    r"^(?:sr|sra|srta|d|dn|dna|don|dona|dr|dra|prof|profa|ing|lic|mr|mrs|ms|miss|dr)\.?\s+",
    re.IGNORECASE,
)

# Sufijos societarios: "TechCore S.L." y "TechCore" son la misma organizacion.
_ORG_SUFFIX = re.compile(
    r"[\s,]+(?:s\.?\s?[all]\.?|s\.?\s?a\.?\s?s?\.?|sl|sa|sas|spa|ltda?|"
    r"inc|corp|co|gmbh|bv|nv|plc|llc|srl)\.?$",
    re.IGNORECASE,
)

# Particulas que no identifican a nadie por si solas.
_PARTICLES = {
    "de", "del", "la", "las", "los", "el", "y", "van", "von", "da", "do",
    "dos", "das", "di", "der", "den", "af", "bin", "ibn", "san", "santa",
}

_PUNCT_EDGES = re.compile(r"^[\s\"'(\[.,;:-]+|[\s\"')\]\.,;:-]+$")
_SPACES = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def normalize(surface: str, kind: str = "") -> str:
    """Clave de comparacion: sin acentos, sin tratamientos, en minusculas."""
    value = _PUNCT_EDGES.sub("", surface or "")
    value = _SPACES.sub(" ", value).strip()
    value = strip_accents(value).casefold()
    previous = None
    while previous != value:                 # "Sr. Dr. Juan" -> "juan"
        previous = value
        value = _TITLES.sub("", value).strip()
    if kind == "ORG":
        previous = None
        while previous != value:
            previous = value
            value = _ORG_SUFFIX.sub("", value).strip()
    return value


def significant_tokens(key: str) -> Set[str]:
    """Tokens que sirven para identificar a una persona."""
    return {t for t in key.split() if len(t) >= 3 and t not in _PARTICLES}


class EntityRegistry:
    """Asigna marcadores estables a las entidades de un documento."""

    def __init__(self, lang: str = "es") -> None:
        self.lang = lang
        self._markers: Dict[Tuple[str, str], str] = {}
        self._counters: Dict[str, int] = {}
        self._person_tokens: Dict[str, Set[str]] = {}
        self._surfaces: Dict[Tuple[str, str], Set[str]] = {}
        self._order: List[str] = []

    # ------------------------------------------------------------ interno
    def _resolve_person_alias(self, key: str) -> str:
        """Devuelve la clave de la persona ya registrada que corresponde a ``key``.

        Solo fusiona cuando hay exactamente un candidato compatible.
        """
        tokens = significant_tokens(key)
        if not tokens:
            return key

        candidates = [k for k, known in self._person_tokens.items()
                      if k != key and (tokens <= known or known <= tokens)]
        if len(candidates) != 1:
            # 0 candidatos: entidad nueva. 2 o mas: ambiguo, mejor separarlas.
            return key

        candidate = candidates[0]
        if tokens <= self._person_tokens[candidate]:
            # "Correa" despues de "Juan Miguel Correa": reutiliza su marcador.
            return candidate

        # El nombre nuevo es mas completo que el ya visto ("Juan Miguel Correa"
        # tras haber visto solo "Correa"): hereda el marcador ya asignado para no
        # renumerar nada retroactivamente.
        marker = self._markers.get(("PERSON", candidate))
        if marker is not None:
            self._markers[("PERSON", key)] = marker
        self._person_tokens[key] = tokens | self._person_tokens[candidate]
        return key

    # ------------------------------------------------------------ publico
    def marker_for(self, kind: str, surface: str) -> str:
        """Marcador de esta entidad, creandolo la primera vez que aparece."""
        key = normalize(surface, kind)
        if not key:
            return surface

        if kind == "PERSON":
            key = self._resolve_person_alias(key)

        entry = (kind, key)
        if entry in self._markers:
            self._surfaces.setdefault(entry, set()).add(surface)
            return self._markers[entry]

        self._counters[kind] = self._counters.get(kind, 0) + 1
        marker = format_marker(kind, self._counters[kind], self.lang)
        self._markers[entry] = marker
        self._surfaces.setdefault(entry, set()).add(surface)
        self._order.append(marker)
        if kind == "PERSON":
            self._person_tokens.setdefault(key, significant_tokens(key))
        return marker

    def marker_without_brackets(self, kind: str, surface: str) -> str:
        """Igual que ``marker_for`` pero con parentesis (nombres de hoja Excel)."""
        marker = self.marker_for(kind, surface)
        return marker.replace("[", "(").replace("]", ")")

    def canonical_surfaces(self) -> Dict[str, Tuple[str, str]]:
        """Superficie vista -> (kind, marcador), para el refuerzo por diccionario."""
        out: Dict[str, Tuple[str, str]] = {}
        for (kind, key), surfaces in self._surfaces.items():
            marker = self._markers.get((kind, key))
            if marker is None:
                continue
            for surface in surfaces:
                cleaned = _PUNCT_EDGES.sub("", surface).strip()
                if len(cleaned) >= 4:        # evita disparar con fragmentos cortos
                    out[cleaned] = (kind, marker)
        return out

    def person_token_index(self, min_length: int = 5) -> Dict[str, str]:
        """Apellidos sueltos que identifican sin ambiguedad a una persona ya vista.

        Permite rescatar "Correa" o "R. Andrade" en una celda o una cabecera,
        donde el modelo no tiene contexto para reconocer un nombre. Se exige que
        el token pertenezca a una sola persona y que sea razonablemente largo:
        con tokens cortos o compartidos el riesgo de sustituir una palabra comun
        es demasiado alto.
        """
        owners: Dict[str, Set[str]] = {}
        for key in self._person_tokens:
            for token in self._person_tokens[key]:
                if len(token) >= min_length:
                    owners.setdefault(token, set()).add(key)

        index: Dict[str, str] = {}
        for token, keys in owners.items():
            if len(keys) != 1:
                continue                      # compartido por varias personas
            marker = self._markers.get(("PERSON", next(iter(keys))))
            if marker is not None:
                index[token] = marker
        return index

    def counts_by_kind(self) -> Dict[str, int]:
        return dict(self._counters)

    def markers_in_order(self) -> List[str]:
        return list(self._order)
