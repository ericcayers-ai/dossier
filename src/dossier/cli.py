import argparse
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn

from .api.app import create_app
from .config import AppConfig


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main():
    parser = argparse.ArgumentParser(description="Open a local Dossier workspace")
    parser.add_argument("--root", required=True, help="folder to browse")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open", action="store_true", help="open the workspace in the default browser")
    args = parser.parse_args()
    config = AppConfig.create(Path(args.root))
    port = args.port or _free_port()
    application = create_app(config)
    url = f"http://127.0.0.1:{port}/?token={config.token}"
    print(f"Dossier URL: {url}", flush=True)
    if args.open:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    uvicorn.run(application, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
