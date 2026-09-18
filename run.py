import argparse
import importlib.util
import subprocess
import sys
import time
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
REQUIREMENTS = ROOT / "requirements.txt"
URL = "http://localhost:8001"
HEALTH_URL = f"{URL}/api/health"
MAX_WAIT_SECONDS = 30

# Modulo importable por cada dependencia de requirements.txt.
REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "openpyxl": "openpyxl",
    "lxml": "lxml",
    "spacy": "spacy",
}

# Modelos del modo de anonimizacion. Son opcionales: sin ellos el modo sigue
# funcionando con reglas de patron, pero no detecta nombres de persona.
SPACY_MODELS = ("es_core_news_md", "en_core_web_sm")


def _missing_modules(names):
    missing = []
    for module in names:
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except (ImportError, ValueError):
            missing.append(module)
    return missing


def check_and_install_dependencies():
    missing = _missing_modules(REQUIRED_MODULES)
    if not missing:
        print("Dependencies OK.")
        return
    packages = sorted({REQUIRED_MODULES[m] for m in missing})
    print(f"Missing dependencies ({', '.join(packages)}). Installing...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
        )
        print("Dependencies installed.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: dependency installation failed ({e}).")
        print("The server will start anyway; some features may be unavailable.")


def check_spacy_models(auto_install=False):
    """Avisa (o instala) los modelos de lenguaje del modo de anonimizacion.

    Nunca aborta el arranque: sin modelos el servidor funciona igual y el modo
    de estructura no se ve afectado en absoluto.
    """
    if importlib.util.find_spec("spacy") is None:
        print("NOTE: spaCy is not installed. 'Information anonymization' mode will")
        print("      run with pattern rules only (personal names will NOT be detected).")
        return

    missing = _missing_modules(SPACY_MODELS)
    if not missing:
        print("spaCy models OK.")
        return

    if auto_install:
        for model in missing:
            print(f"Downloading spaCy model {model}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "spacy", "download", model], timeout=900
                )
            except Exception as e:
                print(f"WARNING: could not install {model}: {e}")
        return

    print(f"NOTE: spaCy models not installed: {', '.join(missing)}")
    print("      'Information anonymization' mode will run with pattern rules only,")
    print("      so personal names will NOT be detected. To install them:")
    for model in missing:
        print(f"        {sys.executable} -m spacy download {model}")


def wait_for_server(timeout: int = MAX_WAIT_SECONDS) -> bool:
    """Poll /api/health until the server responds or timeout is reached."""
    print(f"Waiting for server to be ready (max {timeout}s)...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    print(" ready!")
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)
    print(" timed out.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Launch Document Anonymizer.")
    parser.add_argument(
        "--with-models",
        action="store_true",
        help="download the spaCy language models if they are missing",
    )
    args = parser.parse_args()

    check_and_install_dependencies()
    check_spacy_models(auto_install=args.with_models)

    print(f"Starting server on {URL} ...")
    server = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--reload",
        ],
        cwd=str(BACKEND),
    )

    if not wait_for_server():
        print()
        print("ERROR: Server did not start within the expected time.")
        print("Check the output above for error messages.")
        server.terminate()
        sys.exit(1)

    print(f"Opening {URL} in browser...")
    webbrowser.open(URL)

    try:
        server.wait()
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.terminate()
        server.wait()
        print("Server stopped.")


if __name__ == "__main__":
    main()
