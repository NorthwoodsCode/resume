"""Functional UI tests for the resume site.

Each test is an async function that takes a ChromeSession and returns
(name, ok, message). Run via `python3 tests/test_home.py` from the repo root.

The script serves the repo over a local http.server, drives headless Chrome
through the small CDP harness in harness.py, and prints PASS/FAIL per test. All
tests share one browser tab, so most start with goto(..., clear_storage=True)
to begin from a clean localStorage. Tests are listed in TESTS near the bottom.
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

# JS snippets reused across tests. GET_ATM / GET_THEME read the attributes the
# site's scripts set on <html> for the colour atmosphere and light/dark theme.
GET_ATM = "document.documentElement.getAttribute('data-atmosphere')"
GET_THEME = "document.documentElement.getAttribute('data-theme')"
# Every page of the site, in the order the "6/6 pages" messages count them.
PAGES = (
    "/",
    "/resume-atlas.html",
    "/resume-signal.html",
    "/proof-hub.html",
    "/resume-switchboard.html",
    "/now.html",
)
# Init script that makes localStorage/sessionStorage throw a SecurityError on
# access, the way a browser with blocked site data behaves. The page's own code
# must cope; see test_pages_survive_blocked_storage.
BLOCK_STORAGE = (
    "(function(){var t={get:function(){throw new DOMException('Storage disabled',"
    "'SecurityError');},configurable:true};try{Object.defineProperty(window,"
    "'localStorage',t);Object.defineProperty(window,'sessionStorage',t);}catch(e){}})();"
)
# Collects only the text a visitor could see: skips script/style/noscript and
# anything hidden with display:none or visibility:hidden. Used to check what is
# actually rendered rather than what is merely in the HTML source.
VISIBLE_TEXT = (
    "(function(){var out='';(function walk(n){if(n.nodeType===3){out+=n.textContent+' ';"
    "return;}if(n.nodeType!==1)return;if(['SCRIPT','STYLE','NOSCRIPT'].indexOf(n.tagName)>=0)"
    "return;var cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')return;"
    "n.childNodes.forEach(walk);})(document.body);return out.replace(/\\s+/g,' ');})()"
)


def _real_errors(c):
    """Console errors, ignoring any that mention three.js (the optional 3D
    background library), so its failures do not fail unrelated tests."""
    return [e for e in c.errors if "three.js" not in e.lower()]


# ─── Page load + structure ──────────────────────────────────────────────
# Protects the basics: each page loads without JS errors, and the FX panel and
# sub-pages get exactly the features they should (and none they should not).

async def test_page_loads_clean(c):
    await c.goto(BASE + "/", clear_storage=True)
    real_errors = _real_errors(c)
    return ("Home loads with no JS errors", not real_errors, f"errors={real_errors!r}")


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
    """Sub-pages load shared-enhancements.js but have no FX panel, so no effect
    (glow, tilt, sparks) may be set up there."""
    failures = []
    for page in PAGES[1:5]:
        await c.goto(BASE + page, clear_storage=True)
        if c.errors:
            failures.append(f"{page}: {c.errors!r}")
        has_fx = await c.eval("!!window.BSC_FX")
        glow = await c.eval("!!document.getElementById('cursor-glow')")
        if has_fx:
            failures.append(f"{page}: unexpectedly exposes BSC_FX")
        if glow:
            failures.append(f"{page}: cursor glow injected without the FX panel")
    return (
        "Sub-pages load with no JS errors, no BSC_FX and no injected effects",
        not failures,
        "; ".join(failures) or "4/4 pages OK",
    )


# ─── BSC_FX state + persistence ─────────────────────────────────────────
# BSC_FX is the effects store behind the FX panel. These tests cover its
# defaults, localStorage persistence, change event and checkbox syncing.

async def test_fx_defaults(c):
    await c.goto(BASE + "/", clear_storage=True)
    state = json.loads(await c.eval("JSON.stringify(window.BSC_FX.all())"))
    expected = {"spotlight": False, "tilt": False, "sparks": False, "confetti": True}
    return ("BSC_FX defaults: confetti on, every other effect off", state == expected, f"got {state}")


async def test_fx_set_persists(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('spotlight', true)")
    raw = await c.eval("localStorage.getItem('bsc_fx')")
    parsed = json.loads(raw) if raw else {}
    return ("BSC_FX.set persists to localStorage", parsed.get("spotlight") is True, f"localStorage: {raw}")


async def test_fx_state_survives_reload(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('sparks', true)")
    await c.goto(BASE + "/")  # reload without clearing
    state = json.loads(await c.eval("JSON.stringify(window.BSC_FX.all())"))
    return ("BSC_FX state survives page reload", state.get("sparks") is True, f"after reload: {state}")


async def test_fx_change_event(c):
    await c.goto(BASE + "/", clear_storage=True)
    captured = await c.eval(
        "(function(){var got=null;window.addEventListener('bsc-fx-change',"
        "function(ev){got=ev.detail;},{once:true});window.BSC_FX.set('tilt',true);"
        "return JSON.stringify(got);})()"
    )
    detail = json.loads(captured) if captured else None
    ok = bool(detail and detail.get("key") == "tilt" and detail.get("value") is True)
    return ("bsc-fx-change event fires with {key, value} detail", ok, f"detail: {detail}")


async def test_checkbox_syncs_with_programmatic_set(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.eval("window.BSC_FX.set('spotlight', true)")
    checked = await c.eval("document.querySelector('input[data-fx=\"spotlight\"]').checked")
    row_on = await c.eval("document.querySelector('[data-fx-row=\"spotlight\"]').getAttribute('data-on')")
    return (
        "Checkbox + row[data-on] sync when BSC_FX.set is called externally",
        checked is True and row_on == "true",
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


async def _confetti_fires(c, url, window_s=2.0):
    """Navigate and report whether the confetti canvas switches on within window_s."""
    # Short initial wait, then poll every 100 ms: the check should not depend
    # on exactly when the burst starts, and a long sleep could miss it.
    await c.goto(url, wait=0.25)
    for _ in range(int(window_s / 0.1)):
        if await c.eval("(function(){var e=document.getElementById('confetti');return !!(e&&e.classList.contains('is-on'));})()"):
            return True
        await asyncio.sleep(0.1)
    return False


async def test_confetti_pops_on_home_load(c):
    await c.goto(BASE + "/", clear_storage=True)
    fired = await _confetti_fires(c, BASE + "/")
    plain = await _confetti_fires(c, BASE + "/?plain=1", window_s=1.5)
    await c.eval("window.BSC_FX && window.BSC_FX.set('confetti', false)")
    off = await _confetti_fires(c, BASE + "/", window_s=1.5)
    await c.eval("window.BSC_FX && window.BSC_FX.set('confetti', true)")
    # Emulate the OS "reduce motion" setting; the site must skip the animation.
    await c.emulate_media("", [{"name": "prefers-reduced-motion", "value": "reduce"}])
    reduced = await _confetti_fires(c, BASE + "/", window_s=1.5)
    await c.emulate_media("", [])
    return (
        "Confetti pops on Home load, but not in plain mode, reduced motion, or with the toggle off",
        fired and not plain and not off and not reduced,
        f"default={fired} plain={plain} toggle_off={off} reduced_motion={reduced}",
    )


# ─── Shared module: footer line, palette, dock ──────────────────────────
# Features injected by shared-enhancements.js: the stack footer (Home only),
# the Ctrl+K command palette and the navigation dock on sub-pages.

async def test_stack_footer_home_only(c):
    failures = []
    for page in PAGES:
        await c.goto(BASE + page, clear_storage=True)
        await asyncio.sleep(0.15)
        present = await c.eval("!!document.querySelector('[data-bsc-stack]')")
        want = page == "/"
        if bool(present) != want:
            failures.append(f"{page}: present={present}")
    return ("Stack-disclosure line appears on Home only", not failures, "; ".join(failures) or "6/6 pages OK")


async def test_shared_palette_and_dock_on_subpages(c):
    failures = []
    for page in PAGES[1:]:
        await c.goto(BASE + page, clear_storage=True)
        pal = await c.eval("!!document.getElementById('cmd-pal')")
        dock = await c.eval("document.querySelectorAll('.bsc-dock').length")
        current = await c.eval(
            "(function(){var a=document.querySelector('.bsc-dock-link[aria-current=\"page\"]');"
            "return a?a.getAttribute('data-page'):null;})()"
        )
        opened = await c.eval(
            "(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,"
            "bubbles:true,cancelable:true}));var p=document.getElementById('cmd-pal');return p&&!p.hidden;})()"
        )
        if not pal or dock != 1 or current != page.lstrip("/") or not opened:
            failures.append(f"{page}: palette={pal} docks={dock} current={current} ctrlK={opened}")
    return (
        "Every sub-page gets the shared palette (Ctrl+K) and one dock marking the current page",
        not failures,
        "; ".join(failures) or "5/5 pages OK",
    )


# ─── ?for= personalization, /now ────────────────────────────────────────
# Personalised links (?for=<company>) and the /now page: correct atmosphere and
# badge for known slugs, silent no-op for unknown ones.

async def test_for_param_personalizes(c):
    await c.goto(BASE + "/?for=stripe", clear_storage=True)
    for _ in range(20):
        present = await c.eval("!!document.querySelector('[data-for-badge]')")
        if present:
            break
        await asyncio.sleep(0.1)
    atm = await c.eval(GET_ATM)
    badge_text = await c.eval(
        "(function(){var b=document.querySelector('[data-for-badge]');return b?b.textContent:'';})()"
    )
    overlap = await c.eval(
        "(function(){var b=document.querySelector('[data-for-badge]');var t=document.querySelector('.top-actions');"
        "if(!b||!t)return false;var r=b.getBoundingClientRect(),s=t.getBoundingClientRect();"
        "return r.left<s.right&&r.right>s.left&&r.top<s.bottom&&r.bottom>s.top;})()"
    )
    return (
        "?for=stripe pins emerald atmosphere, shows the badge, and the badge does not cover the top controls",
        atm == "emerald" and "Stripe" in (badge_text or "") and not overlap,
        f"atmosphere={atm} badge_text={badge_text!r} overlap={overlap}",
    )


async def test_for_param_unknown_slug_is_silent(c):
    await c.goto(BASE + "/?for=nonexistent-co-99", clear_storage=True)
    await asyncio.sleep(0.3)
    badge = await c.eval("!!document.querySelector('[data-for-badge]')")
    real_errors = _real_errors(c)
    return ("Unknown ?for= slug fails silently", not badge and not real_errors, f"badge={badge} errors={real_errors!r}")


async def test_now_page_loads_with_sections(c):
    await c.goto(BASE + "/now.html", clear_storage=True)
    real_errors = _real_errors(c)
    sections = await c.eval(
        "Array.from(document.querySelectorAll('section.card h2')).map(function(h){return h.textContent.trim();}).join('|')"
    )
    expected = ["Currently building", "Currently learning", "Currently reading", "Open to"]
    missing = [s for s in expected if s not in sections]
    return (
        "/now.html loads with all four section headings and no JS errors",
        not real_errors and not missing,
        f"errors={real_errors!r} missing={missing}",
    )


# ─── Proof Hub ──────────────────────────────────────────────────────────
# Proof Hub case studies: anchors, copy-link buttons, deep links and keyboard
# shortcuts that must not fire while typing in the search box.

async def test_proof_hub_case_anchors_exist(c):
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    ids = await c.eval(
        "Array.from(document.querySelectorAll('[id^=\"case-\"]')).map(function(el){return el.id;}).sort().join(',')"
    )
    expected = "case-data-foundations,case-java-etl,case-payment-portal,case-secure-provisioning,case-serverless-bus"
    return ("Proof Hub exposes all 5 case anchors", ids == expected, f"got: {ids}")


async def test_proof_hub_case_share_buttons_render(c):
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    await asyncio.sleep(0.2)
    count = await c.eval("document.querySelectorAll('[data-case-share]').length")
    return ("Each case anchor gets a copy-link button", count == 5, f"count={count}")


async def test_proof_hub_deep_link_opens_case(c):
    await c.goto(BASE + "/proof-hub.html#case-java-etl", clear_storage=True)
    await asyncio.sleep(0.3)
    state = json.loads(await c.eval(
        "JSON.stringify((function(){var e=document.getElementById('case-java-etl');"
        "return {open:!!(e&&e.open),top:e?Math.round(e.getBoundingClientRect().top):null};})())"
    ))
    return (
        "#case-<slug> deep link opens the case card and lands on it",
        state.get("open") is True and state.get("top") is not None and -50 <= state["top"] <= 400,
        f"state={state}",
    )


async def test_proof_hub_typing_does_not_trigger_shortcuts(c):
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    before = await c.eval(GET_THEME)
    await c.eval(
        "(function(){var s=document.getElementById('search');s.focus();"
        "'tpcs'.split('').forEach(function(k){s.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true}));});"
        "document.dispatchEvent(new KeyboardEvent('keydown',{key:'p',ctrlKey:true,bubbles:true,cancelable:true}));})()"
    )
    after = await c.eval(GET_THEME)
    public_btn_visible = await c.eval(
        "(function(){var b=document.getElementById('publicBtn');return !!(b&&b.offsetParent);})()"
    )
    return (
        "Typing in Proof Hub search and pressing Ctrl+P change nothing; Public Mode toggle is hidden",
        before == after and not public_btn_visible,
        f"theme {before}->{after} publicBtnVisible={public_btn_visible}",
    )


async def test_no_internal_terms_rendered(c):
    banned = ["JEDI", "Exceeds Expectations", "Meets Expectations", "Data Engineer II",
              "Wausau", "switchboard-next", "Switchboard+", "manager review", "self-evaluation",
              "100-device", "Post Inspector", "master inventory"]
    failures = []
    for page in ("/proof-hub.html", "/resume-switchboard.html", "/resume-signal.html", "/resume-atlas.html"):
        await c.goto(BASE + page, clear_storage=True)
        text = await c.eval(VISIBLE_TEXT)
        hits = [b for b in banned if b.lower() in (text or "").lower()]
        if hits:
            failures.append(f"{page}: {hits}")
    return ("No internal team names or review language is rendered", not failures, "; ".join(failures) or "clean")


# ─── Signal ─────────────────────────────────────────────────────────────
# Signal's filter UI: ?focus= parsing and aliases, history (popstate) handling
# and the empty state.

async def test_signal_focus_filters_and_aliases(c):
    await c.goto(BASE + "/resume-signal.html?focus=cloud,api", clear_storage=True)
    s1 = json.loads(await c.eval(
        "JSON.stringify({checked:Array.from(document.querySelectorAll('.chip input[value]')).filter(function(i){return i.checked}).map(function(i){return i.value}),"
        "match:document.querySelectorAll('.item[data-match=\"true\"]').length,"
        "nomatch:document.querySelectorAll('.item[data-match=\"false\"]').length})"
    ))
    # No storage clear here: that reloads the page, and the first load already
    # rewrote the URL to the canonical keys (dropping "bogus"), which is the point.
    await c.goto(BASE + "/resume-signal.html?focus=leadership,enablement,bogus")
    s2 = json.loads(await c.eval(
        "JSON.stringify({checked:Array.from(document.querySelectorAll('.chip input[value]')).filter(function(i){return i.checked}).map(function(i){return i.value}),"
        "hint:document.getElementById('matchHint').textContent,url:location.search})"
    ))
    ok = (
        sorted(s1["checked"]) == ["api", "cloud"] and s1["match"] > 0 and s1["nomatch"] > 0
        and sorted(s2["checked"]) == ["enable", "lead"] and "bogus" in s2["hint"] and "focus=lead" in s2["url"]
    )
    return ("Signal ?focus= filters, maps README aliases, and reports unknown keys", ok, f"s1={s1} s2={s2}")


async def test_signal_back_button_restores_filters(c):
    await c.goto(BASE + "/resume-signal.html", clear_storage=True)
    await c.eval("document.querySelector('[data-preset-focus=\"lead,enable,opex\"]').click()")
    after_preset = await c.eval("location.search")
    # history.back() fires popstate asynchronously, so give the handler time to run.
    await c.eval("history.back()")
    await asyncio.sleep(0.4)
    checked = await c.eval(
        "Array.from(document.querySelectorAll('.chip input[value]')).filter(function(i){return i.checked}).length"
    )
    return (
        "Browser Back restores Signal's filters (popstate)",
        "focus=" in after_preset and checked == 0,
        f"after_preset={after_preset} checked_after_back={checked}",
    )


async def test_signal_empty_state(c):
    await c.goto(BASE + "/resume-signal.html?q=zzzqqq&only=1", clear_storage=True)
    shown = await c.eval("(function(){var e=document.getElementById('emptyState');return !!(e&&!e.hidden);})()")
    return ("Signal shows an empty state when nothing matches", bool(shown), f"shown={shown}")


# ─── Print ──────────────────────────────────────────────────────────────
# Print styles: identity details stay visible on a white page and animated
# cards do not print as invisible. Print is emulated, not opened.

async def test_print_keeps_identity(c):
    checks = {
        "/resume-atlas.html": "header",
        "/resume-signal.html": ".hero",
        "/proof-hub.html": ".print-identity",
    }
    failures = []
    for page, sel in checks.items():
        await c.goto(BASE + page, clear_storage=True)
        # Force the dark theme first so the test proves print rules override it.
        await c.eval("document.documentElement.setAttribute('data-theme','dark')")
        await c.emulate_media("print")
        await asyncio.sleep(0.3)
        res = json.loads(await c.eval(
            "JSON.stringify((function(){var el=document.querySelector(%s);var cs=el&&getComputedStyle(el);"
            "var t=%s;return {display:cs?cs.display:'missing',bodyBg:getComputedStyle(document.body).backgroundColor,"
            "name:/Brandon S\\. Clark/.test(t),email:/bsc_pro@protonmail\\.com/.test(t)};})())"
            % (json.dumps(sel), VISIBLE_TEXT)
        ))
        await c.emulate_media("")
        if res["display"] in ("none", "missing") or not res["name"] or not res["email"] or res["bodyBg"] != "rgb(255, 255, 255)":
            failures.append(f"{page}: {res}")
    return ("Print keeps name and email visible on a white page (Atlas, Signal, Proof Hub)", not failures, "; ".join(failures) or "3/3 OK")


async def test_home_print_shows_cards(c):
    await c.goto(BASE + "/", clear_storage=True)
    await c.emulate_media("print")
    await asyncio.sleep(0.3)
    hidden = await c.eval(
        "Array.from(document.querySelectorAll('.section-shell > .card, .formats-grid > .card')).filter(function(e){return getComputedStyle(e).opacity==='0'}).length"
    )
    await c.emulate_media("")
    return ("Home prints its mode cards (no opacity-0 cards in print)", hidden == 0, f"hidden={hidden}")


async def test_atlas_print_param_triggers_print(c):
    # Replace window.print before the page runs so no dialog opens and calls are counted.
    ident = await c.add_init_script("window.__printed=0;window.print=function(){window.__printed++;};")
    await c.goto(BASE + "/resume-atlas.html?print=1", clear_storage=True)
    await asyncio.sleep(0.6)
    printed = await c.eval("window.__printed")
    await c.remove_init_script(ident)
    return ("resume-atlas.html?print=1 opens the print dialog once", printed == 1, f"printed={printed}")


# ─── Robustness ─────────────────────────────────────────────────────────
# Resilience checks: no failed requests, working pages without storage, valid
# links, lazy-loaded 3D libraries and no sideways scroll on phones.

async def test_no_failed_resources(c):
    failures = []
    for page in PAGES:
        await c.goto(BASE + page, clear_storage=True)
        # CDN failures are ignored so an offline or flaky network cannot fail the run.
        bad = [f for f in c.failed_requests if "cdn.jsdelivr.net" not in f]
        if bad:
            failures.append(f"{page}: {bad}")
    return ("No page requests a resource that 404s or fails", not failures, "; ".join(failures) or "6/6 pages OK")


async def test_pages_survive_blocked_storage(c):
    ident = await c.add_init_script(BLOCK_STORAGE)
    failures = []
    probes = {
        "/resume-atlas.html": "(function(){var b=document.getElementById('themeBtn');var t0=document.documentElement.dataset.theme;b.click();return document.documentElement.dataset.theme!==t0;})()",
        "/resume-signal.html": "(function(){var m=function(){return document.querySelectorAll('.item[data-match=\"true\"]').length};var b=m();document.querySelector('.chip input[value=\"cloud\"]').click();return m()!==b;})()",
        "/proof-hub.html": "(function(){var s=document.getElementById('search');var n=function(){return Array.from(document.querySelectorAll('li.bullet')).filter(function(e){return e.offsetParent!==null}).length};var b=n();s.value='Lambda';s.dispatchEvent(new Event('input',{bubbles:true}));return n()!==b;})()",
        "/resume-switchboard.html": "(function(){var sec=document.querySelector('section[aria-labelledby=\"builder-heading\"]');var cb=sec.querySelector('input[type=checkbox]');var p=document.getElementById('preview');var b=p.textContent;cb.click();return p.textContent!==b;})()",
        "/": "(function(){return !!window.BSC_FX;})()",
    }
    for page, probe in probes.items():
        await c.goto(BASE + page)
        if c.errors:
            failures.append(f"{page}: errors={c.errors!r}")
            continue
        works = await c.eval(probe)
        if not works:
            failures.append(f"{page}: controls dead")
    await c.remove_init_script(ident)
    return ("Pages keep working when localStorage throws", not failures, "; ".join(failures) or "5/5 pages OK")


async def test_switchboard_links_resolve(c):
    await c.goto(BASE + "/resume-switchboard.html", clear_storage=True)
    hrefs = json.loads(await c.eval(
        "JSON.stringify(Array.from(document.querySelectorAll('a[href]:not(.bsc-dock-link)')).map(function(a){return a.getAttribute('href')}))"
    ))
    missing, selfs = [], 0
    for h in hrefs:
        if h.startswith(("http", "mailto:", "#")):
            continue
        path = h.split("?")[0].split("#")[0]
        if path == "resume-switchboard.html":
            selfs += 1
        if path and not os.path.exists(os.path.join(ROOT, path)):
            missing.append(h)
    return ("Switchboard links all resolve and the page does not link to itself", not missing and selfs == 0, f"missing={missing} self_links={selfs}")


async def test_plain_and_reduced_motion_skip_3d_stack(c):
    # c.requests is reset on each goto and records every URL fetched, so an
    # empty CDN list proves the bundles were never even requested.
    await c.goto(BASE + "/?plain=1", clear_storage=True)
    plain_cdn = [u for u in c.requests if "cdn.jsdelivr.net" in u]
    await c.emulate_media("", [{"name": "prefers-reduced-motion", "value": "reduce"}])
    await c.goto(BASE + "/", clear_storage=True)
    rm_cdn = [u for u in c.requests if "cdn.jsdelivr.net" in u]
    await c.emulate_media("", [])
    return (
        "?plain=1 and prefers-reduced-motion never download the Three/Vanta bundles",
        not plain_cdn and not rm_cdn,
        f"plain={plain_cdn} reduced={rm_cdn}",
    )


async def test_home_default_requests_3d_stack_lazily(c):
    await c.goto(BASE + "/", clear_storage=True)
    await asyncio.sleep(0.5)
    cdn = [u.split("/")[-1] for u in c.requests if "cdn.jsdelivr.net" in u]
    return (
        "Default Home requests three.js plus only the fog bundle",
        "three.min.js" in cdn and "vanta.fog.min.js" in cdn and not any(x in cdn for x in ("vanta.clouds.min.js", "vanta.waves.min.js", "vanta.ripple.min.js")),
        f"cdn={cdn}",
    )


async def test_mobile_no_horizontal_overflow(c):
    # 375px is a common phone width; scrollWidth > clientWidth means sideways scroll.
    await c.set_viewport(375, 812, mobile=True)
    failures = []
    for page in PAGES:
        await c.goto(BASE + page, clear_storage=True)
        over = await c.eval("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if over and over > 1:
            failures.append(f"{page}: overflow {over}px")
    await c.clear_viewport()
    return ("No page scrolls sideways at 375px", not failures, "; ".join(failures) or "6/6 pages OK")


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
    test_confetti_pops_on_home_load,
    test_stack_footer_home_only,
    test_shared_palette_and_dock_on_subpages,
    test_for_param_personalizes,
    test_for_param_unknown_slug_is_silent,
    test_now_page_loads_with_sections,
    test_proof_hub_case_anchors_exist,
    test_proof_hub_case_share_buttons_render,
    test_proof_hub_deep_link_opens_case,
    test_proof_hub_typing_does_not_trigger_shortcuts,
    test_no_internal_terms_rendered,
    test_signal_focus_filters_and_aliases,
    test_signal_back_button_restores_filters,
    test_signal_empty_state,
    test_print_keeps_identity,
    test_home_print_shows_cards,
    test_atlas_print_param_triggers_print,
    test_no_failed_resources,
    test_pages_survive_blocked_storage,
    test_switchboard_links_resolve,
    test_plain_and_reduced_motion_skip_3d_stack,
    test_home_default_requests_3d_stack_lazily,
    test_mobile_no_horizontal_overflow,
]


async def main():
    """Serve the repo, run every test in TESTS and exit non-zero on any failure."""
    server = serve_directory(ROOT, port=PORT)
    # Separate ports for the web server (8766) and DevTools (9438), so neither
    # collides with a developer's own server or browser.
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
