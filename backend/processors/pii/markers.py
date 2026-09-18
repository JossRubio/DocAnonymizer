"""Taxonomia de marcadores PII y sus plantillas por idioma.

Un marcador tiene la forma ``[TIPO_n]``: el tipo identifica la clase de dato y
``n`` numera las entidades distintas de ese tipo dentro del documento, en orden
de primera aparicion.

Los nombres de hoja de Excel no admiten corchetes, de ahi ``brackets=False``.
"""

import re

# ---------------------------------------------------------------- tipos
# El orden de esta tupla no es significativo; la numeracion es por documento.
KINDS = (
    # --- identidad ---
    "PERSON", "ORG", "LOC", "ADDRESS", "POSTAL_CODE",
    "EMAIL", "PHONE",
    "NATIONAL_ID", "TAX_ID", "PASSPORT", "SSN", "BIRTHDATE",
    # --- economico ---
    "IBAN", "CARD", "AMOUNT", "CONTRACT", "INVOICE", "REFERENCE",
    # --- credenciales ---
    "USERNAME", "CREDENTIAL", "API_KEY", "TOKEN",
    # --- tecnico ---
    "IP", "HOSTNAME", "URL", "PATH", "DATABASE",
    # --- otros ---
    "PLATE", "HEALTH_CODE", "NUMBER",
)

_MARKER_NAMES = {
    "es": {
        "PERSON": "NOMBRE",
        "ORG": "ORGANIZACION",
        "LOC": "UBICACION",
        "ADDRESS": "DIRECCION",
        "POSTAL_CODE": "CP",
        "EMAIL": "EMAIL",
        "PHONE": "TELEFONO",
        "NATIONAL_ID": "ID_NACIONAL",
        "TAX_ID": "ID_FISCAL",
        "PASSPORT": "PASAPORTE",
        "SSN": "NUM_SEGURIDAD_SOCIAL",
        "BIRTHDATE": "FECHA_NACIMIENTO",
        "IBAN": "IBAN",
        "CARD": "TARJETA",
        "AMOUNT": "IMPORTE",
        "CONTRACT": "CONTRATO",
        "INVOICE": "FACTURA",
        "REFERENCE": "REFERENCIA",
        "USERNAME": "USUARIO",
        "CREDENTIAL": "CREDENCIAL",
        "API_KEY": "CLAVE_API",
        "TOKEN": "TOKEN",
        "IP": "IP",
        "HOSTNAME": "HOST",
        "URL": "URL",
        "PATH": "RUTA",
        "DATABASE": "BBDD",
        "PLATE": "MATRICULA",
        "HEALTH_CODE": "DATO_SALUD",
        "NUMBER": "VALOR",
    },
    "en": {
        "PERSON": "NAME",
        "ORG": "ORGANIZATION",
        "LOC": "LOCATION",
        "ADDRESS": "ADDRESS",
        "POSTAL_CODE": "ZIP",
        "EMAIL": "EMAIL",
        "PHONE": "PHONE",
        "NATIONAL_ID": "NATIONAL_ID",
        "TAX_ID": "TAX_ID",
        "PASSPORT": "PASSPORT",
        "SSN": "SSN",
        "BIRTHDATE": "BIRTH_DATE",
        "IBAN": "IBAN",
        "CARD": "CARD",
        "AMOUNT": "AMOUNT",
        "CONTRACT": "CONTRACT",
        "INVOICE": "INVOICE",
        "REFERENCE": "REFERENCE",
        "USERNAME": "USERNAME",
        "CREDENTIAL": "CREDENTIAL",
        "API_KEY": "API_KEY",
        "TOKEN": "TOKEN",
        "IP": "IP",
        "HOSTNAME": "HOSTNAME",
        "URL": "URL",
        "PATH": "PATH",
        "DATABASE": "DATABASE",
        "PLATE": "PLATE",
        "HEALTH_CODE": "HEALTH_DATA",
        "NUMBER": "VALUE",
    },
}


SUPPORTED_MARKER_LANGS = tuple(_MARKER_NAMES)

# Reconoce un marcador ya presente en el texto, en cualquiera de los dos idiomas.
# Se usa para que reprocesar un documento ya anonimizado no anide marcadores.


def marker_name(kind: str, lang: str = "es") -> str:
    """Nombre visible del tipo en el idioma dado (cae a 'es' si no existe)."""
    table = _MARKER_NAMES.get(lang, _MARKER_NAMES["es"])
    return table.get(kind, _MARKER_NAMES["es"].get(kind, kind))


def format_marker(kind: str, n: int, lang: str = "es", brackets: bool = True) -> str:
    """``[NOMBRE_1]``, o ``(NOMBRE_1)`` con ``brackets=False`` (hojas de Excel)."""
    body = f"{marker_name(kind, lang)}_{n}"
    return f"[{body}]" if brackets else f"({body})"
_MK = r"[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1_]{2,40}_\d{1,4}"
MARKER_RE = re.compile(rf"\[{_MK}\]|\({_MK}\)")
