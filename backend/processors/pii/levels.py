"""Niveles de agresividad de la anonimizacion.

Cada regla de deteccion y cada tipo de entidad del NER declara un nivel minimo.
El nivel elegido por el usuario actua como filtro: se descarta todo lo que exija
un nivel superior al activo.
"""

SOFT = 1
BALANCED = 2
FULL = 3

LEVELS = {"soft": SOFT, "balanced": BALANCED, "full": FULL}
SUPPORTED_LEVELS = tuple(LEVELS)
DEFAULT_LEVEL = "balanced"


def level_value(name: str) -> int:
    """Valor numerico del nivel; cae a BALANCED si el nombre no se reconoce."""
    return LEVELS.get((name or "").lower(), BALANCED)


# Tipos de entidad que aporta el NER de spaCy, y desde que nivel se aceptan.
# spaCy espanol emite PER/ORG/LOC/MISC; el ingles usa PERSON/ORG/GPE/LOC/...
NER_LABEL_MAP = {
    "PER": "PERSON", "PERSON": "PERSON",
    "ORG": "ORG",
    "LOC": "LOC", "GPE": "LOC", "FAC": "LOC",
}

NER_MIN_LEVEL = {
    "PERSON": SOFT,
    "ORG": BALANCED,
    "LOC": FULL,
}

# Celdas numericas de Excel: que hacer en cada nivel.
#   SOFT     -> nunca se tocan
#   BALANCED -> solo si la cabecera de su columna sugiere un dato sensible
#   FULL     -> siempre
NUMERIC_NEVER, NUMERIC_BY_HEADER, NUMERIC_ALWAYS = 0, 1, 2

NUMERIC_POLICY = {
    SOFT: NUMERIC_NEVER,
    BALANCED: NUMERIC_BY_HEADER,
    FULL: NUMERIC_ALWAYS,
}
