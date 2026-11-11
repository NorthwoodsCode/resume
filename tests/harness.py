"""CDP test harness for driving headless Chrome.

Stdlib + websockets only — no pytest, no playwright. Each test navigates the
shared page, runs Runtime.evaluate calls over the Chrome DevTools Protocol, and
reports back. Use ChromeSession via `async with` or call start()/stop().
The session also records every request URL and every failed or 4xx/5xx
response (requests / failed_requests), and can emulate print media, media
features, viewports and init scripts.
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets


def _find_chrome():
    for path in (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ):
        if os.path.exists(path):
            return path
    raise RuntimeError("No Chrome/Chromium binary found on PATH")


class ChromeSession:
    def __init__(self, port=9437, chrome_path=None, window=(1280, 820)):
        self.port = port
        self.chrome_path = chrome_path or _find_chrome()
        self.window = window
        self.proc = None
        self.ws = None
        self._id = 0
        self._errors = []
        self._warnings = []
        self._requests = []
        self._failed = []
        self._reqmap = {}

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def start(self):
        # Refuse to attach to a browser that is already listening on the port:
        # a leftover instance would answer with its own (stale) cache.
        try:
            urllib.request.urlopen(
                f"http://localhost:{self.port}/json/version", timeout=1
            ).read()
            raise RuntimeError(
                f"Something already answers on DevTools port {self.port}; "
                f"stop the stale Chrome (pkill -f remote-debugging-port={self.port}) "
                "or use another port"
            )
        except RuntimeError:
            raise
        except Exception:
            pass
        self._profile = tempfile.mkdtemp(prefix="cdp-")
        profile = self._profile
        self._log_path = os.path.join(profile, "chrome.log")
        log_fh = open(self._log_path, "wb")
        self.proc = subprocess.Popen(
            [
                self.chrome_path,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-features=VizDisplayCompositor,Translate",
                "--no-first-run",
                "--no-default-browser-check",
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={profile}",
                f"--window-size={self.window[0]},{self.window[1]}",
                "about:blank",
            ],
            stdout=log_fh,
            stderr=log_fh,
        )
        # Poll up to 30s — runners can be slow on the first profile bootstrap.
        last_err = None
        for _ in range(150):
            if self.proc.poll() is not None:
                self._raise_with_log(
                    f"Chrome exited early with code {self.proc.returncode}"
                )
            try:
                urllib.request.urlopen(
                    f"http://localhost:{self.port}/json/version", timeout=1
                ).read()
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.2)
        else:
            self._raise_with_log(
                f"Chrome DevTools endpoint never became ready in 30s "
                f"(last error: {last_err!r})"
            )
        targets = json.loads(
            urllib.request.urlopen(f"http://localhost:{self.port}/json").read()
        )
        page = next(t for t in targets if t["type"] == "page")
        self.ws = await websockets.connect(
            page["webSocketDebuggerUrl"], max_size=50_000_000
        )
        await self.call("Runtime.enable")
        await self.call("Page.enable")
        await self.call("Network.enable")
        await self.call("Network.setCacheDisabled", {"cacheDisabled": True})

    async def stop(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
            self.proc = None
        profile = getattr(self, "_profile", None)
        if profile and os.path.isdir(profile):
            shutil.rmtree(profile, ignore_errors=True)

    def _raise_with_log(self, message):
        tail = ""
        try:
            with open(self._log_path, "rb") as f:
                data = f.read()[-4000:]
            tail = data.decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            self.proc.kill()
        except Exception:
            pass
        raise RuntimeError(
            message + ("\n--- chrome log tail ---\n" + tail if tail else "")
        )

    async def call(self, method, params=None):
        self._id += 1
        await self.ws.send(
            json.dumps({"id": self._id, "method": method, "params": params or {}})
        )
        while True:
            msg = json.loads(await self.ws.recv())
            self._capture(msg)
            if msg.get("id") == self._id:
                return msg

    def _capture(self, msg):
        m = msg.get("method")
        if m == "Network.requestWillBeSent":
            p = msg["params"]
            self._reqmap[p["requestId"]] = p["request"]["url"]
            self._requests.append(p["request"]["url"])
        elif m == "Network.responseReceived":
            r = msg["params"]["response"]
            if r.get("status", 0) >= 400:
                self._failed.append(f"{r['status']} {r['url']}")
        elif m == "Network.loadingFailed":
            p = msg["params"]
            self._failed.append(
                f"FAILED {p.get('errorText')} {self._reqmap.get(p.get('requestId'), '?')}"
            )
        if m == "Runtime.exceptionThrown":
            self._errors.append(msg["params"]["exceptionDetails"]["text"])
        elif m == "Runtime.consoleAPICalled":
            t = msg["params"]["type"]
            if t in ("error",):
                args = " ".join(
                    str(a.get("value", a.get("description", "")))
                    for a in msg["params"]["args"]
                )
                self._errors.append(f"[{t}] {args}")
            elif t == "warning":
                args = " ".join(
                    str(a.get("value", a.get("description", "")))
                    for a in msg["params"]["args"]
                )
                self._warnings.append(args)

    async def drain(self, timeout=0.25):
        try:
            while True:
                msg = json.loads(
                    await asyncio.wait_for(self.ws.recv(), timeout=timeout)
                )
                self._capture(msg)
        except asyncio.TimeoutError:
            return

    async def goto(self, url, wait=2.5, clear_storage=False):
        """Navigate to url. If clear_storage, wipe localStorage and reload."""
        self._errors.clear()
        self._warnings.clear()
        self._requests.clear()
        self._failed.clear()
        self._reqmap.clear()
        self._id += 1
        await self.ws.send(
            json.dumps(
                {"id": self._id, "method": "Page.navigate", "params": {"url": url}}
            )
        )
        await asyncio.sleep(wait)
        await self.drain()
        if clear_storage:
            await self.eval("try{localStorage.clear()}catch(e){}")
            self._errors.clear()
            self._warnings.clear()
            self._id += 1
            await self.ws.send(
                json.dumps({"id": self._id, "method": "Page.reload"})
            )
            await asyncio.sleep(wait)
            await self.drain()

    async def eval(self, expr, await_promise=False):
        r = await self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        )
        result = r["result"].get("result", {})
        return result.get("value")

    async def emulate_media(self, media="", features=None):
        """Emulate print/screen media and media features such as
        prefers-reduced-motion or prefers-color-scheme."""
        params = {"media": media}
        if features is not None:
            params["features"] = features
        await self.call("Emulation.setEmulatedMedia", params)

    async def add_init_script(self, source):
        """Run `source` before every subsequent page load; returns an id for
        remove_init_script()."""
        r = await self.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})
        return r["result"]["identifier"]

    async def remove_init_script(self, identifier):
        await self.call(
            "Page.removeScriptToEvaluateOnNewDocument", {"identifier": identifier}
        )

    async def set_viewport(self, width, height, mobile=False):
        await self.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile},
        )

    async def clear_viewport(self):
        await self.call("Emulation.clearDeviceMetricsOverride")

    @property
    def requests(self):
        return list(self._requests)

    @property
    def failed_requests(self):
        return list(self._failed)

    @property
    def errors(self):
        return list(self._errors)

    @property
    def warnings(self):
        return list(self._warnings)


def serve_directory(path, port=8766):
    """Spawn a `python3 -m http.server` in the background and return the Popen.

    Caller is responsible for terminating it. Refuses to reuse a port that is
    already being served, so tests never run against a stale server.
    """
    try:
        urllib.request.urlopen(f"http://localhost:{port}/", timeout=1).read()
        raise RuntimeError(
            f"Port {port} is already served; stop the stale server first "
            f"(pkill -f 'http.server {port}')"
        )
    except RuntimeError:
        raise
    except Exception:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1).read()
            return proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"Local server at :{port} failed to start")
