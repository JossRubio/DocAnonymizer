"""Sustitucion de rangos de caracteres sobre texto repartido en varios segmentos.

Es el nucleo del modo PII. El texto de un parrafo de Word o PowerPoint no es una
cadena: son varios nodos (``<w:t>`` / runs) con formato propio. Una entidad puede
empezar en un segmento y terminar en otro, asi que no sirve un ``str.replace``.

El modulo trabaja sobre ``list[str]`` y no sabe nada de OOXML: cada procesador
solo tiene que extraer los textos de sus segmentos y volcar el resultado.
"""

from bisect import bisect_right
from typing import Iterable, List, Sequence, Tuple

# (inicio, fin, texto_de_reemplazo) con offsets sobre el texto concatenado.
Replacement = Tuple[int, int, str]


def segment_starts(segments: Sequence[str]) -> List[int]:
    """Offset global en el que empieza cada segmento."""
    starts, acc = [], 0
    for s in segments:
        starts.append(acc)
        acc += len(s)
    return starts


def normalize_replacements(replacements: Iterable[Replacement],
                           text_len: int) -> List[Replacement]:
    """Descarta reemplazos invalidos y resuelve solapes por si acaso.

    El motor ya entrega spans disjuntos, pero esta funcion es la ultima linea de
    defensa: si dos se solapasen, ``apply_replacements`` corromperia el texto.
    Ante un solape gana el que empieza antes y, a igualdad, el mas largo.
    """
    clean = []
    for start, end, repl in replacements:
        if start is None or end is None:
            continue
        start, end = int(start), int(end)
        if not (0 <= start < end <= text_len):
            continue
        clean.append((start, end, repl))

    clean.sort(key=lambda r: (r[0], -(r[1] - r[0])))
    out: List[Replacement] = []
    last_end = -1
    for start, end, repl in clean:
        if start < last_end:          # solapa con el anterior aceptado
            continue
        out.append((start, end, repl))
        last_end = end
    return out


def apply_replacements(segments: Sequence[str],
                       replacements: Sequence[Replacement]) -> List[str]:
    """Aplica los reemplazos y devuelve los segmentos resultantes.

    Cuando un rango cruza varios segmentos, el texto de reemplazo entra entero en
    el primero (el que aporta el formato), los intermedios quedan vacios y del
    ultimo se conserva solo la cola posterior al rango. Los segmentos vacios NO
    se eliminan: borrar un ``<w:r>`` puede arrastrar propiedades del parrafo.
    """
    out = list(segments)
    if not out or not replacements:
        return out

    starts = segment_starts(out)
    total = starts[-1] + len(out[-1])
    ordered = normalize_replacements(replacements, total)

    # De derecha a izquierda: los offsets de los reemplazos pendientes siguen
    # siendo validos porque solo afectan a posiciones anteriores a la ya tocada.
    for start, end, repl in reversed(ordered):
        i = bisect_right(starts, start) - 1
        j = bisect_right(starts, end - 1) - 1
        local_start = start - starts[i]
        local_end = end - starts[j]
        if i == j:
            out[i] = out[i][:local_start] + repl + out[i][local_end:]
        else:
            out[i] = out[i][:local_start] + repl
            for k in range(i + 1, j):
                out[k] = ""
            out[j] = out[j][local_end:]
    return out


def apply_to_text(text: str, replacements: Sequence[Replacement]) -> str:
    """Version de un solo segmento, para celdas de Excel y titulos sueltos."""
    return apply_replacements([text], replacements)[0]
