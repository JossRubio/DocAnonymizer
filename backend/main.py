import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from processors.word_processor import process_word
from processors.pptx_processor import process_pptx
from processors.excel_processor import process_excel
from processors.labels import SUPPORTED_LANGS

app = FastAPI(title="Document Anonymizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = Path(__file__).parent.parent / "temp_files"
TEMP_DIR.mkdir(exist_ok=True)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# "structure" es el modo historico: sustituye todo el texto por etiquetas de
# maquetacion. "pii" conserva el texto y solo retira lo que identifica a alguien.
SUPPORTED_MODES = ("structure", "pii")
SUPPORTED_PII_LEVELS = ("soft", "balanced", "full")

_STRUCTURE_PROCESSORS = {
    "docx": process_word,
    "pptx": process_pptx,
    "xlsx": process_excel,
}

_OUTPUT_SUFFIX = {"structure": "_structure", "pii": "_anonymized"}


def _load_pii_processors():
    """Importa el paquete PII solo cuando se usa.

    Es un import perezoso a proposito: el modo de estructura no debe dejar de
    funcionar porque falte spaCy o porque el paquete PII tenga un problema.
    """
    from processors.pii import anonymize_word, anonymize_pptx, anonymize_excel
    return {
        "docx": anonymize_word,
        "pptx": anonymize_pptx,
        "xlsx": anonymize_excel,
    }


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/modes")
async def modes():
    """Modos y niveles disponibles, para que el frontend no los duplique."""
    return {"modes": list(SUPPORTED_MODES), "pii_levels": list(SUPPORTED_PII_LEVELS)}


@app.post("/api/process")
async def process_document(
    file: UploadFile = File(...),
    label_lang: str = Form("es"),
    mode: str = Form("structure"),
    pii_level: str = Form("balanced"),
):
    filename = file.filename or "document"
    ext = Path(filename).suffix.lower()

    if ext not in (".docx", ".pptx", ".xlsx"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    if mode not in SUPPORTED_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    if label_lang not in SUPPORTED_LANGS:
        label_lang = "es"

    if pii_level not in SUPPORTED_PII_LEVELS:
        pii_level = "balanced"

    job_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{job_id}_input{ext}"
    stem = Path(filename).stem
    output_filename = f"{stem}{_OUTPUT_SUFFIX[mode]}{ext}"
    output_path = TEMP_DIR / f"{job_id}_{output_filename}"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    tipo = ext.lstrip(".")

    try:
        if mode == "pii":
            try:
                processor = _load_pii_processors()[tipo]
            except ImportError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Modo de anonimizacion no disponible: {e}",
                )
            # El procesado es sincrono y con spaCy puede tardar segundos: fuera
            # del bucle de eventos para no bloquear el resto de peticiones.
            stats = await run_in_threadpool(
                processor, str(input_path), str(output_path), label_lang, pii_level
            )
        else:
            stats = await run_in_threadpool(
                _STRUCTURE_PROCESSORS[tipo], str(input_path), str(output_path), label_lang
            )
    except HTTPException:
        raise
    except Exception as e:
        # PiiUnavailableError solo aparece si se ha exigido spaCy por entorno.
        if type(e).__name__ == "PiiUnavailableError":
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)

    return JSONResponse({
        "status": "success",
        "filename": output_filename,
        "stats": {
            "elementos_procesados": stats["total"],
            "tipo_archivo": tipo,
            "etiquetas_usadas": stats["labels"],
            "modo": mode,
            "nivel": pii_level if mode == "pii" else None,
            "por_tipo": stats.get("by_kind", {}),
            "motor": stats.get("engine", "structure"),
            "idioma_detectado": stats.get("doc_lang"),
            "avisos": stats.get("warnings", []),
        },
        "download_url": f"/api/download/{job_id}",
        "job_id": job_id,
    })


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    # Files are stored as "{job_id}_{original_stem}_{mode}{ext}"
    matches = [p for p in TEMP_DIR.glob(f"{job_id}_*") if "_input" not in p.name]
    if not matches:
        raise HTTPException(status_code=404, detail="File not found or expired")
    output_path = matches[0]
    ext = output_path.suffix.lower()
    # Recover the original output filename by stripping the job_id prefix
    download_name = output_path.name[len(job_id) + 1:]
    media_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=download_name,
    )
