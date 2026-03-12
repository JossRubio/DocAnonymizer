# Document Anonymizer

Una herramienta web que convierte documentos confidenciales en versiones con etiquetas estructurales, sustituyendo todo el texto por marcadores semánticos (`[TÍTULO DEL DOCUMENTO]`, `[CONTENIDO PÁRRAFO 1]`, etc.) mientras preserva íntegramente el formato visual, el layout y la estructura del archivo original.

Útil para compartir la estructura de un documento sin exponer su contenido: plantillas, auditorías de formato, revisiones de layout o pruebas de maquetación.

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| Frontend | HTML / CSS / JavaScript vanilla |
| Word (.docx) | python-docx + lxml (manipulación XML directa) |
| PowerPoint (.pptx) | python-pptx |
| Excel (.xlsx) | openpyxl |

---

## Funcionalidades

### Word (.docx) — Soporte completo
Manipula el XML interno del documento a nivel de elemento `<w:t>`, sin tocar ningún otro nodo. Esto garantiza que posiciones, anclajes de imágenes flotantes, columnas y estilos permanecen bit a bit idénticos al original.

| Elemento detectado | Etiqueta generada |
|---|---|
| Título del documento | `[TÍTULO DEL DOCUMENTO]` |
| Títulos de sección (Heading 1-2) | `[TÍTULO SECCIÓN N]` |
| Subtítulos (Heading 3 / Subtitle) | `[SUBTÍTULO N.M]` |
| Párrafos de contenido | `[CONTENIDO PÁRRAFO N]` |
| Elementos de lista | `[ELEMENTO LISTA N]` |
| Celdas de tabla | `[CELDA TABLA FILA-N COL-M]` |
| Cuadros de texto flotantes | `[CUADRO DE TEXTO N]` |
| Encabezado | `[ENCABEZADO]` |
| Pie de página | `[PIE DE PÁGINA]` |

**Preservación de layout:** cuando el texto original ocupa más líneas que la etiqueta, se añaden saltos de línea blandos (`<w:br>`) dentro del mismo run para mantener la altura del párrafo y evitar el desplazamiento de imágenes y elementos flotantes.

### PowerPoint (.pptx) — Soporte completo
Procesa cada shape de cada diapositiva preservando posición, tamaño y estilos visuales.

| Elemento | Etiqueta generada |
|---|---|
| Título de diapositiva | `[TÍTULO DIAPOSITIVA N]` |
| Subtítulo / cuerpo | `[SUBTÍTULO DIAPOSITIVA N]` |
| Cuadros de texto adicionales | `[TEXTO CUERPO N]` |
| Shapes / formas con texto | `[ETIQUETA FORMA N]` |
| Tablas | `[CELDA TABLA DIAP-N FILA-M COL-K]` |
| Notas del presentador | `[NOTA PRESENTADOR DIAP-N]` |
| Pie de diapositiva | `[PIE DIAPOSITIVA]` |

### Excel (.xlsx) — En desarrollo
La funcionalidad básica de anonimización de celdas está implementada, pero el soporte de casos avanzados (celdas combinadas, formatos condicionales, rangos con nombre) se encuentra en fase de desarrollo activo.

### PDF — En desarrollo
El soporte para documentos PDF está planificado para una versión futura.

---

## Interfaz Web

- **Drag & Drop** — arrastra el archivo o haz clic para seleccionarlo
- **Barra de progreso** — indicador animado durante el procesamiento
- **Vista previa de etiquetas** — lista de todas las etiquetas generadas en el documento
- **Descarga directa** — botón para descargar el archivo anonimizado
- **Historial de sesión** — registro de todos los archivos procesados durante la sesión actual

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

# 3. Lanzar el servidor
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Abre `http://localhost:8001` en el navegador.

### Inicio rápido (scripts incluidos)

| Sistema | Comando |
|---|---|
| Windows | Doble clic en `start.bat` |
| Linux / macOS | `bash start.sh` |

Ambos scripts verifican automáticamente si las dependencias están instaladas y abren el navegador tras arrancar el servidor.

---

## Estructura del proyecto

```
DocAnonymizer/
├── backend/
│   ├── main.py                      # API FastAPI
│   └── processors/
│       ├── word_processor.py        # Procesador .docx (XML directo)
│       ├── pptx_processor.py        # Procesador .pptx
│       └── excel_processor.py       # Procesador .xlsx
├── frontend/
│   └── index.html                   # Interfaz web (vanilla JS)
├── temp_files/                      # Archivos temporales (generado en runtime)
├── requirements.txt
├── start.bat                        # Inicio en Windows
└── start.sh                         # Inicio en Linux/macOS
```

---

## API

### `POST /api/process`
Recibe un archivo `.docx`, `.pptx` o `.xlsx` via `multipart/form-data` y devuelve un JSON con las estadísticas y la URL de descarga.

```json
{
  "status": "success",
  "filename": "documento_anonimizado.docx",
  "stats": {
    "elementos_procesados": 42,
    "tipo_archivo": "docx",
    "etiquetas_usadas": ["[TÍTULO DEL DOCUMENTO]", "[CONTENIDO PÁRRAFO 1]", "..."]
  },
  "download_url": "/api/download/<job_id>"
}
```

### `GET /api/download/{job_id}`
Descarga el archivo procesado. Los archivos temporales se eliminan del servidor tras la descarga.

### `GET /api/health`
Health check del servidor. Devuelve `{"status": "ok"}`.
