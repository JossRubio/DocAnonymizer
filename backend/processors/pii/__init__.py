"""Modo "Anonimizacion de informacion": conserva el texto y retira lo sensible.

A diferencia del modo de estructura, que sustituye todo el contenido por
etiquetas de maquetacion, este modo deja el documento legible y solo reemplaza
los fragmentos que identifican a una persona o revelan datos reservados.
"""

from .engine import PiiEngine
from .excel_pii import anonymize_excel
from .nlp import PiiUnavailableError
from .pptx_pii import anonymize_pptx
from .word_pii import anonymize_word

__all__ = [
    "anonymize_word",
    "anonymize_pptx",
    "anonymize_excel",
    "PiiEngine",
    "PiiUnavailableError",
]
