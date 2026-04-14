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
