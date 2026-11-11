# Brandon S. Clark — Audience-Routed Resume Site

> Not one resume. A system. Built for the way people actually hire.

Most resume sites force every reader through the same generic page. This one routes them to the version that fits how they actually evaluate candidates — and it does it in plain static HTML with no framework and no build step.

**Senior Software Engineer — AWS Backend / Cloud Platform.** Five years at Milwaukee Tool building serverless APIs, platform tooling, and data foundations. Prior: $85M payment portal, 1,200-hour automation, and full-stack product work across fintech and public sector.

**Live site:** [northwoodscode.github.io/resume](https://northwoodscode.github.io/resume/)

---

## The five entry points

| Page | Audience | What it does |
| ---- | -------- | ------------ |
| [Home](https://northwoodscode.github.io/resume/) | First impression | Landing page with audience routing, an animated backdrop that loads on demand, optional effects (off by default), command palette, theme toggle, and a tailored-link builder |
| [Atlas](https://northwoodscode.github.io/resume/resume-atlas.html) | Recruiters / ATS | Classic document layout — clean, fast, print-to-PDF safe |
| [Signal](https://northwoodscode.github.io/resume/resume-signal.html) | Hiring managers | Focus-filtered view with shareable URLs and copy-ready ATS text |
| [Proof Hub](https://northwoodscode.github.io/resume/proof-hub.html) | Technical interviewers | Case studies, accomplishment inventory, JD matching, and bullet export |
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
- **11 atmospheres** (blue, crimson, emerald, violet, ghost, void, amethyst, graphite, ink, bronze, autumn), each with light and dark tokens, across **6 visual effects** (still, leaves, fog, clouds, ocean, depth). Three.js and the one Vanta bundle an effect needs load on demand, only for fog, clouds, ocean and depth, and never under `?plain=1` or `prefers-reduced-motion`
- **FX panel** on Home — a confetti burst pops on every load (skipped under `?plain=1` and `prefers-reduced-motion`), plus toggles for cursor spotlight, 3D card tilt and click sparks, which are off by default; choices persist to `localStorage`, and other pages run no effects
- **Command palette** (`⌘K` / `Ctrl+K`) and **mode dock** on every page, provided by `shared-enhancements.js`
- Hero typing animation (runs once), availability badge, scroll-reveal that fails open (print and no-observer browsers see everything)
- Print stylesheets on Atlas, Signal and Proof Hub keep the name and contact block, force light tokens, and print link URLs; `resume-atlas.html?print=1` opens the print dialog directly
- Local browser storage for theme, atmosphere, effect, and FX preferences, guarded so blocked storage never breaks a page
- Structured data (JSON-LD), OG tags, favicons, sitemap, and robots.txt for SEO
- GitHub Pages deployment via GitHub Actions — tests gate every deploy
- Headless-Chrome UI test suite (CDP over websockets) runs on every push and PR: print identity, deep links, focus filters, blocked storage, lazy loading, mobile overflow, dead links

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
├── shared-enhancements.js     # Shared palette + dock, ?for= personalization, case share links, safe storage, opt-in FX
├── resume-ats.txt             # Plain-text ATS-friendly resume
├── favicon.ico / favicon.svg / apple-touch-icon.png / og-image.png
├── robots.txt / sitemap.xml
├── 404.html                   # /for/<slug> pretty-URL redirect handler
├── cases.json / companies.json
├── scripts/
│   ├── gen_og.py              # OG image renderer (Pillow)
│   ├── gen_cases.py           # per-case OG art + /case/<slug>/ stub pages (run at deploy)
│   └── stamp_dates.py         # writes last-updated dates from git history (run at deploy)
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
- Key metrics (keep numbers consistent across modes)
- Case studies and accomplishment inventory in Proof Hub
- Routing copy in Home and Switchboard
- Preset links that point into Signal

After editing, verify:

- [ ] `python3 tests/test_home.py` from the repo root — all 32 functional tests pass
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

Pushes to `main` deploy to GitHub Pages via the `.github/workflows/deploy.yml` workflow. The workflow first runs the headless-Chrome test suite — if any test fails, the deploy is skipped. Pull requests run the test suite only; the build and deploy jobs run on `main`. During the build, `scripts/stamp_dates.py` writes each page's last-updated date and the sitemap's `lastmod` values from git history, and per-case OG art and `/case/<slug>/` stub pages are generated, so none of those are committed.

```text
Production:  https://northwoodscode.github.io/resume/
```

One-time setup: repo **Settings → Pages → Source → GitHub Actions** (already done for the live site).

Pretty `/for/<company>` links are handled by `404.html`, which redirects to `/?for=<company>` client-side (GitHub Pages has no server-side redirects).

Verify all six pages after deploy, plus `/case/payment-portal/` and `/for/stripe` (served by `404.html`, so it returns HTTP 404 with a client-side redirect; link unfurlers will not see OG tags for it).

---

## If you're reviewing this repo as a hiring manager or interviewer

Start with **[Signal](https://northwoodscode.github.io/resume/resume-signal.html)** or **[Proof Hub](https://northwoodscode.github.io/resume/proof-hub.html)**.

If you're a recruiter, start with **[Atlas](https://northwoodscode.github.io/resume/resume-atlas.html)**.
