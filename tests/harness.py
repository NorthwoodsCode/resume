"""CDP test harness for driving headless Chrome.

Stdlib + websockets only — no pytest, no playwright. Each test boots a fresh
page, runs Runtime.evaluate calls over the Chrome DevTools Protocol, and
reports back. Use ChromeSession via `async with` or call start()/stop().
"""
import asyncio
import json
import os
import subprocess
import sys
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

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def start(self):
        profile = f"/tmp/cdp-{os.getpid()}-{self.port}"
        self._log_path = f"/tmp/chrome-{os.getpid()}-{self.port}.log"
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

    async def swipe(self, direction="left", pid=None, start_y=400):
        """Simulate a fast 'full swipe' touch flick that satisfies the
        thresholds in the home-page swipe handler.
        """
        import random

        pid = pid or random.randint(100, 99999)
        layouts = {
            "left": (900, 80, start_y, start_y + 8),
            "right": (80, 900, start_y, start_y + 8),
            "up": (640, 645, 700, 100),
            "down": (640, 645, 100, 700),
        }
        sx, ex, sy, ey = layouts[direction]
        return await self.eval(
            "(function(){"
            f"var pid={pid};"
            "var f=function(t,x,y){document.dispatchEvent(new PointerEvent(t,"
            "{pointerType:'touch',clientX:x,clientY:y,button:0,pointerId:pid,"
            "isPrimary:true,bubbles:true}));};"
            f"f('pointerdown',{sx},{sy});"
            f"f('pointermove',{(sx*2+ex)//3},{(sy*2+ey)//3});"
            f"f('pointermove',{(sx+ex*2)//3},{(sy+ey*2)//3});"
            f"f('pointermove',{ex},{ey});"
            f"f('pointerup',{ex},{ey});"
            "})()"
        )

    async def slow_drag(self, dx=-800, dy=8, pid=200):
        """Slow horizontal drag spanning >900ms — should NOT be detected as a swipe."""
        return await self.eval(
            "(async function(){"
            f"var pid={pid};"
            "var f=function(t,x,y){document.dispatchEvent(new PointerEvent(t,"
            "{pointerType:'touch',clientX:x,clientY:y,button:0,pointerId:pid,"
            "isPrimary:true,bubbles:true}));};"
            "var s=function(ms){return new Promise(function(r){setTimeout(r,ms);});};"
            f"var sx=900, sy=400; var ex=sx+({dx}); var ey=sy+({dy});"
            "f('pointerdown',sx,sy);"
            "await s(350); f('pointermove',(sx*2+ex)/3,(sy*2+ey)/3);"
            "await s(350); f('pointermove',(sx+ex*2)/3,(sy+ey*2)/3);"
            "await s(350); f('pointerup',ex,ey);"
            "return 'done';"
            "})()",
            await_promise=True,
        )

    async def click_target(self, selector, pid=300):
        """Simulate a pointerdown→up on an element (for testing the
        'interactive target' exclusion in the swipe handler).
        """
        return await self.eval(
            "(function(){"
            f"var el = document.querySelector({json.dumps(selector)});"
            "if(!el) return false;"
            "var r = el.getBoundingClientRect();"
            "var cx = r.left + r.width/2, cy = r.top + r.height/2;"
            f"var pid={pid};"
            "var f=function(t,x,y){var ev = new PointerEvent(t,"
            "{pointerType:'touch',clientX:x,clientY:y,button:0,pointerId:pid,"
            "isPrimary:true,bubbles:true}); el.dispatchEvent(ev); "
            "document.dispatchEvent(ev);};"
            "f('pointerdown', cx, cy);"
            "f('pointermove', cx - 600, cy + 4);"
            "f('pointerup', cx - 600, cy + 4);"
            "return true;"
            "})()"
        )

    @property
    def errors(self):
        return list(self._errors)

    @property
    def warnings(self):
        return list(self._warnings)


def serve_directory(path, port=8766):
    """Spawn a `python3 -m http.server` in the background and return the Popen.

    Caller is responsible for terminating it.
    """
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
