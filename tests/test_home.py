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


# ─── Phone emulation ────────────────────────────────────────────────────
# These tests emulate a phone: a narrow viewport, touch events, a coarse
# pointer and no hover, which is what the site's (pointer:coarse) and
# (hover:none) rules key on. phone_off() returns the tab to desktop defaults so
# later tests see the normal layout again.

PHONE_FEATURES = [{"name": "pointer", "value": "coarse"}, {"name": "hover", "value": "none"}]


async def phone_on(c, width=375, height=667):
    await c.set_viewport(width, height, mobile=True)
    await c.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
    await c.emulate_media("", PHONE_FEATURES)


async def phone_off(c):
    await c.emulate_media("", [])
    await c.call("Emulation.setTouchEmulationEnabled", {"enabled": False})
    await c.clear_viewport()


# Visible interactive controls that are too short to tap comfortably. Inline
# links inside running text are exempt (WCAG 2.5.8 exempts them too); the
# thresholds are per kind: buttons/inputs 36px, disclosure summaries 32px,
# standalone links 28px.
SHORT_TARGETS = (
    "(function(){var vis=function(el){var r=el.getBoundingClientRect();var cs=getComputedStyle(el);"
    "return r.width>0&&r.height>0&&cs.visibility!=='hidden'&&cs.display!=='none';};"
    "var out=[];var sel='button,summary,input:not([type=checkbox]):not([type=radio]),select,textarea,a[href],[role=button]';"
    "document.querySelectorAll(sel).forEach(function(el){if(!vis(el)||el.closest('#cmd-pal'))return;"
    "var r=el.getBoundingClientRect();var cs=getComputedStyle(el);var min=36;"
    "if(el.tagName==='SUMMARY')min=32;else if(el.tagName==='A'){if(cs.display==='inline'&&el.closest('p,li,dd,figcaption,td,.stamp,.note,small'))return;min=28;}"
    "if(r.height<min-0.5)out.push(el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+'.'+String(el.className||'').trim().split(/\\s+/)[0]+' \"'+(el.innerText||el.value||el.getAttribute('aria-label')||'').trim().slice(0,22)+'\" '+Math.round(r.width)+'x'+Math.round(r.height));});"
    "return JSON.stringify(out.slice(0,8).concat(out.length>8?['+'+(out.length-8)+' more']:[]));})()"
)

# Smallest computed font-size of any visible text node outside the palette.
MIN_FONT = (
    "(function(){var min=99;var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);var n;var ex='';"
    "while((n=w.nextNode())){if(!n.textContent.trim())continue;var el=n.parentElement;if(!el||el.closest('#cmd-pal,script,style,noscript'))continue;"
    "var r=el.getBoundingClientRect();var cs=getComputedStyle(el);if(!r.width||!r.height||cs.visibility==='hidden'||cs.display==='none')continue;"
    "var fs=parseFloat(cs.fontSize);if(fs<min){min=fs;ex=el.tagName.toLowerCase()+'.'+String(el.className||'').trim().split(/\\s+/)[0]+' \"'+n.textContent.trim().slice(0,20)+'\"';}}"
    "return JSON.stringify({min:Math.round(min*10)/10,ex:ex});})()"
)

# Visible text inputs below 16px: iOS Safari zooms the page when one is focused.
SMALL_INPUTS = (
    "(function(){var out=[];document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),textarea,select').forEach(function(el){"
    "var r=el.getBoundingClientRect();var cs=getComputedStyle(el);if(!r.width||!r.height||cs.visibility==='hidden'||el.closest('#cmd-pal'))return;"
    "var fs=parseFloat(cs.fontSize);if(fs<16)out.push(el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+' '+fs.toFixed(1)+'px');});return JSON.stringify(out);})()"
)


async def test_phone_no_horizontal_overflow_320(c):
    # 320px is the narrowest common phone (older iPhone SE, small Androids).
    await phone_on(c, 320, 568)
    failures = []
    for page in PAGES:
        await c.goto(BASE + page, clear_storage=True)
        over = await c.eval("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if over and over > 1:
            failures.append(f"{page}: overflow {over}px")
    await phone_off(c)
    return ("No page scrolls sideways at 320px", not failures, "; ".join(failures) or "6/6 pages OK")


async def test_phone_atlas_header_not_sticky(c):
    # On desktop the Atlas header is a one-row sticky bar; on a phone it wraps
    # to ~330px, so it must become static there or it hides half the screen.
    await phone_on(c)
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    phone = await c.eval("getComputedStyle(document.querySelector('header')).position")
    over = await c.eval("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    await phone_off(c)
    await c.goto(BASE + "/resume-atlas.html")
    desktop = await c.eval("getComputedStyle(document.querySelector('header')).position")
    return (
        "Atlas header is static on phones and sticky on desktop",
        phone == "static" and desktop == "sticky" and (over or 0) <= 1,
        f"phone={phone} desktop={desktop} overflow={over}",
    )


async def test_phone_menus_within_viewport(c):
    # The FX and Look & Feel menus drop down from mid-row buttons; at phone
    # widths they must not hang off either edge of the screen.
    failures = []
    for width, height in ((375, 667), (320, 568), (667, 375)):
        await phone_on(c, width, height)
        await c.goto(BASE + "/", clear_storage=True)
        for summary_sel, menu_sel in ((".fx-panel summary", ".fx-menu"), (".appearance-menu", None)):
            if menu_sel is None:
                js_open = "(function(){var m=document.querySelector('.appearance-menu');var d=m&&m.closest('details');if(d){d.open=true;}return !!d;})()"
                await c.eval(js_open)
                menu_sel = ".appearance-menu"
            else:
                await c.eval(f"document.querySelector('{summary_sel}').click()")
            await asyncio.sleep(0.3)
            rect = json.loads(await c.eval(
                f"JSON.stringify((function(){{var m=document.querySelector('{menu_sel}');if(!m)return null;var r=m.getBoundingClientRect();"
                f"return {{l:Math.round(r.left),r:Math.round(r.right),b:Math.round(r.bottom),w:Math.round(r.width),vw:innerWidth,vh:innerHeight}};}})())"
            ) or "null")
            if not rect or rect["w"] < 200 or rect["l"] < -1 or rect["r"] > rect["vw"] + 1 or rect["b"] > rect["vh"] + 1:
                failures.append(f"{width}px {menu_sel}: {rect}")
            await c.eval("document.querySelectorAll('details[open]').forEach(function(d){d.open=false})")
    await phone_off(c)
    return ("FX and Look & Feel menus stay inside the viewport on phones (375, 320, landscape)", not failures, "; ".join(failures) or "both menus fit at all three sizes")


DOCK_RECT = (
    "JSON.stringify((function(){var d=document.querySelector('.bsc-dock');var p=d&&d.querySelector('.bsc-dock-panel');"
    "if(!p)return null;var r=p.getBoundingClientRect();var links=d.querySelectorAll('.bsc-dock-link').length;"
    "return {open:d.open,top:Math.round(r.top),bottom:Math.round(r.bottom),vh:innerHeight,links:links};})())"
)


async def test_phone_dock_fits_landscape_and_closes(c):
    # Landscape phones are only 375px tall: the open dock panel must fit (or
    # scroll) instead of running off the top, and a tap outside must close it.
    failures = []
    for page in ("/", "/resume-atlas.html"):
        await phone_on(c, 667, 375)
        await c.goto(BASE + page, clear_storage=True)
        # Home only shows its dock after 160px of scroll.
        await c.eval("window.scrollTo(0, 700)")
        await asyncio.sleep(0.4)
        await c.eval("document.querySelector('.bsc-dock summary').click()")
        await asyncio.sleep(0.5)
        opened = json.loads(await c.eval(DOCK_RECT) or "null")
        if not opened or not opened["open"] or opened["top"] < -1 or opened["bottom"] > opened["vh"] + 1 or opened["links"] < 6:
            failures.append(f"{page} open: {opened}")
        # A pointerdown anywhere outside the dock should close it.
        await c.eval("document.querySelector('main, body').dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX:20, clientY:20}))")
        await asyncio.sleep(0.3)
        closed = json.loads(await c.eval(DOCK_RECT) or "null")
        if not closed or closed["open"]:
            failures.append(f"{page} did not close on outside tap: {closed}")
    await phone_off(c)
    return ("Dock panel fits a landscape phone and closes on an outside tap", not failures, "; ".join(failures) or "Home and Atlas OK")


# Portrait and landscape: a phone held sideways is wider than the narrow-screen
# breakpoints, so the touch rules must key on the pointer, not only the width.
PHONE_SIZES = ((375, 667), (667, 375))


async def test_phone_inputs_at_least_16px(c):
    failures = []
    for width, height in PHONE_SIZES:
        await phone_on(c, width, height)
        for page in PAGES:
            await c.goto(BASE + page, clear_storage=True)
            small = json.loads(await c.eval(SMALL_INPUTS) or "[]")
            if small:
                failures.append(f"{width}x{height} {page}: {small}")
    await phone_off(c)
    return ("No text field is under 16px on phones, portrait or landscape (avoids iOS focus zoom)", not failures, "; ".join(failures) or "6/6 pages OK at both sizes")


async def test_phone_tap_targets(c):
    failures = []
    for width, height in PHONE_SIZES:
        await phone_on(c, width, height)
        for page in PAGES:
            await c.goto(BASE + page, clear_storage=True)
            short = json.loads(await c.eval(SHORT_TARGETS) or "[]")
            if short:
                failures.append(f"{width}x{height} {page}: {short}")
    await phone_off(c)
    return ("Buttons, fields and standalone links are tall enough to tap on phones, portrait or landscape", not failures, "; ".join(failures) or "6/6 pages OK at both sizes")


async def test_phone_text_at_least_12px(c):
    await phone_on(c)
    failures = []
    for page in PAGES:
        await c.goto(BASE + page, clear_storage=True)
        # Open the dock so its labels are measured too (closed <details> content
        # may or may not be measurable depending on the Chrome version).
        await c.eval("var d=document.querySelector('.bsc-dock'); if(d) d.open=true")
        if page == "/":
            # Open the FX menu so its labels are measured too.
            await c.eval("document.querySelector('.fx-panel summary').click()")
            await asyncio.sleep(0.3)
        info = json.loads(await c.eval(MIN_FONT) or "{}")
        if info.get("min", 0) < 12:
            failures.append(f"{page}: {info}")
    await phone_off(c)
    return ("No visible text is smaller than 12px on phones", not failures, "; ".join(failures) or "6/6 pages OK")


async def test_phone_home_skips_3d_stack(c):
    # On a phone the default atmosphere uses the CSS fallback instead of
    # downloading three.js, but an explicit swatch choice still loads it.
    await phone_on(c)
    await c.goto(BASE + "/", clear_storage=True)
    await asyncio.sleep(0.8)
    default_cdn = [u.split("/")[-1] for u in c.requests if "cdn.jsdelivr.net" in u]
    effect = await c.eval("document.documentElement.getAttribute('data-effect')")
    await c.eval("var b=document.querySelector('[data-effect-btn=\"fog\"]'); b && b.click()")
    await asyncio.sleep(2.5)
    chosen_cdn = [u.split("/")[-1] for u in c.requests if "cdn.jsdelivr.net" in u]
    await phone_off(c)
    return (
        "Phones skip three.js by default but honour an explicit effect choice",
        not default_cdn and bool(effect) and "three.min.js" in chosen_cdn,
        f"default={default_cdn} effect={effect} after-choice={chosen_cdn}",
    )


async def test_phone_presets_fit_rail(c):
    await phone_on(c)
    await c.goto(BASE + "/", clear_storage=True)
    info = json.loads(await c.eval(
        "JSON.stringify((function(){var g=document.querySelector('.presets');if(!g)return null;var gr=g.getBoundingClientRect();"
        "var a=g.children[0].getBoundingClientRect();var b=g.children[1].getBoundingClientRect();"
        "return {railR:Math.round(gr.right),firstR:Math.round(a.right),secondL:Math.round(b.left),n:g.children.length};})())"
    ) or "null")
    await phone_off(c)
    ok = bool(info) and info["firstR"] <= info["railR"] + 1 and info["secondL"] < info["railR"] + 1
    return ("Preset cards fit the rail with the next card peeking at 375px", ok, f"{info}")


async def test_phone_touch_labels_and_dock_search(c):
    # Touch users have no keyboard: the palette button says "Search", the
    # subpage dock offers a Search pages button, and keyboard hints are hidden.
    await phone_on(c)
    await c.goto(BASE + "/", clear_storage=True)
    label = (await c.eval("document.getElementById('cmdPalBtn').textContent") or "").strip()
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    await c.eval("document.querySelector('.bsc-dock summary').click()")
    await asyncio.sleep(0.3)
    clicked = await c.eval(
        "(function(){var b=Array.from(document.querySelectorAll('.bsc-dock button')).find(function(x){return /search/i.test(x.textContent)});"
        "if(!b)return false;b.click();return true;})()"
    )
    await asyncio.sleep(0.4)
    pal_open = await c.eval("(function(){var p=document.getElementById('cmd-pal');return !!p && !p.hidden;})()")
    await c.eval("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    text = await c.eval(VISIBLE_TEXT)
    hint_hidden = "Press / to search" not in (text or "")
    await c.eval("document.querySelector('.search').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    await asyncio.sleep(0.2)
    focused = await c.eval("document.activeElement && document.activeElement.id")
    await phone_off(c)
    ok = label == "Search" and clicked and pal_open and hint_hidden and focused == "search"
    return (
        "Touch users get a Search label, a dock Search button and no keyboard hints",
        ok,
        f"label={label!r} dockSearch={clicked} paletteOpened={pal_open} hintHidden={hint_hidden} tapFocus={focused!r}",
    )


# ─── Reach features: transitions, contact, print QR, offline, one-pager ──
# These cover the features that help a reader act on the resume: page
# transitions, saving the contact card and sharing, the QR on paper, the
# installable offline copy, and the tailored one-pager from Proof Hub.

# Records clipboard writes and hides the native share sheet, so the Share
# button takes its copy-link fallback and the test can read what it copied.
STUB_CLIPBOARD_NO_SHARE = (
    "(function(){window.__copied=[];try{Object.defineProperty(navigator,'share',{value:undefined,configurable:true});}catch(e){}"
    "try{Object.defineProperty(navigator,'clipboard',{value:{writeText:function(t){window.__copied.push(t);return Promise.resolve();}},configurable:true});}catch(e){}})();"
)
# Pretends the browser has a native share sheet and records what was shared.
STUB_SHARE = (
    "(function(){window.__shared=[];try{Object.defineProperty(navigator,'share',{value:function(d){window.__shared.push(d);return Promise.resolve();},configurable:true});}catch(e){}})();"
)
STUB_PRINT = "(function(){window.__prints=0;window.print=function(){window.__prints++;};})();"

CONTACT_PAGES = tuple(p for p in PAGES)  # every page carries contact details


async def test_view_transitions_declared(c):
    # Cross-document View Transitions are declared in the shared stylesheet,
    # the dock keeps its place across pages, and reduced motion turns them off.
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    supported = await c.eval("CSS.supports('view-transition-name: a')")
    info = json.loads(await c.eval(
        "JSON.stringify((function(){var css='';document.querySelectorAll('style').forEach(function(s){css+=s.textContent;});"
        "var dock=document.querySelector('.bsc-dock');return {declared:/@view-transition\\s*\\{[^}]*navigation\\s*:\\s*auto/.test(css),"
        "reduced:/prefers-reduced-motion[^{]*\\{[^@]*@view-transition\\s*\\{[^}]*navigation\\s*:\\s*none/.test(css),"
        "dockName:dock?getComputedStyle(dock).viewTransitionName:null};})())"
    ) or "{}")
    ok = info.get("declared") and info.get("reduced") and (not supported or info.get("dockName") == "bsc-dock")
    return ("View Transitions are declared, the dock is named, reduced motion disables them", bool(ok), f"supported={supported} {info}")


async def test_mailto_links_carry_mode_subject(c):
    # Every email link tells the recipient which page it came from.
    labels = {"/": "Home", "/resume-atlas.html": "Atlas", "/resume-signal.html": "Signal", "/proof-hub.html": "Proof Hub", "/resume-switchboard.html": "Switchboard", "/now.html": "Now"}
    failures = []
    for page in CONTACT_PAGES:
        await c.goto(BASE + page, clear_storage=True)
        hrefs = json.loads(await c.eval("JSON.stringify(Array.from(document.querySelectorAll('a[href^=\"mailto:\"]')).map(function(a){return a.getAttribute('href');}))") or "[]")
        bad = [h for h in hrefs if "subject=" not in h or labels[page].replace(" ", "%20") not in h.replace("+", "%20")]
        if not hrefs or bad:
            failures.append(f"{page}: {bad or 'no mailto links'}")
    return ("Every mailto link carries a subject naming its page", not failures, "; ".join(failures) or "6/6 pages OK")


async def test_save_contact_and_share(c):
    # The vCard downloads (also in plain mode), and Share falls back to copying
    # the link when there is no native share sheet, or uses it when there is.
    failures = []
    for page in CONTACT_PAGES:
        await c.goto(BASE + page + "?plain=1", clear_storage=True)
        info = json.loads(await c.eval(
            "JSON.stringify((function(){var a=document.querySelector('a[href$=\".vcf\"]');var s=document.querySelector('[data-bsc-share]');"
            "return {vcf:a?a.getAttribute('href'):null,download:a?a.hasAttribute('download'):false,share:!!s};})())"
        ) or "{}")
        if not info.get("vcf") or "?" in info["vcf"] or not info.get("download") or (not info.get("share") and page != "/now.html"):
            failures.append(f"{page}: {info}")
    text = await c.eval("fetch('brandon-clark.vcf').then(function(r){return r.ok?r.text():'HTTP '+r.status;})", await_promise=True)
    if not (text or "").startswith("BEGIN:VCARD") or "FN:Brandon S. Clark" not in text or "\r\n" not in text or "END:VCARD" not in text:
        failures.append(f"vcf content: {str(text)[:60]!r}")
    ident = await c.add_init_script(STUB_CLIPBOARD_NO_SHARE)
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    await c.eval("document.querySelector('[data-bsc-share]').click()")
    await asyncio.sleep(0.5)
    copied = json.loads(await c.eval("JSON.stringify(window.__copied||[])") or "[]")
    toast = await c.eval(VISIBLE_TEXT)
    await c.remove_init_script(ident)
    if not copied or not copied[0].startswith(BASE + "/resume-atlas.html") or "copied" not in (toast or "").lower():
        failures.append(f"copy fallback: copied={copied} toast={'copied' in (toast or '').lower()}")
    ident = await c.add_init_script(STUB_SHARE)
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    await c.eval("document.querySelector('[data-bsc-share]').click()")
    await asyncio.sleep(0.3)
    shared = json.loads(await c.eval("JSON.stringify(window.__shared||[])") or "[]")
    await c.remove_init_script(ident)
    if not shared or not str(shared[0].get("url", "")).startswith(BASE + "/resume-atlas.html"):
        failures.append(f"native share: {shared}")
    return ("Save contact downloads a valid vCard and Share copies or shares the link", not failures, "; ".join(failures) or "vCard valid on 6 pages; share and copy fallback OK")


async def test_print_shows_qr(c):
    # The printed resume carries a scannable link back to the live site; on
    # screen the QR stays hidden.
    failures = []
    for page in ("/resume-atlas.html", "/resume-signal.html", "/proof-hub.html"):
        await c.goto(BASE + page, clear_storage=True)
        # Hidden on screen means no rendered box (the image or an ancestor is display:none).
        on_screen = await c.eval("(function(){var q=document.querySelector('.print-qr');return q?(q.getClientRects().length?'visible':'none'):'missing';})()")
        await c.emulate_media("print")
        await asyncio.sleep(0.3)
        info = json.loads(await c.eval(
            "JSON.stringify((function(){var q=document.querySelector('.print-qr');if(!q)return null;var r=q.getBoundingClientRect();"
            "return {w:Math.round(r.width),h:Math.round(r.height),loaded:q.naturalWidth>0||q.complete,display:getComputedStyle(q).display};})())"
        ) or "null")
        await c.emulate_media("")
        if on_screen != "none" or not info or info["w"] < 60 or info["h"] < 60 or not info["loaded"]:
            failures.append(f"{page}: screen={on_screen} print={info}")
    return ("Atlas, Signal and Proof Hub print a QR code to the live site", not failures, "; ".join(failures) or "3/3 pages OK")


async def test_manifest_and_icons(c):
    failures = []
    # 404.html is served at any URL depth, so it carries no relative manifest link.
    for page in CONTACT_PAGES:
        await c.goto(BASE + page, clear_storage=True)
        info = json.loads(await c.eval(
            "JSON.stringify({manifest:(document.querySelector('link[rel=manifest]')||{}).getAttribute?document.querySelector('link[rel=manifest]').getAttribute('href'):null,"
            "theme:document.querySelectorAll('meta[name=theme-color]').length})"
        ) or "{}")
        if info.get("manifest") != "site.webmanifest" or info.get("theme") != 1:
            failures.append(f"{page}: {info}")
    manifest = await c.eval("fetch('site.webmanifest').then(function(r){return r.json();})", await_promise=True)
    icons = {i.get("sizes"): i.get("src") for i in (manifest or {}).get("icons", [])}
    if not manifest or manifest.get("display") != "standalone" or "192x192" not in icons or "512x512" not in icons:
        failures.append(f"manifest: {manifest}")
    else:
        for src in icons.values():
            ok = await c.eval(f"fetch('{src}').then(function(r){{return r.ok;}})", await_promise=True)
            if not ok:
                failures.append(f"icon missing: {src}")
    return ("Every page links a valid web app manifest with 192 and 512px icons", not failures, "; ".join(failures) or f"6/6 pages; icons {sorted(icons)}")


async def test_service_worker_offline(c):
    # The worker is opt-in on localhost (?sw=1) and absent otherwise. It is
    # exercised on a throwaway second server (its own origin, so the rest of
    # the suite never sees a worker) which is then stopped: cached pages must
    # still render and unknown pages must get the offline page. DevTools
    # offline emulation does not reach service-worker fetches, hence the stop.
    await c.goto(BASE + "/resume-atlas.html", clear_storage=True)
    regs_default = await c.eval("navigator.serviceWorker.getRegistrations().then(function(r){return r.length;})", await_promise=True)
    port2 = PORT + 1
    base2 = f"http://localhost:{port2}"
    server2 = serve_directory(ROOT, port=port2)
    try:
        await asyncio.sleep(0.6)
        # Another project on the same origin (github.io is shared) has a cache
        # of its own; activation must leave it alone.
        await c.goto(base2 + "/resume-atlas.html")
        await c.eval("caches.open('other-project-cache').then(function(){return true;})", await_promise=True)
        await c.goto(base2 + "/resume-atlas.html?sw=1")
        ready = await c.eval(
            "navigator.serviceWorker.ready.then(function(r){return new Promise(function(res){var n=0;(function poll(){"
            "caches.keys().then(function(keys){var k=keys.filter(function(x){return x.indexOf('bsc')===0;});"
            "if(k.length){caches.open(k[0]).then(function(cache){return cache.keys();}).then(function(reqs){"
            "if(reqs.length>=6||n++>=40){res({cache:k[0],urls:reqs.map(function(q){return q.url.split('/').pop();})});}else{setTimeout(poll,250);}});}"
            "else if(n++<40){setTimeout(poll,250);}else{res({cache:null,urls:[]});}});})();});})",
            await_promise=True,
        )
        urls = set((ready or {}).get("urls", []))
        cached_ok = bool((ready or {}).get("cache")) and {"resume-signal.html", "offline.html", "shared-enhancements.js"} <= urls
        other_kept = await c.eval("caches.has('other-project-cache')", await_promise=True)
    finally:
        server2.terminate()
        server2.wait(timeout=5)
    await asyncio.sleep(0.3)
    await c.goto(base2 + "/resume-signal.html")
    offline_name = await c.eval("(document.querySelector('h1')||{}).textContent||''")
    await c.goto(base2 + "/not-cached-page.html")
    offline_fallback = await c.eval(VISIBLE_TEXT)
    await c.eval(
        "Promise.all([navigator.serviceWorker.getRegistrations().then(function(rs){return Promise.all(rs.map(function(r){return r.unregister();}));}),"
        "caches.keys().then(function(ks){return Promise.all(ks.map(function(k){return caches.delete(k);}));})])",
        await_promise=True,
    )
    regs_after = await c.eval("navigator.serviceWorker.getRegistrations().then(function(r){return r.length;})", await_promise=True)
    await c.goto(BASE + "/resume-atlas.html")
    ok = regs_default == 0 and cached_ok and other_kept and "Brandon" in (offline_name or "") and "offline" in (offline_fallback or "").lower() and regs_after == 0
    return (
        "Service worker is opt-in, caches the pages, keeps other caches, and serves pages with the server gone",
        ok,
        f"default_regs={regs_default} cache={(ready or {}).get('cache')} cached={len(urls)} otherCacheKept={other_kept} offlineSignal={'Brandon' in (offline_name or '')} fallback={'offline' in (offline_fallback or '').lower()} after={regs_after}",
    )


async def test_proof_hub_one_pager(c):
    # Picked bullets print as a one-page brief; without picks a pasted JD
    # drives the selection; with neither nothing prints.
    ident = await c.add_init_script(STUB_PRINT)
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    picked = json.loads(await c.eval(
        "JSON.stringify((function(){var btns=Array.from(document.querySelectorAll('.bullet .pick-btn')).slice(0,2);"
        "return btns.map(function(b){b.click();return b.closest('.bullet').querySelector('.bullet-text').textContent.trim().slice(0,40);});})())"
    ) or "[]")
    await c.eval("document.getElementById('onepagerBtn').click()")
    await asyncio.sleep(0.5)
    prints = await c.eval("window.__prints")
    flagged = await c.eval("document.documentElement.getAttribute('data-onepager')")
    await c.emulate_media("print")
    await asyncio.sleep(0.3)
    info = json.loads(await c.eval(
        "JSON.stringify((function(){var o=document.getElementById('onepager');if(!o)return null;var r=o.getBoundingClientRect();var txt=o.innerText;"
        "var q=o.querySelector('img[src*=\"qr\"]');var jd=document.getElementById('jd');var b=document.querySelector('.bullet');"
        "var vis=function(el){if(!el)return false;var cs=getComputedStyle(el);var rr=el.getBoundingClientRect();return cs.display!=='none'&&rr.width>0&&rr.height>0;};"
        "return {visible:vis(o),h:Math.round(r.height),name:/Brandon S\\. Clark/.test(txt),contact:/bsc_pro@protonmail\\.com/.test(txt),qr:!!q&&q.naturalWidth>0,jdHidden:!vis(jd),bulletsHidden:!vis(b),text:txt.slice(0,2000)};})())"
    ) or "null")
    await c.emulate_media("")
    await c.eval("window.dispatchEvent(new Event('afterprint'))")
    await asyncio.sleep(0.2)
    cleared = await c.eval("document.documentElement.getAttribute('data-onepager')")
    hidden_on_screen = await c.eval("(function(){var o=document.getElementById('onepager');return !o||getComputedStyle(o).display==='none';})()")
    pick_ok = bool(info) and info["visible"] and all(p in info["text"] for p in picked) and info["name"] and info["contact"] and info["qr"] and info["jdHidden"] and info["bulletsHidden"]
    # JD-driven selection without picks.
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    await c.eval("var t=document.getElementById('jd');t.value='Terraform AWS IoT provisioning Python';t.dispatchEvent(new Event('input',{bubbles:true}));")
    await asyncio.sleep(0.8)
    jd_count = await c.eval("typeof window.bscBuildOnePager==='function'?window.bscBuildOnePager():-1")
    jd_text = await c.eval("(document.getElementById('onepager')||{}).innerText||''")
    # Every bullet picked: the height cap must trim the list to one Letter page.
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    fit = json.loads(await c.eval(
        "JSON.stringify((function(){document.querySelectorAll('.bullet .pick-btn').forEach(function(b){b.click();});"
        "var n=window.bscBuildOnePager();var s=document.getElementById('onepager');s.classList.add('op-measure');var h=s.offsetHeight;s.classList.remove('op-measure');"
        "var more=(s.querySelector('.op-more')||{}).textContent||'';return {kept:n,h:h,more:more.slice(0,12)};})())"
    ) or "{}")
    fits = bool(fit) and 0 < fit.get("kept", 0) <= 14 and fit.get("h", 9999) <= 965 and fit.get("more", "").startswith("+")
    # Neither picks nor JD: toast, no print.
    await c.goto(BASE + "/proof-hub.html", clear_storage=True)
    await c.eval("document.getElementById('onepagerBtn').click()")
    await asyncio.sleep(0.4)
    no_prints = await c.eval("window.__prints")
    await c.remove_init_script(ident)
    ok = len(picked) == 2 and prints == 1 and flagged == "1" and pick_ok and cleared is None and hidden_on_screen and jd_count and jd_count > 0 and "matched to" in jd_text.lower() and fits and no_prints == 0
    return (
        "Proof Hub prints a tailored one-pager from picks or JD matches, and nothing without either",
        bool(ok),
        f"picked={len(picked)} prints={prints} flagged={flagged} pickOK={pick_ok} cleared={cleared} hiddenOnScreen={hidden_on_screen} jdCount={jd_count} jdTerms={'matched to' in jd_text.lower()} fit={fit} noPrints={no_prints}" + ("" if pick_ok else f" info={ {k: v for k, v in (info or {}).items() if k != 'text'} }"),
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
    test_phone_no_horizontal_overflow_320,
    test_phone_atlas_header_not_sticky,
    test_phone_menus_within_viewport,
    test_phone_dock_fits_landscape_and_closes,
    test_phone_inputs_at_least_16px,
    test_phone_tap_targets,
    test_phone_text_at_least_12px,
    test_phone_home_skips_3d_stack,
    test_phone_presets_fit_rail,
    test_phone_touch_labels_and_dock_search,
    test_view_transitions_declared,
    test_mailto_links_carry_mode_subject,
    test_save_contact_and_share,
    test_print_shows_qr,
    test_manifest_and_icons,
    test_service_worker_offline,
    test_proof_hub_one_pager,
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
