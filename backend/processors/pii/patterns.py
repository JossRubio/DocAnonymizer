"""Reglas deterministas de deteccion de datos sensibles.

Cubren lo que un modelo de lenguaje detecta mal: identificadores, numeros de
contacto, credenciales y codigos de referencia. Los nombres de persona y las
organizaciones los aporta el NER (ver nlp.py).

Sobre los validadores de digito de control: no siempre son excluyentes. Un RUT
ficticio o mal tecleado en un documento real sigue siendo un dato personal y hay
que anonimizarlo, asi que cuando el formato ya es muy distintivo (RUT con
puntos, DNI con letra) el checksum solo refuerza la prioridad. Se exige de
verdad donde el patron es ambiguo por si mismo: tarjetas de credito e IBAN.
"""

import re
from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional

from .levels import BALANCED, FULL, SOFT
from .markers import MARKER_RE
from .spans import Span
from .validators import (valid_cif, valid_dni, valid_iban, valid_luhn,
                         valid_nie, valid_rut)

REQUIRED = "required"   # si el validador falla, se descarta el match
BOOST = "boost"         # si el validador pasa sube la prioridad; si no, se acepta igual

# Prioridades. Mayor gana en caso de solape.
P_SKIP = 999        # marcadores ya presentes: nunca se re-anonimizan
P_ID = 100          # identificadores personales
P_SECRET = 95       # credenciales y claves
P_CONTACT = 90      # email, URL
P_PHONE = 85
P_NET = 80          # IP
P_REF_CTX = 78      # codigos de referencia con palabra clave delante
P_REF = 70          # codigos de referencia por formato
P_MONEY = 65
P_DATE = 60
P_ADDRESS = 55
P_INFRA = 50        # hostname, ruta, base de datos
P_GAZETTEER = 45    # entidades ya conocidas, re-encontradas por texto
P_NER = 40          # lo que aporta el modelo


@dataclass(frozen=True)
class Rule:
    kind: str
    regex: re.Pattern
    priority: int
    min_level: int
    group: int = 0                      # 0 = todo el match; >0 = solo ese grupo
    context: Optional[re.Pattern] = None
    context_window: int = 70
    validator: Optional[Callable[[str], bool]] = None
    validator_mode: str = REQUIRED
    boost: int = 10


def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# --------------------------------------------------------------- contextos
CTX_RUT = _c(r"\bR\.?U\.?[TN]\b|\brol\s+unico\b")
CTX_PASSPORT = _c(r"\bpasaporte\b|\bpassport\b")
CTX_SSN = _c(r"seguridad\s+social|afiliad|\bAf\.|\bAFP\b|\bNAF\b|\bNUSS\b|\bSSN\b|"
             r"\bfonasa\b|\bisapre\b|previsi[oó]n|\bcotizante\b")
CTX_BIRTH = _c(r"naci[dmó]|f\.?\s?nac\b|fecha\s+nac|\bDOB\b|born|date\s+of\s+birth")
CTX_CONTRACT = _c(r"contrato|contract|expediente|acuerdo|p[oó]liza|policy|protocolo")
CTX_INVOICE = _c(r"factura|invoice|albar[aá]n|pedido|presupuesto|\bPO\b|boleta")
CTX_PHONE = _c(r"tel[eé]fono|\btel\b|m[oó]vil|celular|\bfono\b|phone|contacto|whatsapp|llamar")
CTX_POSTAL = _c(r"\bC\.?P\.?\b|c[oó]digo\s+postal|\bzip\b|postal\s+code")
CTX_DB = _c(r"base\s+de\s+datos|database|esquema|schema|instancia|dbname|initial\s+catalog")
CTX_HEALTH = _c(r"diagn[oó]stic|\bCIE-?10\b|patolog|morbilidad")

# Cabeceras de columna o etiquetas que marcan un valor numerico como sensible.
# En Excel decide si se anonimizan los numeros de esa columna (nivel intermedio).
SENSITIVE_HEADER = _c(
    r"salario|sueldo|remunerac|haber|l[ií]quido|bruto|neto|renta|ingreso|"
    r"importe|monto|precio|tarifa|coste|costo|presupuesto|prima|bonific|"
    r"comisi[oó]n|honorario|deuda|saldo|capital|patrimonio|"
    r"edad|\bage\b|peso|altura|\bimc\b|"
    r"\brut\b|\bdni\b|\bnif\b|\bnie\b|c[eé]dula|identidad|pasaporte|"
    r"tel[eé]fono|m[oó]vil|celular|phone|contacto|"
    r"afiliado|seguridad\s+social|"
    r"cuenta|iban|tarjeta|"
    r"salary|amount|price|budget|wage|income|revenue"
)

RULES: List[Rule] = [
    # ---------------------------------------------------------- idempotencia
    # Un marcador ya escrito gana cualquier solape y luego se descarta, de modo
    # que reprocesar un documento no produce [[NOMBRE_1]_2].
    Rule("__SKIP__", MARKER_RE, P_SKIP, SOFT),

    # ------------------------------------------------------- identificadores
    # RUT chileno con puntos: el formato ya es inequivoco.
    Rule("NATIONAL_ID", re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}\s*-\s*[\dkK]\b"),
         P_ID, SOFT, validator=valid_rut, validator_mode=BOOST),
    # RUT sin puntos: ambiguo, se apoya en el contexto.
    Rule("NATIONAL_ID", re.compile(r"\b\d{7,8}\s*-\s*[\dkK]\b"),
         P_ID, SOFT, validator=valid_rut, validator_mode=BOOST, context=CTX_RUT),
    Rule("NATIONAL_ID", re.compile(r"\b\d{8}\s*-?\s*[TRWAGMYFPDXBNJZSQVHLCKE]\b"),
         P_ID, SOFT, validator=valid_dni, validator_mode=BOOST),
    Rule("NATIONAL_ID", re.compile(r"\b[XYZ]\s*-?\s*\d{7}\s*-?\s*[TRWAGMYFPDXBNJZSQVHLCKE]\b"),
         P_ID, SOFT, validator=valid_nie, validator_mode=BOOST),
    Rule("TAX_ID", re.compile(r"\b[ABCDEFGHJNPQRSUVW]\s*-?\s*\d{7}\s*-?\s*[0-9A-J]\b"),
         P_ID, SOFT, validator=valid_cif, validator_mode=REQUIRED),
    Rule("PASSPORT", re.compile(r"\b[A-Z]{2,3}\d{6}[A-Z]?\b"),
         P_ID, SOFT, context=CTX_PASSPORT),
    Rule("SSN", re.compile(r"\b\d{2,3}\s*-\s*\d{6,8}\b"),
         P_ID, SOFT, context=CTX_SSN),
    Rule("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), P_ID, SOFT),

    # ------------------------------------------------------------ financiero
    Rule("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"),
         P_ID, SOFT, validator=valid_iban, validator_mode=REQUIRED),
    Rule("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b"),
         P_ID, SOFT, validator=valid_luhn, validator_mode=REQUIRED),

    # ---------------------------------------------------------- credenciales
    Rule("CREDENTIAL",
         _c(r"\b(?:contrase[nñ]a|password|passwd|pwd|clave|secret)\b\s*[:=]\s*[\"']?([^\s\"',;]{4,})"),
         P_SECRET, SOFT, group=1),
    Rule("API_KEY",
         _c(r"\b(?:api[_-]?key|access[_-]?token|bearer|authorization)\b\s*[:=]?\s*[\"']?([A-Za-z0-9._\-]{16,})"),
         P_SECRET, SOFT, group=1),
    Rule("API_KEY", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), P_SECRET, SOFT),
    Rule("API_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), P_SECRET, SOFT),
    Rule("API_KEY", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), P_SECRET, SOFT),
    Rule("TOKEN", re.compile(r"\bey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
         P_SECRET, SOFT),
    Rule("USERNAME",
         _c(r"\b(?:usuario|user(?:name)?|login|cuenta)\b\s*[:=]\s*[\"']?([A-Za-z0-9._@-]{3,})"),
         P_SECRET, SOFT, group=1),

    # --------------------------------------------------------------- contacto
    Rule("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), P_CONTACT, SOFT),
    Rule("URL", re.compile(r"\bhttps?://[^\s<>\"'\)\]]+"), P_CONTACT, BALANCED),
    Rule("URL", _c(r"\bwww\.[a-z0-9-]+(?:\.[a-z]{2,})+[^\s<>\"'\)\]]*"), P_CONTACT, FULL),
    # Chile: +56 9 XXXX XXXX
    Rule("PHONE", re.compile(r"(?:\+|00)\s?56\s?9\s?\d{4}\s?\d{4}\b"), P_PHONE, SOFT),
    # Espana: 6XX XXX XXX con separadores
    Rule("PHONE", re.compile(r"(?:(?:\+|00)\s?34[\s.-]?)?\b[6789]\d{2}[\s.-]\d{3}[\s.-]?\d{3}\b"),
         P_PHONE, SOFT),
    # Sin separadores: 9 digitos son ambiguos, se exige contexto explicito.
    Rule("PHONE", re.compile(r"\b[6789]\d{8}\b"), P_PHONE, SOFT, context=CTX_PHONE),
    # Internacional generico, siempre con prefijo explicito
    Rule("PHONE", re.compile(r"\+\d{1,3}[\s.()-]?(?:\d[\s.()-]?){6,14}\d"), P_PHONE, SOFT),

    # ---------------------------------------------------------------- tecnico
    Rule("IP", re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?::\d{1,5})?\b"),
        P_NET, BALANCED),
    Rule("PATH", re.compile(r"\\\\[A-Za-z0-9._-]+\\[^\s\"'<>|]+"), P_INFRA, BALANCED),
    Rule("PATH", re.compile(r"\b[A-Za-z]:\\[^\s\"'<>|]{2,}"), P_INFRA, BALANCED),
    Rule("PATH", re.compile(r"(?<![\w/])/(?:etc|var|opt|srv|home|usr|mnt|data)/[^\s\"'<>|]+"),
         P_INFRA, BALANCED),
    Rule("HOSTNAME",
         _c(r"\b[a-z0-9][a-z0-9-]{1,30}\.(?:local|lan|internal|corp|intranet|int|priv)\b"),
         P_INFRA, BALANCED),
    Rule("HOSTNAME", _c(r"\b(?:srv|server|host|node|db|app|web|vm|bbdd)[a-z0-9-]*\d{1,4}\b"),
         P_INFRA, BALANCED),
    Rule("DATABASE",
         _c(r"(?:base\s+de\s+datos|database|esquema|schema|dbname|initial\s+catalog)"
            r"\s*[:=]?\s*[\"']?([A-Za-z_][A-Za-z0-9_]{2,})"),
         P_INFRA, BALANCED, group=1, context=CTX_DB),

    # ------------------------------------------------------------ referencias
    # Codigo con palabra clave delante: "Poliza N. VD-2019-44821"
    Rule("CONTRACT",
         _c(r"\b(?:contrato|contract|expediente|acuerdo|p[oó]liza|policy|protocolo)\b"
            r"[\s\w.º°-]{0,18}?[:\s#]\s*((?-i:[A-Z0-9][A-Z0-9/_.-]{4,}))"),
         P_REF_CTX, BALANCED, group=1, context=CTX_CONTRACT),
    Rule("INVOICE",
         _c(r"\b(?:factura|invoice|albar[aá]n|pedido|presupuesto|boleta)\b"
            r"[\s\w.º°-]{0,18}?[:\s#]\s*((?-i:[A-Z0-9][A-Z0-9/_.-]{4,}))"),
         P_REF_CTX, BALANCED, group=1, context=CTX_INVOICE),
    # Codigo por formato: SIN-2025-03812, TCL-2023-0047, ECA-2024-ONCOL
    Rule("REFERENCE", re.compile(r"\b[A-Z]{2,5}-\d{4}-[A-Z0-9]{2,10}\b"), P_REF, BALANCED),
    Rule("REFERENCE", re.compile(r"\b\d{4}-[A-Z]{2,5}-[A-Z0-9]{2,10}\b"), P_REF, BALANCED),
    # Numero de afiliado o de cliente con su etiqueta delante
    Rule("REFERENCE",
         _c(r"\bn[º°o]?\s*(?:af(?:iliado)?|cliente|socio|miembro|registro)\b"
            r"[\s.:]*((?-i:[A-Z0-9][A-Z0-9/_.-]{3,}))"),
         P_REF_CTX, BALANCED, group=1),

    # -------------------------------------------------------------- economico
    # Prefijo de moneda: $ 2.850.000 / $82.400 / EUR 1.500,00 / UF 3.200 / $42.7B
    Rule("AMOUNT",
         _c(r"(?<![\w.,])(?:US\$|\$|€|£|EUR|USD|CLP|UF|UTM)\s?"
            r"\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?\s?(?:[MKB](?!\w)|millones)?"),
         P_MONEY, BALANCED),
    # Sufijo de moneda: 2.850.000 CLP / 1.500 euros
    Rule("AMOUNT",
         _c(r"(?<![\w.,])\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?\s?"
            r"(?:€|EUR|euros?|USD|US\$|d[oó]lares|CLP|pesos|UF|UTM)\b"),
         P_MONEY, BALANCED),

    # ----------------------------------------------------------------- fechas
    Rule("BIRTHDATE", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
         P_DATE, BALANCED, context=CTX_BIRTH),
    Rule("BIRTHDATE",
         _c(r"\b\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}\b"),
         P_DATE, BALANCED, context=CTX_BIRTH),
    # En nivel total, cualquier fecha corta.
    Rule("BIRTHDATE", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"), P_DATE, FULL),

    # --------------------------------------------------------------- domicilio
    Rule("ADDRESS",
         _c(r"\b(?:c/|calle|avenida|avda?\.?|av\.|plaza|pl\.|paseo|psje\.?|pasaje|camino|"
            r"ctra\.?|carretera|traves[ií]a|ronda|rda\.|pol[ií]gono)\s+"
            r"[A-ZÁÉÍÓÚÑ]"
            r"[\wáéíóúñÁÉÍÓÚÑ'.\s-]{2,45}?"
            r"\s*n?[º°]?\s*\d{1,5}(?:[.,]\d{3})?"
            r"(?:\s*,\s*(?:dpto|depto|of|oficina|piso|casa|block)\.?\s*[\w-]{1,8})?"),
         P_ADDRESS, BALANCED),
    Rule("POSTAL_CODE", re.compile(r"\b\d{5}\b"), P_ADDRESS, FULL, context=CTX_POSTAL),

    # ------------------------------------------------------------------ salud
    Rule("HEALTH_CODE", re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b"),
         P_REF, BALANCED, context=CTX_HEALTH),

    # --------------------------------------------------------------- vehiculo
    Rule("PLATE", re.compile(r"\b\d{4}\s?[BCDFGHJKLMNPRSTVWXYZ]{3}\b"), P_REF, BALANCED),
]


def _context_ok(rule: Rule, text: str, start: int, end: int, extra_context: str) -> bool:
    """True si la regla no exige contexto o si su palabra clave esta cerca.

    ``extra_context`` inyecta contexto externo a la unidad de texto: en Excel es
    la cabecera de la columna, que suele estar muchas filas mas arriba.
    """
    if rule.context is None:
        return True
    window_start = max(0, start - rule.context_window)
    window = text[window_start:min(len(text), end + rule.context_window)]
    if rule.context.search(window):
        return True
    return bool(extra_context and rule.context.search(extra_context))


def iter_regex_spans(text: str, level: int = BALANCED,
                     extra_context: str = "") -> Iterator[Span]:
    """Genera los spans que las reglas activas reconocen en ``text``."""
    if not text:
        return
    for rule in RULES:
        if rule.min_level > level:
            continue
        for match in rule.regex.finditer(text):
            span = match.span(rule.group) if rule.group else match.span()
            start, end = span
            if start < 0 or end <= start:
                continue
            if not _context_ok(rule, text, start, end, extra_context):
                continue
            value = text[start:end]
            priority = rule.priority
            if rule.validator is not None:
                if rule.validator(value):
                    priority += rule.boost
                elif rule.validator_mode == REQUIRED:
                    continue
            yield Span(start, end, rule.kind, value, priority, "regex")
