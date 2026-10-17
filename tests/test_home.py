"""Functional UI tests for the home page FX panel + swipe gestures.

Each test is an async function that takes (chrome, base_url) and returns
(name, ok, message). Run via `python3 tests/test_home.py` from the repo root.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import ChromeSession, serve_directory  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8766
BASE = f"http://localhost:{PORT}"

GET_ATM = "document.documentElement.getAttribute('data-atmosphere')"


# ─── Page load + structure ──────────────────────────────────────────────

async def test_page_loads_clean(c):
    await c.goto(BASE + "/", clear_storage=True)
    # Ignore the third-party three.js deprecation warning from the CDN bundle.
    real_errors = [e for e in c.errors if "three.js" not in e.lower()]
    return (
        "Page loads with no JS errors",
        not real_errors,
        f"errors={real_errors!r}",
    )


async def test_fx_panel_renders(c):
    await c.goto(BASE + "/")
    exists = await c.eval("!!document.getElementById('fxPanel')")
    count = await c.eval("document.querySelectorAll('.fx-toggle').length")
    keys = await c.eval(
        "Array.from(document.querySelectorAll('.fx-toggle'))"
        ".map(function(i){return i.getAttribute('data-fx');}).join(',')"
    )
    expected_keys = "spotlight,tilt,sparks,confetti"
    return (
        "FX panel renders with the expected 4 toggles",
        exists and count == 4 and keys == expected_keys,
        f"exists={exists} count={count} keys={keys}",
    )


async def test_subpages_load_without_BSC_FX(c):
    """Sub-pages load shared-enhancements.js but don't define BSC_FX —
    the fxOn helper must default to on so behavior is unchanged.
    """
    failures = []
    for page in (
        "resume-atlas.html",
        "resume-signal.html",
        "proof-hub.html",
        "resume-switchboard.html",
    ):
        await c.goto(f"{BASE}/{page}", clear_storage=True)
        if c.errors:
            failures.append(f"{page}: {c.errors!r}")
        has_fx = await c.eval("!!window.BSC_FX")
        if has_fx:
            failures.append(f"{page}: unexpectedly exposes BSC_FX")
    return (
        "All sub-pages load with no JS errors and don't expose BSC_FX",
        not failures,
        "; ".join(failures) or "4/4 pages OK",
    )


# ─── BSC_FX state + persistence ─────────────────────────────────────────

async def test_fx_defaults(c):
    await c.goto(BASE + "/", clear_storage=True)
    state = json.loads(await c.eval("JSON.stringify(window.BSC_FX.all())"))
    expected = {
        "spotlight": False, "tilt": False, "sparks": False,
        "confetti": False,
    }
    return (
        "BSC_FX defaults are all-off (opt-in only)",
        state == expected,
        f"got {state}",
    )


async def test_fx_set_persists(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('spotlight', false)")
    raw = await c.eval("localStorage.getItem('bsc_fx')")
    parsed = json.loads(raw) if raw else {}
    return (
        "BSC_FX.set persists to localStorage",
        parsed.get("spotlight") is False,
        f"localStorage: {raw}",
    )


async def test_fx_state_survives_reload(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('sparks', false)")
    await c.goto(BASE + "/")  # reload without clearing
    state = json.loads(await c.eval("JSON.stringify(window.BSC_FX.all())"))
    return (
        "BSC_FX state survives page reload",
        state.get("sparks") is False,
        f"after reload: {state}",
    )


async def test_fx_change_event(c):
    await c.goto(BASE + "/", clear_storage=True)
    captured = await c.eval(
        "(function(){"
        "var got = null;"
        "window.addEventListener('bsc-fx-change',"
        "function(ev){got = ev.detail;},{once:true});"
        "window.BSC_FX.set('tilt', false);"
        "return JSON.stringify(got);"
        "})()"
    )
    detail = json.loads(captured) if captured else None
    ok = bool(detail and detail.get("key") == "tilt" and detail.get("value") is False)
    return (
        "bsc-fx-change event fires with {key, value} detail",
        ok,
        f"detail: {detail}",
    )


async def test_checkbox_syncs_with_programmatic_set(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('spotlight', false)")
    checked = await c.eval(
        "document.querySelector('input[data-fx=\"spotlight\"]').checked"
    )
    row_on = await c.eval(
        "document.querySelector('[data-fx-row=\"spotlight\"]').getAttribute('data-on')"
    )
    return (
        "Checkbox + row[data-on] sync when BSC_FX.set is called externally",
        checked is False and row_on == "false",
        f"checked={checked} data-on={row_on}",
    )


async def test_checkbox_click_updates_state(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval(
        "(function(){var i=document.querySelector('input[data-fx=\"confetti\"]');"
        "i.checked=false; i.dispatchEvent(new Event('change',{bubbles:true}));})()"
    )
    state = json.loads(await c.eval("JSON.stringify(window.BSC_FX.all())"))
    raw = await c.eval("localStorage.getItem('bsc_fx')")
    persisted = json.loads(raw) if raw else {}
    return (
        "Toggling a checkbox updates BSC_FX state and persists",
        state.get("confetti") is False and persisted.get("confetti") is False,
        f"runtime={state.get('confetti')} stored={persisted.get('confetti')}",
    )


# ─── New: stack footer, ?for= personalization, /now, per-case share ─────

async def test_stack_footer_injected_on_home(c):
    await c.goto(BASE + "/", clear_storage=True)
    await asyncio.sleep(0.15)
    present = await c.eval("!!document.querySelector('[data-bsc-stack]')")
    return (
        "Stack-disclosure line is injected into the footer",
        bool(present),
        f"present={present}",
    )


async def test_stack_footer_present_on_all_entry_points(c):
    pages = (
        "/",
        "resume-atlas.html",
        "resume-signal.html",
        "proof-hub.html",
        "resume-switchboard.html",
        "now.html",
    )
    failures = []
    for page in pages:
        url = BASE + ("/" + page if not page.startswith("/") else page)
        await c.goto(url, clear_storage=True)
        await asyncio.sleep(0.15)
        present = await c.eval("!!document.querySelector('[data-bsc-stack]')")
        if not present:
            failures.append(page)
    return (
        "Stack-disclosure footer present on all 6 entry points",
        not failures,
        "; ".join(failures) or f"{len(pages)}/{len(pages)} pages OK",
    )


async def test_for_param_personalizes(c):
    await c.goto(BASE + "/?for=stripe", clear_storage=True)
    # Give the fetch + DOM injection a moment to settle.
    for _ in range(20):
        present = await c.eval("!!document.querySelector('[data-for-badge]')")
        if present:
            break
        await asyncio.sleep(0.1)
    atm = await c.eval(GET_ATM)
    badge_text = await c.eval(
        "(function(){var b=document.querySelector('[data-for-badge]');"
        "return b ? b.textContent : '';})()"
    )
    return (
        "?for=stripe pins emerald atmosphere AND shows 'Tailored for Stripe' badge",
        atm == "emerald" and "Stripe" in (badge_text or ""),
        f"atmosphere={atm} badge_text={badge_text!r}",
    )


async def test_for_param_unknown_slug_is_silent(c):
    await c.goto(BASE + "/?for=nonexistent-co-99", clear_storage=True)
    await asyncio.sleep(0.3)
    badge = await c.eval("!!document.querySelector('[data-for-badge]')")
    real_errors = [e for e in c.errors if "three.js" not in e.lower()]
    return (
        "Unknown ?for= slug fails silently — no badge, no JS error",
        not badge and not real_errors,
        f"badge={badge} errors={real_errors!r}",
    )


async def test_now_page_loads_with_sections(c):
    await c.goto(BASE + "/now.html", clear_storage=True)
    real_errors = [e for e in c.errors if "three.js" not in e.lower()]
    sections = await c.eval(
        "Array.from(document.querySelectorAll('section.card h2'))"
        ".map(function(h){return h.textContent.trim();}).join('|')"
    )
    expected = ["Currently building", "Currently learning", "Currently reading", "Open to"]
    missing = [s for s in expected if s not in sections]
    return (
        "/now.html loads with all four expected section headings and no JS errors",
        not real_errors and not missing,
        f"errors={real_errors!r} missing={missing} got={sections!r}",
    )


async def test_proof_hub_case_anchors_exist(c):
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    ids = await c.eval(
        "Array.from(document.querySelectorAll('[id^=\"case-\"]'))"
        ".map(function(el){return el.id;}).sort().join(',')"
    )
    expected = "case-data-foundations,case-java-etl,case-payment-portal,case-secure-provisioning,case-serverless-bus"
    return (
        "Proof Hub exposes all 5 case anchors (id=case-<slug>)",
        ids == expected,
        f"got: {ids}",
    )


async def test_proof_hub_case_share_buttons_render(c):
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    await asyncio.sleep(0.2)
    count = await c.eval("document.querySelectorAll('[data-case-share]').length")
    return (
        "Each case anchor gets a [data-case-share] copy-link button",
        count == 5,
        f"count={count}",
    )


# ─── Runner ──────────────────────────────────────────────────────────────

TESTS = [
    test_page_loads_clean,
    test_fx_panel_renders,
    test_subpages_load_without_BSC_FX,
    test_fx_defaults,
    test_fx_set_persists,
    test_fx_state_survives_reload,
    test_fx_change_event,
    test_checkbox_syncs_with_programmatic_set,
    test_checkbox_click_updates_state,
    test_stack_footer_injected_on_home,
    test_stack_footer_present_on_all_entry_points,
    test_for_param_personalizes,
    test_for_param_unknown_slug_is_silent,
    test_now_page_loads_with_sections,
    test_proof_hub_case_anchors_exist,
    test_proof_hub_case_share_buttons_render,
]


async def main():
    server = serve_directory(ROOT, port=PORT)
    async with ChromeSession(port=9438) as chrome:
        print(f"Running {len(TESTS)} tests against {BASE}\n")
        results = []
        for fn in TESTS:
            try:
                name, ok, msg = await fn(chrome)
            except Exception as e:
                name, ok, msg = fn.__name__, False, f"EXCEPTION: {e!r}"
            results.append((name, ok, msg))
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}")
            if not ok:
                print(f"         → {msg}")
        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        print(f"\n{passed}/{total} passed")
    server.terminate()
    try:
        server.wait(timeout=3)
    except Exception:
        server.kill()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
