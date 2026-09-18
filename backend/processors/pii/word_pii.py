"""Anonimizacion de documentos .docx conservando el texto no sensible.

Se edita el XML a nivel de ``<w:t>``, igual que el modo de estructura, para no
perturbar ningun otro nodo: posiciones, anclajes de imagenes y estilos quedan
intactos. La diferencia es que aqui se sustituyen fragmentos, no parrafos
enteros, asi que hace falta el mapeo de offsets de ``runs.py``.

Frente al recorrido del modo de estructura se amplia la cobertura en dos puntos,
y en modo PII no son cosmeticos sino fugas de datos:

  - Se recogen tambien los runs dentro de ``<w:hyperlink>``, ``<w:smartTag>`` e
    ``<w:ins>``. Un correo electronico casi siempre vive dentro de un hyperlink.
  - Se recorren las tablas anidadas y las de encabezados y pies, que
    ``doc.tables`` no devuelve.
"""

from docx import Document
from docx.oxml.ns import qn

from .engine import PiiEngine
from .runs import apply_replacements

_W_P = qn("w:p")
_W_R = qn("w:r")
_W_T = qn("w:t")
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# Propiedades del documento que identifican a personas u organizaciones.
_TEXT_PROPERTIES = ("author", "last_modified_by", "title", "subject",
                    "comments", "keywords", "category")


def _own_t_elements(p_elem):
    """Nodos ``<w:t>`` que pertenecen a este parrafo y no a uno anidado.

    Un parrafo puede contener otros parrafos (cuadros de texto, tablas dentro de
    celdas). Esos se procesan como unidades independientes, asi que aqui se
    descartan para no anonimizar su texto dos veces con offsets equivocados.
    """
    result = []
    for t_elem in p_elem.iter(_W_T):
        parent = t_elem.getparent()
        if parent is None or parent.tag != _W_R:
            continue
        # Sube hasta el parrafo que lo contiene; si no es este, es texto anidado.
        ancestor = parent
        while ancestor is not None and ancestor.tag != _W_P:
            ancestor = ancestor.getparent()
        if ancestor is p_elem:
            result.append(t_elem)
    return result


def _paragraph_text(p_elem) -> str:
    return "".join(t.text or "" for t in _own_t_elements(p_elem))


def _iter_paragraphs(doc):
    """Todos los parrafos del documento, sin repetir ninguno."""
    seen = set()

    def emit(element):
        for p_elem in element.iter(_W_P):
            key = id(p_elem)
            if key not in seen:
                seen.add(key)
                yield p_elem

    yield from emit(doc.element.body)

    for section in doc.sections:
        for part_name in ("header", "footer",
                          "even_page_header", "even_page_footer",
                          "first_page_header", "first_page_footer"):
            part = getattr(section, part_name, None)
            if part is None:
                continue
            try:
                yield from emit(part._element)
            except AttributeError:
                continue


# Cuanto texto del parrafo anterior se arrastra como contexto.
_CONTEXT_CHARS = 90


def iter_texts(doc):
    """Unidades de texto a analizar, en orden de lectura.

    Cada unidad arrastra como contexto el texto del parrafo anterior. En las
    fichas y tablas de clave-valor la etiqueta ("Fecha de nacimiento", "RUT")
    esta en una celda y el valor en la siguiente, es decir en parrafos distintos,
    de modo que sin esto las reglas que dependen de una palabra clave no se
    activarian nunca. El contexto solo habilita reglas que ya existen: nunca
    genera por si mismo una deteccion.
    """
    previous = ""
    for p_elem in _iter_paragraphs(doc):
        text = _paragraph_text(p_elem)
        if text.strip():
            yield (text, previous)
            previous = text[:_CONTEXT_CHARS]


def _anonymize_core_properties(doc, engine) -> int:
    """Limpia los metadatos del archivo.

    Un .docx guarda el nombre de quien lo escribio y su empresa aunque el cuerpo
    quede impecable; es una fuga silenciosa que nadie ve al revisar el documento.
    """
    changed = 0
    try:
        props = doc.core_properties
    except Exception:
        return 0
    for name in _TEXT_PROPERTIES:
        try:
            value = getattr(props, name, None)
        except Exception:
            continue
        if not value or not str(value).strip():
            continue
        text = str(value)
        # El autor es siempre una persona; el resto puede contener cualquier cosa.
        new_value = (engine.registry.marker_for("PERSON", text)
                     if name in ("author", "last_modified_by")
                     else engine.anonymize_plain(text))
        if new_value != text:
            try:
                setattr(props, name, new_value)
                changed += 1
            except Exception:
                continue
    return changed


def anonymize_word(input_path: str, output_path: str,
                   lang: str = "es", level: str = "balanced") -> dict:
    doc = Document(input_path)
    engine = PiiEngine(label_lang=lang, level=level)

    paragraphs = list(_iter_paragraphs(doc))
    engine.prime(iter_texts(doc))

    previous = ""
    for p_elem in paragraphs:
        t_elems = _own_t_elements(p_elem)
        if not t_elems:
            continue
        segments = [t.text or "" for t in t_elems]
        text = "".join(segments)
        replacements = engine.replacements_for(text, previous)
        previous = text[:_CONTEXT_CHARS] if text.strip() else previous
        if not replacements:
            continue
        for t_elem, new_text in zip(t_elems, apply_replacements(segments, replacements)):
            t_elem.text = new_text
            t_elem.set(_XML_SPACE, "preserve")

    meta_changed = _anonymize_core_properties(doc, engine)

    doc.save(output_path)
    stats = engine.stats()
    stats["total"] += meta_changed
    stats["metadata_cleaned"] = meta_changed
    return stats
