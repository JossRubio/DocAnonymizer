# Document Anonymizer

Una herramienta web que procesa documentos de Office preservando íntegramente su formato visual, su layout y su estructura. Ofrece **dos modos de trabajo** según lo que necesites compartir:

| Modo (nombre en la interfaz) | Qué hace | Para qué sirve |
|---|---|---|
| **Anonimización de información** | Conserva todo el texto y sustituye únicamente los fragmentos que identifican a alguien o revelan datos reservados: `El desarrollador [NOMBRE_1] declara haber…` | Compartir un documento **legible** sin exponer datos personales: informes, fichas, expedientes |
| **Obtención estructura documento** | Sustituye **todo** el texto por etiquetas de maquetación: `[TÍTULO SECCIÓN 1]`, `[CONTENIDO PÁRRAFO 2]` | Compartir la **maqueta** de un documento sin su contenido: plantillas, auditorías de formato, pruebas de layout |

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| Frontend | HTML / CSS / JavaScript vanilla |
| Word (.docx) | python-docx + lxml (manipulación XML directa) |
| PowerPoint (.pptx) | python-pptx |
| Excel (.xlsx) | openpyxl |
| Detección de datos personales | spaCy (NER local, sin conexión) + reglas de patrón |

Todo el procesamiento es **local**. No se envía ningún dato a servicios externos y no se requiere ninguna clave de API.

---

## Modo «Anonimización de información»

Detecta y sustituye datos sensibles dejando intacto el resto del texto. Combina dos mecanismos:

- **Reglas deterministas** para lo que tiene formato reconocible: RUT chileno (módulo 11), DNI/NIE/CIF español, IBAN (módulo 97), tarjetas (Luhn), correos, teléfonos, IPs, rutas, claves de API, tokens, importes, códigos de referencia y direcciones postales.
- **Reconocimiento de entidades (spaCy)** para nombres de persona, organizaciones y ubicaciones, que no tienen un formato fijo.

Además, tres mecanismos de apoyo que resuelven los fallos típicos del reconocimiento de entidades en documentos de oficina:

- **Refuerzo por diccionario.** Una vez identificada una persona, sus apariciones parciales se rescatan en todo el documento. Si «Rodrigo Andrade Peña» aparece en un párrafo y «R. Andrade» en una celda de tabla, ambas reciben el mismo marcador.
- **Contexto del elemento anterior.** En las fichas y tablas de clave-valor, la etiqueta («Fecha de nacimiento», «RUT») y su valor están en celdas distintas. Cada fragmento arrastra el texto del anterior como contexto, de modo que las reglas que dependen de una palabra clave se activan igualmente. En Excel el mismo papel lo cumple la cabecera de la columna.
- **Filtro de ruido.** Los modelos de spaCy están entrenados con textos periodísticos y en documentos de oficina confunden con nombres propios los títulos en mayúsculas («PERITAJE»), las cabeceras de tabla («Teléfono», «Parentesco») y los cargos («Jefe de Ingeniería»). Se descartan las entidades sin letras, las que empiezan en minúscula, las palabras sueltas en mayúsculas y las compuestas solo por términos genéricos. La lista de términos vive en `backend/processors/pii/nlp.py` y se puede ampliar según el vocabulario de tus documentos.

### Consistencia de marcadores

La misma entidad recibe **siempre** el mismo marcador en todo el documento, incluidas sus formas parciales:

```
Juan Miguel Correa  ->  [NOMBRE_1]
Juan Miguel         ->  [NOMBRE_1]
Correa              ->  [NOMBRE_1]
```

Cuando un nombre parcial encaja con **dos** personas distintas, recibe su propio marcador en lugar de fundirlas: separar por error lo que es una sola persona es un fallo mucho menos grave que unir a dos personas distintas.

### Niveles de anonimización

| Nivel | Qué cubre |
|---|---|
| **Suave** | Solo detecciones de alta confianza: identificadores con dígito de control, correos, teléfonos, credenciales, claves de API y nombres de persona. No toca importes, direcciones, organizaciones, datos técnicos ni valores numéricos de Excel |
| **Intermedio** *(por defecto)* | Lo anterior más organizaciones, direcciones, importes con símbolo de moneda, números de contrato/factura/póliza, fechas de nacimiento, IPs, hosts, rutas y bases de datos. En Excel, los valores numéricos se anonimizan **solo si la cabecera de su columna** indica que son sensibles («Salario», «RUT», «Edad»…) |
| **Total** | Lo anterior más ubicaciones, códigos postales, cualquier fecha, URLs públicas y **todos** los valores numéricos de Excel. Máxima protección, más falsos positivos |

> **Sobre el nivel intermedio en Excel:** el sistema no «razona» sobre el significado de cada columna. Lo que hace es propagar el texto de la cabecera como contexto de todas las celdas de esa columna, de modo que las reglas que dependen de una palabra clave se activan aunque esa palabra esté decenas de filas más arriba.

### Marcadores generados

Formato `[TIPO_n]`, numerados por tipo y en orden de aparición. Se traducen según el idioma de etiquetas elegido.

| Tipo | Español | Inglés |
|---|---|---|
| Persona | `[NOMBRE_n]` | `[NAME_n]` |
| Organización | `[ORGANIZACION_n]` | `[ORGANIZATION_n]` |
| Ubicación | `[UBICACION_n]` | `[LOCATION_n]` |
| Dirección postal | `[DIRECCION_n]` | `[ADDRESS_n]` |
| Correo electrónico | `[EMAIL_n]` | `[EMAIL_n]` |
| Teléfono | `[TELEFONO_n]` | `[PHONE_n]` |
| Identificador nacional (RUT, DNI, NIE) | `[ID_NACIONAL_n]` | `[NATIONAL_ID_n]` |
| Identificador fiscal (CIF) | `[ID_FISCAL_n]` | `[TAX_ID_n]` |
| Pasaporte | `[PASAPORTE_n]` | `[PASSPORT_n]` |
| Seguridad social / afiliado | `[NUM_SEGURIDAD_SOCIAL_n]` | `[SSN_n]` |
| Fecha de nacimiento | `[FECHA_NACIMIENTO_n]` | `[BIRTH_DATE_n]` |
| IBAN / tarjeta | `[IBAN_n]` / `[TARJETA_n]` | `[IBAN_n]` / `[CARD_n]` |
| Importe | `[IMPORTE_n]` | `[AMOUNT_n]` |
| Contrato / factura / referencia | `[CONTRATO_n]` / `[FACTURA_n]` / `[REFERENCIA_n]` | `[CONTRACT_n]` / `[INVOICE_n]` / `[REFERENCE_n]` |
| Usuario / credencial / clave / token | `[USUARIO_n]` / `[CREDENCIAL_n]` / `[CLAVE_API_n]` / `[TOKEN_n]` | `[USERNAME_n]` / `[CREDENTIAL_n]` / `[API_KEY_n]` / `[TOKEN_n]` |
| IP / host / URL / ruta / BBDD | `[IP_n]` / `[HOST_n]` / `[URL_n]` / `[RUTA_n]` / `[BBDD_n]` | `[IP_n]` / `[HOSTNAME_n]` / `[URL_n]` / `[PATH_n]` / `[DATABASE_n]` |
| Dato de salud (CIE-10) | `[DATO_SALUD_n]` | `[HEALTH_DATA_n]` |
| Valor numérico (Excel) | `[VALOR_n]` | `[VALUE_n]` |

### Comportamiento por formato

- **Word** — además del cuerpo, se procesan tablas (incluidas las anidadas), cuadros de texto, encabezados y pies, y el texto dentro de hipervínculos y marcas de control de cambios. Se limpian los metadatos del archivo (autor, empresa, título…).
- **PowerPoint** — formas, grupos anidados, tablas y notas del presentador. **No se elimina ningún párrafo**: viñetas y saltos de línea se conservan.
- **Excel** — las **fórmulas no se tocan nunca** (alterarlas dejaría el libro con `#REF!`). Los nombres de hoja solo se renombran si contienen datos personales y ninguna fórmula los referencia. También se procesan comentarios de celda y títulos de gráfico.

### Reprocesar un documento ya anonimizado

Es idempotente: los marcadores existentes se reconocen y no se vuelven a envolver. No se producen anidamientos como `[[NOMBRE_1]_2]`.

---

## Modo «Obtención estructura documento»

Comportamiento original de la herramienta, sin cambios. Manipula el XML interno a nivel de elemento `<w:t>` sin tocar ningún otro nodo, de modo que posiciones, anclajes de imágenes flotantes, columnas y estilos permanecen idénticos al original.

### Word (.docx)

| Elemento detectado | Etiqueta generada |
|---|---|
| Título del documento | `[TÍTULO DEL DOCUMENTO]` |
| Títulos de sección (Heading 1-2) | `[TÍTULO SECCIÓN N]` |
| Subtítulos (Heading 3 / Subtitle) | `[SUBTÍTULO N.M]` |
| Párrafos de contenido | `[CONTENIDO PÁRRAFO N]` |
| Elementos de lista | `[ELEMENTO LISTA N]` |
| Celdas de tabla | `[CELDA TABLA FILA-N COL-M]` |
| Cuadros de texto flotantes | `[CUADRO DE TEXTO N]` |
| Encabezado / pie | `[ENCABEZADO]` / `[PIE DE PÁGINA]` |

**Preservación de layout:** cuando el texto original ocupa más líneas que la etiqueta, se añaden saltos de línea blandos (`<w:br>`) dentro del mismo run para mantener la altura del párrafo.

### PowerPoint (.pptx)

| Elemento | Etiqueta generada |
|---|---|
| Título / subtítulo de diapositiva | `[TÍTULO DIAPOSITIVA N]` / `[SUBTÍTULO DIAPOSITIVA N]` |
| Cuadros de texto y formas | `[TEXTO CUERPO N]` / `[ETIQUETA FORMA N]` |
| Tablas | `[CELDA TABLA DIAP-N FILA-M COL-K]` |
| Notas del presentador | `[NOTA PRESENTADOR DIAP-N]` |
| Pie de diapositiva | `[PIE DIAPOSITIVA]` |

### Excel (.xlsx)

| Elemento | Etiqueta generada |
|---|---|
| Nombre de hoja | `(NOMBRE HOJA N)` |
| Cabecera (fila 1) | `[CABECERA COL-N]` |
| Dato de texto / valor numérico | `[DATO FILA-N COL-M]` / `[VALOR NUMÉRICO N]` |
| Fórmula | `[FÓRMULA N]` |
| Título de gráfico | `[TÍTULO GRÁFICO N]` |

> **Nota:** el nombre de hoja usa paréntesis porque Excel no permite `[` ni `]` en títulos de hoja.

### PDF — En desarrollo

El soporte para documentos PDF está planificado para una versión futura.

---

## Interfaz Web

- **Selector de modo** — elige entre anonimización de información y obtención de estructura
- **Selector de nivel** — suave / intermedio / total (solo en modo anonimización)
- **Drag & Drop** — arrastra el archivo o haz clic para seleccionarlo
- **Barra de progreso** e **historial de sesión**
- **Panel de avisos** — informa si la detección se ha degradado (por ejemplo, si falta spaCy)
- **Tema claro/oscuro** e **idioma de interfaz** (ES/EN), independientes del idioma de las etiquetas

---

## Instalación y ejecución local

### Requisitos previos
- Python 3.10 o superior
- pip

### Pasos

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd DocAnonymizer

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar los modelos de lenguaje (recomendado para el modo de anonimización)
python -m spacy download es_core_news_md
python -m spacy download en_core_web_sm

# 4. Lanzar el servidor
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Abre `http://localhost:8001` en el navegador.

### Sobre los modelos de spaCy

Los modelos **no** están en `requirements.txt` a propósito: no se publican en PyPI, pesan unos 55 MB y, si la descarga falla, harían fallar toda la instalación, dejando sin servicio también al modo de estructura.

Son **opcionales**. Sin ellos la aplicación arranca igual y el modo de anonimización sigue funcionando con las reglas de patrón, pero **no detectará nombres de persona ni organizaciones**. La interfaz lo avisa de forma explícita en el panel de avisos, y la tarjeta «Motor de detección» mostrará `regex-only` en lugar de `spacy+regex`.

Si tu red usa un proxy con inspección TLS, `pip` puede fallar con `CERTIFICATE_VERIFY_FAILED`. Consulta con tu administrador de sistemas antes de desactivar la verificación de certificados.

### Inicio rápido (scripts incluidos)

| Sistema | Comando |
|---|---|
| Cualquier SO | `python run.py` |
| Cualquier SO, instalando modelos | `python run.py --with-models` |
| Windows | Doble clic en `start.bat` |
| Linux / macOS | `bash start.sh` |

---

## Estructura del proyecto

```
DocAnonymizer/
├── backend/
│   ├── main.py                      # API FastAPI
│   └── processors/
│       ├── labels.py                # Etiquetas del modo estructura (ES/EN)
│       ├── word_processor.py        # Estructura .docx (XML directo)
│       ├── pptx_processor.py        # Estructura .pptx
│       ├── excel_processor.py       # Estructura .xlsx
│       └── pii/                     # Modo "Anonimización de información"
│           ├── markers.py           # Taxonomía de marcadores (ES/EN)
│           ├── levels.py            # Niveles suave / intermedio / total
│           ├── patterns.py          # Reglas de patrón
│           ├── validators.py        # Dígitos de control (RUT, DNI, IBAN, Luhn)
│           ├── nlp.py               # spaCy + detección de idioma
│           ├── registry.py          # Consistencia de marcadores
│           ├── engine.py            # Orquestación y resolución de solapes
│           ├── runs.py              # Sustitución por offsets preservando formato
│           ├── word_pii.py          # Anonimización .docx
│           ├── pptx_pii.py          # Anonimización .pptx
│           └── excel_pii.py         # Anonimización .xlsx
├── frontend/
│   └── index.html                   # Interfaz web (vanilla JS)
├── temp_files/                      # Archivos temporales (generado en runtime)
├── requirements.txt
├── requirements-models.txt          # Modelos spaCy (instalación opcional)
├── run.py
├── start.bat                        # Inicio en Windows
└── start.sh                         # Inicio en Linux/macOS
```

---

## API

### `POST /api/process`

Recibe un archivo `.docx`, `.pptx` o `.xlsx` vía `multipart/form-data`.

| Campo | Valores | Por defecto |
|---|---|---|
| `file` | el documento | *(obligatorio)* |
| `mode` | `pii`, `structure` | `structure` |
| `pii_level` | `soft`, `balanced`, `full` | `balanced` |
| `label_lang` | `es`, `en` | `es` |

```json
{
  "status": "success",
  "filename": "documento_anonymized.docx",
  "stats": {
    "elementos_procesados": 18,
    "tipo_archivo": "docx",
    "etiquetas_usadas": ["[NOMBRE_1]", "[EMAIL_1]", "[ID_NACIONAL_1]"],
    "modo": "pii",
    "nivel": "balanced",
    "por_tipo": { "PERSON": 1, "EMAIL": 1, "NATIONAL_ID": 1 },
    "motor": "spacy+regex",
    "idioma_detectado": "es",
    "avisos": []
  },
  "download_url": "/api/download/<job_id>",
  "job_id": "<job_id>"
}
```

### `GET /api/download/{job_id}`
Descarga el archivo procesado.

### `GET /api/modes`
Modos y niveles disponibles.

### `GET /api/health`
Health check. Devuelve `{"status": "ok"}`.

---

## Limitaciones conocidas

El modo de anonimización es **best-effort**: reduce mucho la exposición y hace el documento compartible con bajo riesgo, pero **no garantiza la eliminación completa de datos personales**. No debe ser el único control antes de publicar un documento sensible: revisa siempre el resultado.

**Del reconocimiento de entidades**
- `es_core_news_md` está entrenado con textos periodísticos. En documentos legales, técnicos o formularios su precisión con nombres y organizaciones es menor que la publicada.
- Habrá **falsos negativos** con nombres extranjeros, nombres escritos en MAYÚSCULAS y nombres que coinciden con sustantivos comunes. El refuerzo por diccionario mitiga los casos en que el nombre aparece al menos una vez en un contexto reconocible.
- Es frecuente la confusión persona/organización en empresas con nombre de persona («Martínez e Hijos S.L.»). El dato se anonimiza igual; solo cambia el tipo de marcador.

**De las reglas de patrón**
- Las reglas de dirección postal y de nombre de host son las más frágiles: los límites de una dirección en prosa son ambiguos.
- La regla de importes no distingue una cifra confidencial de una genérica, así que en nivel total es probable la sobre-anonimización en documentos económicos.
- Las reglas que dependen de una palabra clave cercana no se activan si esa palabra está lejos. En tablas se resuelve con la cabecera de columna; en prosa larga, no.

**Estructurales**
- **Texto dentro de imágenes: no cubierto.** No hay OCR; un organigrama o un documento escaneado pasan intactos.
- **Word:** los comentarios, las notas al pie y los campos calculados quedan sin procesar.
- **Hipervínculos:** el texto visible se anonimiza, pero la **URL de destino** no. Un enlace `mailto:` conserva la dirección en su destino.
- **Excel:** en nivel suave las celdas numéricas no se tocan, y el renombrado de hojas es condicional.
- **Formato:** si un dato sensible abarca varios fragmentos con formatos distintos, el marcador hereda el formato del primero.
- **Irreversible:** la correspondencia entre dato y marcador vive solo en memoria durante la petición y no se guarda en ningún sitio, de forma deliberada.
