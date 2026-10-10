"""Script to render visual checklist and README screenshots deterministically.

Captures:
Capabilities:
- docs/screenshots/classification_result.png
- docs/screenshots/data_generation_result.png
- docs/screenshots/regression_result.png
- docs/screenshots/forecasting_result.png
- docs/screenshots/anomaly_detection_result.png
- docs/screenshots/interpretability_result.png

README Product Tour:
- docs/screenshots/landing_desktop.png
- docs/screenshots/landing_mobile_360.png
- docs/screenshots/table_preview.png
- docs/screenshots/chat_plan.png
- docs/screenshots/result_classification.png

Ensures zero network egress and deterministic rendering from contract fixtures.
"""

from __future__ import annotations

import asyncio
import base64
import functools
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import sys

import httpx
import websockets

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
SCREENSHOTS_DIR = PROJECT_ROOT / "docs" / "screenshots"

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CAPABILITIES = [
    "classification",
    "data_generation",
    "regression",
    "forecasting",
    "anomaly_detection",
    "interpretability",
]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def run_server(port: int) -> http.server.HTTPServer:
    handler = functools.partial(QuietHandler, directory=str(DIST_DIR))
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def capture_via_cdp(port: int) -> bool:
    temp_dir = tempfile.mkdtemp()
    cdp_port = find_free_port()

    cmd = [
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={cdp_port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={temp_dir}",
        "--window-size=1280,800",
        "--disable-gpu",
    ]
    proc = subprocess.Popen(cmd)
    try:
        await asyncio.sleep(1.0)
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Capture Capability Results (full vertical height)
        for cap in CAPABILITIES:
            url = f"http://127.0.0.1:{port}/?capability={cap}"
            encoded = urllib.parse.quote(url, safe="")
            target = httpx.put(f"http://127.0.0.1:{cdp_port}/json/new?{encoded}").json()
            ws_url = target["webSocketDebuggerUrl"]
            async with websockets.connect(ws_url) as ws:
                mid = 1
                async def send(method, params=None):
                    nonlocal mid
                    req = {"id": mid, "method": method, "params": params or {}}
                    mid += 1
                    await ws.send(json.dumps(req))
                    while True:
                        r = json.loads(await ws.recv())
                        if r.get("id") == req["id"]:
                            return r.get("result", {})

                await send("Emulation.setDeviceMetricsOverride", {
                    "width": 1200,
                    "height": 2200,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                })
                await asyncio.sleep(1.0)
                shot = await send("Page.captureScreenshot", {"format": "png"})
                img_bytes = base64.b64decode(shot["data"])
                out_file = SCREENSHOTS_DIR / f"{cap}_result.png"
                out_file.write_bytes(img_bytes)
                print(f"  ✓ Saved {out_file.name} ({len(img_bytes) / 1024:.1f} KB)")

        # 2. Capture README Product Tour Shots
        readme_targets = [
            ("landing_desktop.png", f"http://127.0.0.1:{port}/", 1280, 800, False),
            ("landing_mobile_360.png", f"http://127.0.0.1:{port}/", 360, 640, True),
            ("table_preview.png", f"http://127.0.0.1:{port}/?demo=churn&step=view_table", 1280, 800, False),
            ("chat_plan.png", f"http://127.0.0.1:{port}/?demo=churn&step=chat_plan", 1280, 800, False),
            ("result_classification.png", f"http://127.0.0.1:{port}/?capability=classification", 1280, 950, False),
        ]

        for name, url, width, height, is_mobile in readme_targets:
            encoded = urllib.parse.quote(url, safe="")
            target = httpx.put(f"http://127.0.0.1:{cdp_port}/json/new?{encoded}").json()
            ws_url = target["webSocketDebuggerUrl"]
            async with websockets.connect(ws_url) as ws:
                mid = 1
                async def send(method, params=None):
                    nonlocal mid
                    req = {"id": mid, "method": method, "params": params or {}}
                    mid += 1
                    await ws.send(json.dumps(req))
                    while True:
                        r = json.loads(await ws.recv())
                        if r.get("id") == req["id"]:
                            return r.get("result", {})

                await send("Emulation.setDeviceMetricsOverride", {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 2 if is_mobile else 1,
                    "mobile": is_mobile,
                })
                await asyncio.sleep(1.2)
                shot = await send("Page.captureScreenshot", {"format": "png"})
                img_bytes = base64.b64decode(shot["data"])
                out_file = SCREENSHOTS_DIR / name
                out_file.write_bytes(img_bytes)
                print(f"  ✓ Saved {out_file.name} ({len(img_bytes) / 1024:.1f} KB)")

        return True
    finally:
        proc.terminate()
        proc.wait()


def capture_screenshots() -> bool:
    if not DIST_DIR.exists() or not (DIST_DIR / "index.html").exists():
        print(f"Error: {DIST_DIR} not found. Run 'bun run build' inside frontend/ first.")
        return False

    if not Path(CHROME_BIN).exists():
        print(f"Warning: Chrome binary not found at {CHROME_BIN}. Skipping visual screenshots.")
        return True

    port = find_free_port()
    server = run_server(port)
    print(f"Local preview server started on port {port} serving {DIST_DIR}")

    try:
        ok = asyncio.run(capture_via_cdp(port))
    except Exception as e:
        print(f"Error capturing screenshots: {e}")
        ok = False
    finally:
        server.shutdown()
        server.server_close()
        print("Preview server stopped.")

    return ok


if __name__ == "__main__":
    ok = capture_screenshots()
    sys.exit(0 if ok else 1)
