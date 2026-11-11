"""CDP test harness for driving headless Chrome.

Stdlib + websockets only — no pytest, no playwright. Each test navigates the
shared page, runs Runtime.evaluate calls over the Chrome DevTools Protocol, and
reports back. Use ChromeSession via `async with` or call start()/stop().
The session also records every request URL and every failed or 4xx/5xx
response (requests / failed_requests), and can emulate print media, media
features, viewports and init scripts.

How it works, briefly: Chrome is started headless with --remote-debugging-port,
which exposes an HTTP endpoint listing debuggable targets. We connect a
WebSocket to the page target and exchange JSON messages of the form
{"id", "method", "params"}. Chrome answers each with a message carrying the same
"id"; everything else it sends (no "id") is an event such as a network request
or a console error, which _capture() files away for later assertions.
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
    """Return the first Chrome/Chromium binary found at a well-known path."""
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
    """One headless Chrome instance plus a DevTools connection to its page.

    All tests share a single tab, so state such as localStorage persists
    between navigations unless a test clears it (see goto(clear_storage=True)).
    """

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
        """Launch Chrome, wait for DevTools, and enable the CDP domains we use."""
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
        # A fresh temp profile per run means no cookies, cache or localStorage
        # carry over from earlier runs or from the developer's own browser.
        # stop() deletes it again.
        self._profile = tempfile.mkdtemp(prefix="cdp-")
        profile = self._profile
        self._log_path = os.path.join(profile, "chrome.log")
        # Chrome's output goes to a file so _raise_with_log() can show its tail
        # if startup fails; --no-sandbox and --disable-dev-shm-usage are the
        # usual flags for running Chrome inside containers and CI runners.
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
        # /json lists debuggable targets; the first "page" is the about:blank tab
        # we launched with, and its webSocketDebuggerUrl is our command channel.
        targets = json.loads(
            urllib.request.urlopen(f"http://localhost:{self.port}/json").read()
        )
        page = next(t for t in targets if t["type"] == "page")
        self.ws = await websockets.connect(
            page["webSocketDebuggerUrl"], max_size=50_000_000
        )
        # Each domain only emits events after it is enabled: Runtime gives us
        # console/exception events, Network gives request/response events.
        await self.call("Runtime.enable")
        await self.call("Page.enable")
        await self.call("Network.enable")
        # Bypass the HTTP cache so every navigation really fetches its
        # resources. Tests that inspect c.requests (e.g. lazy CDN loading) would
        # otherwise see nothing for files served from cache.
        await self.call("Network.setCacheDisabled", {"cacheDisabled": True})

    async def stop(self):
        """Close the socket, stop Chrome and delete the temp profile."""
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
        """Kill Chrome and raise RuntimeError with the end of its log attached."""
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
        """Send one CDP command and return its raw response message.

        Messages that arrive while we wait (events, or replies to other ids)
        are passed to _capture() so no console error or request is lost.
        """
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
        """Record network and console events; ignore everything else."""
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
        """Read and record pending events until the socket is quiet for `timeout`s.

        Needed because events only get processed while we are reading the
        socket; after a sleep this catches up on everything that arrived.
        """
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
        # Reset the per-page logs so assertions only see this navigation.
        self._errors.clear()
        self._warnings.clear()
        self._requests.clear()
        self._failed.clear()
        self._reqmap.clear()
        self._id += 1
        # Fire Page.navigate without waiting for its reply: that reply comes back
        # when navigation starts, not when the page has loaded. Instead we sleep
        # a fixed time and then drain events, which is simple and good enough
        # for a static site (the stale reply is ignored by call()'s id match).
        await self.ws.send(
            json.dumps(
                {"id": self._id, "method": "Page.navigate", "params": {"url": url}}
            )
        )
        await asyncio.sleep(wait)
        await self.drain()
        if clear_storage:
            # localStorage can only be cleared from inside a page on the right
            # origin, so load first, clear, then reload so the page boots with
            # empty storage (try/catch: storage may be blocked by a test).
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
        """Evaluate a JavaScript expression in the page and return its value.

        returnByValue makes Chrome serialise the result into JSON (numbers,
        strings, booleans, plain objects) instead of returning a remote object
        handle. Non-serialisable results such as DOM nodes come back as an empty
        object, and a thrown exception as None, so tests return primitives or
        JSON.stringify(...). With await_promise=True a returned Promise is
        awaited first.
        """
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
        # media="print" makes @media print rules apply on screen, with no real
        # print dialog; media="" returns to normal screen rendering.
        params = {"media": media}
        if features is not None:
            params["features"] = features
        await self.call("Emulation.setEmulatedMedia", params)

    async def add_init_script(self, source):
        """Run `source` before every subsequent page load; returns an id for
        remove_init_script()."""
        # Chrome runs this source in every new document before any of the
        # page's own scripts, which is how tests stub APIs (e.g. window.print)
        # or make localStorage throw, as if the browser blocked site data.
        r = await self.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})
        return r["result"]["identifier"]

    async def remove_init_script(self, identifier):
        """Stop an init script from running on later page loads."""
        await self.call(
            "Page.removeScriptToEvaluateOnNewDocument", {"identifier": identifier}
        )

    async def set_viewport(self, width, height, mobile=False):
        """Override the page size (CSS px); mobile=True also emulates a phone."""
        await self.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile},
        )

    async def clear_viewport(self):
        """Undo set_viewport() and return to the window size."""
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
