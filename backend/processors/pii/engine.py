"""Motor de anonimizacion: decide que se sustituye y por que marcador.

Funciona en tres pasadas sobre el mismo conjunto de textos, porque para que los
marcadores sean consistentes hay que conocer el documento entero antes de
escribir nada:

  A. Recoleccion  - se reunen todas las unidades de texto y se detecta el idioma.
  B. Analisis     - reglas + NER sobre los textos unicos; se registran entidades.
  B2. Diccionario - las entidades ya conocidas se buscan literalmente en TODOS los
                    textos. Es lo que rescata "Juan Correa" en una celda suelta o
                    en un titulo, donde el modelo no tiene contexto para verlo.
  C. Aplicacion   - cada procesador vuelve a recorrer su documento y pide los
                    reemplazos, que ya estan calculados en cache.
"""

import re
from typing import Dict, Iterable, List, Sequence, Tuple

from . import nlp as nlp_mod
from .levels import BALANCED, level_value
from .patterns import P_GAZETTEER, iter_regex_spans
from .registry import EntityRegistry
from .runs import Replacement
from .spans import Span

# Una unidad es el texto a analizar mas el contexto externo que lo acompana
# (en Excel, la cabecera de su columna; en Word y PowerPoint, cadena vacia).
Unit = Tuple[str, str]

_MAX_GAZETTEER_TERMS = 400


def resolve_overlaps(spans: List[Span]) -> List[Span]:
    """Deja un conjunto de spans disjuntos.

    Criterio, en orden: mayor prioridad de tipo, span mas largo, mas a la
    izquierda. Los marcadores ya existentes (``__SKIP__``) ganan a todo y luego
    se descartan, de modo que reprocesar un documento no los vuelve a envolver.
    """
    ordered = sorted(spans, key=lambda s: (-s.priority, -s.length, s.start))
    accepted: List[Span] = []
    for span in ordered:
        if any(span.start < other.end and other.start < span.end for other in accepted):
            continue
        accepted.append(span)
    accepted.sort(key=lambda s: s.start)
    return [s for s in accepted if s.kind != "__SKIP__"]


class PiiEngine:
    """Analiza un documento completo y entrega los reemplazos por unidad."""

    def __init__(self, label_lang: str = "es", level: str = "balanced") -> None:
        self.label_lang = label_lang if label_lang in ("es", "en") else "es"
        self.level_name = level
        self.level = level_value(level)
        self.registry = EntityRegistry(self.label_lang)
        self.warnings: List[str] = []
        self.doc_lang = self.label_lang
        self.engine_name = "regex-only"
        self.total_replacements = 0
        self._cache: Dict[Unit, List[Replacement]] = {}
        self._gazetteer = None
        self._primed = False

    # ------------------------------------------------------------ pasada A
    def prime(self, units: Iterable) -> None:
        """Analiza el documento entero. Debe llamarse antes de aplicar nada."""
        normalized: List[Unit] = []
        seen = set()
        for unit in units:
            text, context = unit if isinstance(unit, tuple) else (unit, "")
            if not text or not text.strip():
                continue
            key = (text, context)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(key)

        if not normalized:
            self._primed = True
            return

        texts = [t for t, _ in normalized]
        self.doc_lang = nlp_mod.detect_lang(texts, fallback=self.label_lang)

        # ------------------------------------------------------- pasada B
        ner_by_text = self._collect_ner(texts)

        per_unit: List[List[Span]] = []
        for index, (text, context) in enumerate(normalized):
            spans = list(iter_regex_spans(text, self.level, context))
            spans.extend(ner_by_text[index])
            per_unit.append(resolve_overlaps(spans))

        # El registro se puebla en orden de recorrido del documento, de modo que
        # la numeracion de los marcadores sigue el orden de aparicion.
        for spans in per_unit:
            for span in spans:
                self.registry.marker_for(span.kind, span.text)

        # ------------------------------------------------------ pasada B2
        gazetteer = self._build_gazetteer()
        self._gazetteer = gazetteer

        # ------------------------------------------------------- pasada C
        for (text, context), spans in zip(normalized, per_unit):
            if gazetteer is not None:
                extra = self._gazetteer_spans(gazetteer, text)
                if extra:
                    spans = resolve_overlaps(list(spans) + extra)

            replacements: List[Replacement] = []
            for span in spans:
                replacements.append(
                    (span.start, span.end, self.registry.marker_for(span.kind, span.text))
                )
            self._cache[(text, context)] = replacements
            self.total_replacements += len(replacements)

        self._primed = True

    # ------------------------------------------------------------ internos
    def _collect_ner(self, texts: Sequence[str]) -> List[List[Span]]:
        """Entidades del modelo, con degradacion explicita si no esta disponible."""
        if not nlp_mod.spacy_available():
            self._warn("spacy_missing")
            return [[] for _ in texts]

        lang = self.doc_lang
        if not nlp_mod.model_available(lang):
            alternative = next((l for l in nlp_mod.SUPPORTED_DOC_LANGS
                                if nlp_mod.model_available(l)), None)
            if alternative is None:
                self._warn("models_missing")
                return [[] for _ in texts]
            self._warn("model_fallback", missing=lang, used=alternative)
            lang = alternative

        spans = nlp_mod.ner_spans(texts, lang, self.level)
        self.engine_name = "spacy+regex"
        return spans

    def _warn(self, code: str, **params) -> None:
        payload = {"code": code}
        payload.update({k: str(v) for k, v in params.items()})
        if payload not in self.warnings:
            self.warnings.append(payload)
        if nlp_mod.require_spacy_enabled() and code in ("spacy_missing", "models_missing"):
            raise nlp_mod.PiiUnavailableError(
                "El modo de anonimizacion requiere spaCy y sus modelos. "
                "Instalalos con: pip install spacy && python -m spacy download es_core_news_md"
            )

    def _build_gazetteer(self):
        """Busca las entidades ya conocidas por su texto literal.

        Se compone de dos indices con criterios distintos:

        - Nombres y organizaciones completos, sin distinguir mayusculas. Son
          cadenas largas y especificas, con muy poco riesgo de coincidencia
          fortuita.
        - Apellidos sueltos de personas ya identificadas, distinguiendo
          mayusculas. Rescatan "Correa" o "R. Andrade" en tablas y cabeceras,
          que es donde el modelo falla mas; exigir la inicial mayuscula evita
          sustituir palabras comunes que coinciden con un apellido ("leal").

        Solo se aplica a nombres y organizaciones: el resto de tipos ya los
        cubren las reglas, y buscar literalmente un importe generaria ruido.
        """
        surfaces = self.registry.canonical_surfaces()
        full = {s: v for s, v in surfaces.items() if v[0] in ("PERSON", "ORG")}
        tokens = self.registry.person_token_index()

        matchers = []
        if full:
            ordered = sorted(full, key=len, reverse=True)[:_MAX_GAZETTEER_TERMS]
            pattern = "|".join(re.escape(t) for t in ordered)
            try:
                matchers.append((
                    re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE),
                    {t.casefold(): full[t] for t in ordered},
                    True,           # insensible a mayusculas
                ))
            except re.error:
                pass

        if tokens:
            ordered = sorted(tokens, key=len, reverse=True)[:_MAX_GAZETTEER_TERMS]
            # El token esta normalizado (minusculas, sin acentos); se busca su
            # forma capitalizada, que es como aparece un apellido en el texto.
            pattern = "|".join(re.escape(t.capitalize()) for t in ordered)
            try:
                matchers.append((
                    re.compile(rf"(?<!\w)(?:{pattern})(?!\w)"),
                    {t.capitalize(): ("PERSON", tokens[t]) for t in ordered},
                    False,          # sensible a mayusculas
                ))
            except re.error:
                pass

        return matchers or None

    def _gazetteer_spans(self, matchers, text: str) -> List[Span]:
        found: List[Span] = []
        for regex, lookup, ignore_case in matchers:
            for match in regex.finditer(text):
                surface = match.group(0)
                entry = lookup.get(surface.casefold() if ignore_case else surface)
                if entry is None:
                    continue
                found.append(Span(match.start(), match.end(), entry[0],
                                  surface, P_GAZETTEER, "gazetteer"))
        return found

    # ------------------------------------------------------------- publico
    def replacements_for(self, text: str, context: str = "") -> List[Replacement]:
        """Reemplazos calculados para esta unidad (vacio si no hay nada que tocar)."""
        return self._cache.get((text, context), [])

    def anonymize_plain(self, text: str, context: str = "") -> str:
        """Anonimiza una cadena suelta, analizandola si hiciera falta."""
        from .runs import apply_to_text
        if not self._primed:
            self.prime([(text, context)])
        elif (text, context) not in self._cache:
            spans = list(iter_regex_spans(text, self.level, context))
            if self._gazetteer is not None:
                # Que un metadato o un titulo suelto reciba el mismo marcador que
                # la misma entidad en el cuerpo del documento.
                spans.extend(self._gazetteer_spans(self._gazetteer, text))
            spans = resolve_overlaps(spans)
            replacements = [
                (s.start, s.end, self.registry.marker_for(s.kind, s.text)) for s in spans
            ]
            self._cache[(text, context)] = replacements
            self.total_replacements += len(replacements)
        return apply_to_text(text, self.replacements_for(text, context))

    def stats(self) -> dict:
        return {
            "total": self.total_replacements,
            "labels": self.registry.markers_in_order(),
            "by_kind": self.registry.counts_by_kind(),
            "engine": self.engine_name,
            "doc_lang": self.doc_lang,
            "level": self.level_name,
            "warnings": list(self.warnings),
        }
