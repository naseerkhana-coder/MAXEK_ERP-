import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
WEB_APP = BASE_DIR / "web_app.py"
PORT = 8501
URL = f"http://localhost:{PORT}"


def _python_executable() -> str:
    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def launch_web_app() -> None:
    if _port_is_open("127.0.0.1", PORT):
        webbrowser.open(URL)
        return

    subprocess.Popen(
        [
            _python_executable(),
            "-m",
            "streamlit",
            "run",
            str(WEB_APP),
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(PORT),
            "--server.headless",
            "false",
        ],
        cwd=str(BASE_DIR),
    )

    for _ in range(30):
        if _port_is_open("127.0.0.1", PORT):
            break
        time.sleep(0.5)

    webbrowser.open(URL)


if __name__ == "__main__":
    launch_web_app()
