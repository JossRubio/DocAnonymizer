"""Capa de acceso a spaCy, aislada del resto del paquete.

Todo lo que pueda faltar en el entorno vive aqui: si spaCy no esta instalado o
los modelos no se han descargado, este modulo lo dice y el motor sigue
funcionando solo con reglas. El modo "Obtencion estructura documento" no depende
de nada de esto.
"""

import importlib.util
import os
import re
import threading
from typing import Dict, List, Optional, Sequence

from .levels import NER_LABEL_MAP, NER_MIN_LEVEL
from .patterns import P_NER
from .spans import Span

MODEL_BY_LANG = {"es": "es_core_news_md", "en": "en_core_web_sm"}
SUPPORTED_DOC_LANGS = tuple(MODEL_BY_LANG)

# Limite de caracteres que spaCy procesa por documento.
_MAX_LENGTH = 3_000_000


class PiiUnavailableError(RuntimeError):
    """El modo PII se ha exigido con NER y el NER no esta disponible."""


_MODELS: Dict[str, Optional[object]] = {}
_LOCK = threading.Lock()


def spacy_available() -> bool:
    return importlib.util.find_spec("spacy") is not None


def model_available(lang: str) -> bool:
    name = MODEL_BY_LANG.get(lang)
    if not name:
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def require_spacy_enabled() -> bool:
    """Si esta activo, la falta de NER es un error en vez de una degradacion."""
    return os.environ.get("PII_REQUIRE_SPACY", "").strip().lower() in ("1", "true", "yes")


def get_nlp(lang: str):
    """Modelo cargado una sola vez por proceso.

    Cachea tambien el fallo (``None``) para no reintentar una carga costosa en
    cada peticion cuando el modelo no esta instalado.
    """
    name = MODEL_BY_LANG.get(lang)
    if not name:
        return None
    if name in _MODELS:
        return _MODELS[name]
    with _LOCK:
        if name in _MODELS:                       # otra hebra lo cargo mientras esperabamos
            return _MODELS[name]
        model = None
        try:
            import spacy
            # Se excluye solo lo que no alimenta al NER: el tok2vec es compartido
            # y quitarlo degradaria la deteccion.
            model = spacy.load(name, exclude=["lemmatizer", "attribute_ruler", "textcat"])
            model.max_length = _MAX_LENGTH
        except Exception:
            model = None
        _MODELS[name] = model
        return model


# --------------------------------------------------------- deteccion de idioma
# Solo hay que distinguir dos idiomas, asi que el conteo de palabras vacias basta
# y evita una dependencia mas.
_STOP_ES = {
    "de", "la", "el", "y", "que", "en", "los", "del", "las", "por", "con",
    "para", "una", "un", "su", "al", "como", "no", "es", "se", "lo", "mas",
    "o", "este", "esta", "son", "fue", "ha", "han", "sus", "pero", "sobre",
}
_STOP_EN = {
    "the", "of", "and", "to", "in", "a", "is", "that", "for", "it", "as",
    "with", "was", "on", "are", "be", "by", "this", "from", "or", "an",
    "not", "have", "has", "their", "but", "about", "which",
}
_WORD_RE = re.compile(r"[a-záéíóúüñ]+")


def detect_lang(texts: Sequence[str], fallback: str = "es") -> str:
    """Idioma predominante del documento.

    El idioma de las etiquetas lo elige el usuario y no tiene por que coincidir
    con el del documento, asi que el modelo se escoge a partir del texto real.
    """
    sample = " ".join(texts)[:20000].lower()
    words = _WORD_RE.findall(sample)
    if len(words) < 20:
        return fallback
    es = sum(1 for w in words if w in _STOP_ES)
    en = sum(1 for w in words if w in _STOP_EN)
    if es == 0 and en == 0:
        return fallback
    if es >= en * 1.15:
        return "es"
    if en > es * 1.15:
        return "en"
    return fallback


# ------------------------------------------------------- filtrado de ruido
# Los modelos de spaCy estan entrenados con textos periodisticos, y en documentos
# de oficina producen bastante ruido: toman por nombres propios los titulos en
# mayusculas ("PERITAJE", "USO INTERNO"), las cabeceras de tabla ("Teléfono",
# "Tasa") e incluso alguna fecha. Estos filtros descartan ese ruido; todos son
# conservadores, porque descartar de mas significa dejar escapar un dato.

# Terminos genericos de documento y de negocio. Una entidad formada solo por
# estas palabras no identifica a nadie.
_GENERIC_TERMS = {
    # estructura de documento
    "informe", "reporte", "resumen", "indice", "contenido", "anexo", "apartado",
    "seccion", "capitulo", "titulo", "subtitulo", "pagina", "tabla", "cuadro",
    "grafico", "figura", "listado", "detalle", "registro", "ficha", "historial",
    "documento", "archivo", "formulario", "plantilla", "version", "borrador",
    # negocio y proceso
    "gestion", "proceso", "flujo", "procedimiento", "control", "seguimiento",
    "analisis", "evaluacion", "revision", "validacion", "asignacion", "denuncia",
    "resolucion", "liquidacion", "inspeccion", "peritaje", "cierre", "alerta",
    "fraude", "legal", "actuarial", "siniestro", "siniestros", "poliza",
    "polizas", "asegurado", "asegurados", "cartera", "prima", "primas",
    "cobertura", "vencimiento", "corte", "tasa", "indice", "retencion",
    "satisfaccion", "cliente", "clientes", "usuario", "usuarios", "proveedor",
    "departamento", "area", "division", "unidad", "equipo", "oficina",
    "sucursal", "centro", "costos", "producto", "productos", "servicio",
    "proyecto", "programa", "plan", "presupuesto", "contrato", "acuerdo",
    "salud", "vida", "hogar", "auto", "integral", "complementario",
    "ingenieria", "software", "sistema", "sistemas", "datos", "informacion",
    "personal", "personales", "recursos", "humanos", "administracion",
    "finanzas", "contabilidad", "ventas", "marketing", "operaciones",
    "calidad", "produccion", "logistica", "compras", "tecnologia",
    # estado y clasificacion
    "activo", "activos", "activa", "activas", "vigente", "vigentes", "interno",
    "internos", "externo", "confidencial", "restringido", "publico", "privado",
    "aprobado", "rechazado", "rechazo", "pendiente", "estable", "urgente",
    "total", "totales", "general", "anual", "mensual", "semestral", "trimestral",
    "diario", "global", "promedio", "estado", "tipo", "fecha", "hora", "numero",
    "telefono", "movil", "celular", "correo", "email", "direccion", "domicilio",
    "nombre", "apellido", "edad", "sexo", "genero", "grupo", "nivel", "categoria",
    "observaciones", "notas", "comentarios", "descripcion", "clasificacion",
    # cargos y funciones
    "jefe", "jefa", "gerente", "director", "directora", "encargado",
    "encargada", "responsable", "supervisor", "supervisora", "coordinador",
    "coordinadora", "analista", "asistente", "tecnico", "tecnica",
    "especialista", "consultor", "auxiliar", "operario", "empleado",
    "empleada", "trabajador", "socio", "titular", "beneficiario",
    "parentesco", "cargo", "puesto", "funcion", "laboral", "profesional",
    "senior", "junior", "semestral", "innovacion", "desarrollo",
    "sobresaliente", "insuficiente", "cumple", "supera", "deficiente",
    "manager", "supervisor", "analyst", "assistant", "director", "lead",
    "uso", "acceso", "resultado", "resultados", "objetivo", "objetivos",
    # ingles
    "report", "summary", "overview", "index", "content", "section", "chapter",
    "title", "page", "table", "chart", "figure", "detail", "record", "file",
    "management", "process", "flow", "control", "analysis", "review", "status",
    "type", "date", "time", "number", "phone", "mobile", "mail", "address",
    "name", "age", "gender", "group", "level", "category", "notes", "total",
    "annual", "monthly", "average", "active", "internal", "external", "public",
    "private", "approved", "rejected", "pending", "department", "area", "team",
    "office", "branch", "product", "service", "project", "plan", "budget",
    "contract", "data", "information", "personal", "resources", "quality",
}

_WORD_SPLIT = re.compile(r"[^\wÀ-ſ]+")
_PARTICLES = {"de", "del", "la", "las", "los", "el", "y", "e", "o", "u",
              "a", "al", "en", "con", "por", "para", "of", "the", "and", "for"}


def _significant_words(text: str):
    from .registry import strip_accents
    words = [w for w in _WORD_SPLIT.split(strip_accents(text).casefold()) if w]
    return [w for w in words if w not in _PARTICLES and len(w) > 1]


def is_noise_entity(text: str, kind: str = "") -> bool:
    """True si la entidad que propone el modelo casi con seguridad no es un dato personal."""
    surface = (text or "").strip()
    if not surface:
        return True

    # Sin ninguna letra: fechas, codigos y cifras que el modelo confunde con nombres.
    if not any(c.isalpha() for c in surface):
        return True

    # Un nombre propio no empieza en minuscula; si lo hace, es un sustantivo comun
    # que el modelo ha marcado por error.
    first = next((c for c in surface if c.isalpha()), "")
    if first and first.islower():
        return True

    words = _significant_words(surface)
    if not words:
        return True

    # Una sola palabra enteramente en mayusculas: es un titulo o una etiqueta de
    # maqueta ("PERITAJE", "VIGENTE"), no el nombre de nadie.
    if len(words) == 1 and surface.isupper():
        return True

    # Compuesta solo por terminos genericos: "USO INTERNO", "Gestion de Siniestros".
    if all(w in _GENERIC_TERMS for w in words):
        return True

    # Una sola palabra propuesta como nombre de persona ("Sobresaliente",
    # "Parentesco"): el modelo marca asi muchos sustantivos capitalizados de
    # cabeceras y celdas. Un nombre real casi siempre trae apellido, y los
    # apellidos sueltos que importan los rescata el diccionario de entidades a
    # partir de la mencion completa.
    if kind == "PERSON" and len(words) == 1:
        return True

    return False


# -------------------------------------------------------------------- NER
def ner_spans(texts: Sequence[str], lang: str, level: int) -> List[List[Span]]:
    """Entidades que el modelo reconoce en cada texto.

    Se procesa en lote con ``nlp.pipe``: sobre documentos de varios cientos de
    parrafos es varias veces mas rapido que llamar al modelo uno a uno.
    """
    empty: List[List[Span]] = [[] for _ in texts]
    if not texts:
        return empty
    model = get_nlp(lang)
    if model is None:
        return empty

    results: List[List[Span]] = []
    try:
        for doc in model.pipe(list(texts), batch_size=64):
            found = []
            for ent in doc.ents:
                kind = NER_LABEL_MAP.get(ent.label_)
                if kind is None or NER_MIN_LEVEL.get(kind, 99) > level:
                    continue
                surface = ent.text.strip()
                if len(surface) < 3 or is_noise_entity(surface, kind):
                    continue
                found.append(Span(ent.start_char, ent.end_char, kind,
                                  ent.text, P_NER, "ner"))
            results.append(found)
    except Exception:
        return empty
    return results
