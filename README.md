# Brandon S. Clark — Audience-Routed Resume Site

> Not one resume. A system. Built for the way people actually hire.

Most resume sites force every reader through the same generic page. This one routes them to the version that fits how they actually evaluate candidates — and it does it in plain static HTML with no framework and no build step.

**Senior Software Engineer — AWS Backend / Cloud Platform.** Five years at Milwaukee Tool building serverless APIs, platform tooling, and data foundations. Prior: $85M payment portal, 1,200-hour automation, and full-stack product work across fintech and public sector.

**Live site:** [northwoodscode.github.io/resume](https://northwoodscode.github.io/resume/)

---

## The five entry points

| Page | Audience | What it does |
| ---- | -------- | ------------ |
| [Home](https://northwoodscode.github.io/resume/) | First impression | One dated claim whose numbers open their receipts, a facts strip (employer, years, location, certifications, stack), a fit check that scores a pasted job description in the browser, a "verified in real Chrome" chip with live checks, then audience routing, an animated backdrop that loads on demand (plus two hand-drawn canvas backdrops, Leaves and Embers), optional effects (off by default), command palette, theme toggle, and a tailored-link builder |
| [Atlas](https://northwoodscode.github.io/resume/resume-atlas.html) | Recruiters / ATS | Classic document layout — clean, fast, print-to-PDF safe |
| [Signal](https://northwoodscode.github.io/resume/resume-signal.html) | Hiring managers | Focus-filtered view with shareable URLs and copy-ready ATS text |
| [Proof Hub](https://northwoodscode.github.io/resume/proof-hub.html) | Technical interviewers | Case studies, decisions and the road not taken, things that broke on my watch, screen-call answers, accomplishment inventory, JD matching, and bullet export |
| [Switchboard](https://northwoodscode.github.io/resume/resume-switchboard.html) | Reduced-motion / conservative browsers | Plain, privacy-first routing hub |

Plus [/now](https://northwoodscode.github.io/resume/now.html), a short "what I'm building, learning, reading" page. Every page shares a command palette (`Ctrl+K` / `⌘K`) and a "Resume modes" dock for moving between views.

---

## Why this exists

Hiring reviewers don't all want the same thing. A recruiter skimming in 20 seconds needs something different than a hiring manager prepping for a loop, which is different again from a technical interviewer who wants proof behind the bullets.

This repo solves that without making the candidate rewrite five separate resumes by hand.

The design principles:

- **Reader-first, not author-first.** Each mode is optimized for one specific audience, not for the convenience of maintaining a single file.
- **No framework tax.** Every page is standalone HTML, CSS, and vanilla JS — readable, forkable, and deployable to GitHub Pages in one push.
- **Depth on demand.** The Home and Switchboard pages explain where to go. Atlas gives a fast signal. Signal and Proof Hub reward closer reads.

---

## Evidence: receipts, decisions, incidents, answers

Every headline number on the site is a claim a reader can open. `evidence.json` holds a **receipt** per number (baseline, result, method, where, my role, a confidence level of *measured / logged / reported / stated / estimated*, an optional artifact) and the three lists Proof Hub renders: **decisions** (options considered, the choice, what it cost, how it held up), **incidents** (what broke, how it was found, the fix, the guard added) and **answers** (the screen-call questions, answered in advance). Any element marked `data-receipt="<id>"` becomes a button that opens the receipt; `shared-enhancements.js` owns that behaviour on every page.

Two rules keep it honest:

- `scripts/check_evidence.py` runs in CI and fails the build if a page claims a receipt that does not exist, a receipt lacks its fields, a confidence level is unknown, or a payload sample's byte count disagrees with the number it states.
- Entries marked `"draft": true` and keys starting with `_` are author notes. Locally they render with a **DRAFT** badge so they can be previewed; `scripts/strip_drafts.py` removes them at deploy and the strict lint confirms nothing unfinished (no draft, no note, no `TODO` text) is left. A list with nothing published hides its section and nav chip. The notes stay readable in this public repository, on purpose: they are the to-do list for the evidence.

To publish a decision, incident or answer: fill its fields in `evidence.json`, delete `"draft": true`, run `python3 scripts/check_evidence.py`, commit.

Home also carries a **fit check** (`home-evidence.js`): paste a job description and the posting's skills are detected, scored against `resume-ats.txt` and shown as strong matches, partial matches and, in the open, the skills the resume does not have. It runs entirely in the browser; the text is never sent anywhere. "Open these matches in Proof Hub" hands the posting over through `sessionStorage`, where Proof Hub's JD matcher picks it up. The **verified chip** shows the last CI test run (`tests-latest.json`, written by `tests/test_home.py --report` and published with each deploy) and runs seven checks live in the reader's browser.

---

## Signal — the interactive mode

Signal is the most powerful entry point for hiring managers and role-specific tailoring.

Focus filters let you surface the work most relevant to a given role without rewriting anything:

```text
resume-signal.html?focus=cloud,api
resume-signal.html?focus=iot,data
resume-signal.html?focus=lead,enable
resume-signal.html?focus=ai,opex
```

Focus keys: `cloud`, `api`, `iot`, `data`, `opex`, `lead`, `enable`, `ai`. Common aliases (`leadership`, `enablement`, `genai`, `ops`) are mapped automatically; unknown keys are reported on the page instead of silently ignored. Add `&only=1` to hide non-matching bullets and `&q=term` to search. Each filtered URL is shareable, Back/Forward restores the filters, and the view produces copy-ready ATS-formatted text.

---

## Tech

- Static HTML / CSS / Vanilla JavaScript — no framework, no build step
- **11 atmospheres** (blue, crimson, emerald, violet, ghost, void, amethyst, graphite, ink, bronze, autumn), each with light and dark tokens, across **7 visual effects** (still, leaves, embers, fog, clouds, ocean, depth). Leaves and Embers are hand-drawn 2D canvases that need no library or WebGL; Three.js and the one Vanta bundle an effect needs load on demand, only for fog, clouds, ocean and depth, and never under `?plain=1` or `prefers-reduced-motion`
- **FX panel** on Home — toggles for cursor spotlight, 3D card tilt, click sparks and a confetti burst on load, all off by default (confetti and sparks are skipped under `?plain=1` and `prefers-reduced-motion`; with the Embers backdrop active, click sparks rise from the backdrop canvas instead of the page); choices persist to `localStorage`, and other pages run no effects
- **Command palette** (`⌘K` / `Ctrl+K`) and **mode dock** on every page, provided by `shared-enhancements.js`
- **Reach features**: cross-document View Transitions between modes (off under `prefers-reduced-motion` and `?plain=1`); **Save contact** (vCard) and **Share** (native share sheet, or copy the link) next to the contact details; mail links carry a subject naming the page; a **QR code** to the live site on the printed Atlas, Signal and Proof Hub; a web app manifest plus a service worker (`sw.js`, registered on HTTPS only) so the resume installs to a home screen and opens offline; and a **tailored one-pager** printed from Proof Hub's picked bullets or job-description matches
- Availability badge, facts strip, receipts behind every number (the two in the hero claim pulse once after load; off under reduced motion and plain mode), scroll-reveal that fails open (print and no-observer browsers see everything)
- Print stylesheets on Atlas, Signal and Proof Hub keep the name and contact block, force light tokens, and print link URLs; `resume-atlas.html?print=1` opens the print dialog directly
- Local browser storage for theme, atmosphere, effect, and FX preferences, guarded so blocked storage never breaks a page
- Structured data (JSON-LD), OG tags, favicons, sitemap, and robots.txt for SEO
- GitHub Pages deployment via GitHub Actions — tests gate every deploy
- Headless-Chrome UI test suite (CDP over websockets) runs on every push and PR: print identity, deep links, focus filters, blocked storage, lazy loading, mobile overflow, dead links, receipts, fit check, live checks, evidence lists

---

## Run locally

```bash
python3 -m http.server 8000
# then open http://localhost:8000/
```

Or use VS Code Live Server. Avoid opening via `file://` — query-string features, copy actions, and print flows all behave correctly on a local server.

---

## Repo structure

```text
.
├── index.html                 # Home — cinematic landing + routing
├── resume-atlas.html          # Atlas — recruiter-safe document resume
├── resume-signal.html         # Signal — hiring manager + focus filters
├── proof-hub.html             # Proof Hub — evidence layer + case studies
├── resume-switchboard.html    # Switchboard — low-motion fallback hub
├── now.html                   # /now page
├── shared-enhancements.js     # Shared palette + dock, ?for= personalization, case share links, safe storage, opt-in FX,
│                              #   View Transitions, Share + mail subjects, service-worker registration, receipts + evidence lists
├── home-evidence.js           # Home only: fit check, facts strip years, verified chip + live checks
├── evidence.json              # Receipts behind every number; decisions, incidents, answers (drafts stripped at deploy)
├── tests-latest.json          # Placeholder; CI writes the real test report here at deploy
├── sw.js / site.webmanifest / offline.html   # installable, works offline (VERSION stamped at deploy)
├── brandon-clark.vcf          # "Save contact" vCard
├── qr-resume.svg              # QR to the live site, printed on Atlas / Signal / Proof Hub (scripts/gen_qr.py)
├── resume-ats.txt             # Plain-text ATS-friendly resume
├── favicon.ico / favicon.svg / apple-touch-icon.png / icon-192.png / icon-512.png / icon-512-maskable.png / og-image.png
├── robots.txt / sitemap.xml
├── 404.html                   # /for/<slug> pretty-URL redirect handler
├── cases.json / companies.json
├── scripts/
│   ├── check_evidence.py      # Lints evidence.json against the pages (runs in CI; --strict after stripping)
│   ├── strip_drafts.py        # Removes draft entries and author notes from evidence.json (run at deploy)
│   ├── gen_og.py              # OG image renderer (Pillow)
│   ├── gen_cases.py           # per-case OG art + /case/<slug>/ stub pages (run at deploy)
│   ├── gen_qr.py              # qr-resume.svg (python qrcode module; run by hand)
│   ├── gen_icons.py           # icon-192/512.png from the favicon mark (Pillow; run by hand)
│   └── stamp_dates.py         # writes last-updated dates and the sw.js cache version from git (run at deploy)
├── tests/
│   ├── harness.py             # CDP-over-websocket Chrome driver
│   └── test_home.py           # functional UI tests
└── .github/workflows/
    └── deploy.yml             # test → build → deploy to GitHub Pages
```

Intentionally flat. Each page owns its own markup, styling, and behavior; `shared-enhancements.js` is the one shared module and only adds optional desktop effects.

---

## Editing guide

Content is intentionally repeated across pages so each mode stays optimized for its audience. When making content updates, touch all of the following:

- Header / contact details on every page
- Core summary language in Atlas, Signal, and Proof Hub
- Key metrics (keep numbers consistent across modes, and update the matching receipt in `evidence.json`; a new number needs a new receipt and a `data-receipt` attribute)
- Case studies and accomplishment inventory in Proof Hub
- Routing copy in Home and Switchboard
- Preset links that point into Signal

After editing, verify:

- [ ] `python3 scripts/check_evidence.py` passes
- [ ] `python3 tests/test_home.py` from the repo root — all 60 functional tests pass (eleven emulate a phone; seven cover the reach features, including a real offline run; five cover the Embers backdrop; six cover receipts, the fit check, the live checks and the evidence lists)
- [ ] Home loads and routes correctly; `?plain=1` fallback works
- [ ] FX panel toggles each persist + visibly turn the corresponding effect on/off
- [ ] Signal presets open with the right focus areas active
- [ ] Atlas, Signal and Proof Hub print to PDF with the name and contact block on page one
- [ ] Proof Hub filters, JD matching, and copy actions work
- [ ] Switchboard routes readers to the right mode
- [ ] Theme toggles behave consistently across all pages

CI runs the test suite on every push and PR automatically; a regression blocks deploy.

---

## Deployment

Pushes to `main` deploy to GitHub Pages via the `.github/workflows/deploy.yml` workflow. The workflow first runs the headless-Chrome test suite — if any test fails, the deploy is skipped. Pull requests run the test suite only; the build and deploy jobs run on `main`. During the build, `scripts/stamp_dates.py` writes each page's last-updated date, the sitemap's `lastmod` values and the service worker's cache `VERSION` from git history, per-case OG art and `/case/<slug>/` stub pages are generated, the test job's report lands as `tests-latest.json`, and `scripts/strip_drafts.py` removes draft evidence and author notes (then `check_evidence.py --strict` confirms it), so none of those are committed.

**Production:** [northwoodscode.github.io/resume](https://northwoodscode.github.io/resume/)

One-time setup: repo **Settings → Pages → Build and deployment → Source → GitHub Actions**. While the source is still "Deploy from a branch", GitHub's own "pages build and deployment" job runs on every push and races this workflow (it can fail at startup and hold the Actions deploy in the queue).

Pretty `/for/<company>` links are handled by `404.html`, which redirects to `/?for=<company>` client-side (GitHub Pages has no server-side redirects).

Verify all six pages after deploy, plus `/case/payment-portal/` and `/for/stripe` (served by `404.html`, so it returns HTTP 404 with a client-side redirect; link unfurlers will not see OG tags for it).

---

## If you're reviewing this repo as a hiring manager or interviewer

Start with **[Signal](https://northwoodscode.github.io/resume/resume-signal.html)** or **[Proof Hub](https://northwoodscode.github.io/resume/proof-hub.html)**.

If you're a recruiter, start with **[Atlas](https://northwoodscode.github.io/resume/resume-atlas.html)**.
