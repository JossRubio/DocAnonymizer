import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
REQUIREMENTS = ROOT / "requirements.txt"
URL = "http://localhost:8001"


def check_and_install_dependencies():
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "fastapi"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        print("Dependencies not found. Installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
        )
        print("Dependencies installed.")
    else:
        print("Dependencies OK.")


def main():
    check_and_install_dependencies()

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

    print("Waiting for server to be ready...")
    time.sleep(3)

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
