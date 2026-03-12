import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from processors.word_processor import process_word
from processors.pptx_processor import process_pptx
from processors.excel_processor import process_excel

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


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/process")
async def process_document(file: UploadFile = File(...)):
    filename = file.filename or "document"
    ext = Path(filename).suffix.lower()

    if ext not in (".docx", ".pptx", ".xlsx"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    job_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{job_id}_input{ext}"
    output_path = TEMP_DIR / f"{job_id}_output{ext}"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        if ext == ".docx":
            stats = process_word(str(input_path), str(output_path))
            tipo = "docx"
        elif ext == ".pptx":
            stats = process_pptx(str(input_path), str(output_path))
            tipo = "pptx"
        else:
            stats = process_excel(str(input_path), str(output_path))
            tipo = "xlsx"
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)

    stem = Path(filename).stem
    output_filename = f"{stem}_anonimizado{ext}"

    return JSONResponse({
        "status": "success",
        "filename": output_filename,
        "stats": {
            "elementos_procesados": stats["total"],
            "tipo_archivo": tipo,
            "etiquetas_usadas": stats["labels"],
        },
        "download_url": f"/api/download/{job_id}",
        "job_id": job_id,
    })


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    matches = list(TEMP_DIR.glob(f"{job_id}_output.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="File not found or expired")
    output_path = matches[0]
    ext = output_path.suffix.lower()
    media_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=f"documento_anonimizado{ext}",
    )
