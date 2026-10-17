# Readiness TODO

Ordered checklist to get the site accurate, working for readers, and safely deployed on GitHub Pages. Generated from a full code review on 2026-10-17. Each phase leaves the site in a shippable state; work top to bottom.

---

## Phase 0 — Make the deploy pipeline real

- [ ] Enable Pages manually: repo **Settings → Pages → Source → GitHub Actions**. The `enablement: true` in [deploy.yml](.github/workflows/deploy.yml#L61) is a no-op without a PAT (per `actions/configure-pages` docs), so either remove that line or add a token.
- [ ] Move `concurrency: group: pages` and the `pages: write` / `id-token: write` permissions off the workflow and onto the `deploy` job, so PR test runs don't queue behind deploys.
- [ ] Skip the configure/upload steps on `pull_request` events.
- [ ] Push, then verify all six routes load live, plus `/case/payment-portal/` and `/for/stripe`.

## Phase 1 — Content: one set of facts

- [ ] Pick one version of the Milwaukee Tool history (titles, dates, team names) and apply it to [resume-ats.txt](resume-ats.txt), Atlas, Signal, Proof Hub timeline, and Switchboard. The plain-text resume and the Proof Hub timeline currently disagree on the 2023 title.
- [ ] Fix the "~100 hours saved in a 100-device rollout" claim ([proof-hub.html:1149](proof-hub.html#L1149), [cases.json](cases.json), Signal). 100 devices × 9 min ≈ 15 hours.
- [ ] Decide whether the $40K saving is annual or total, then make all pages agree.
- [ ] Decide whether the Terraform Associate cert is listed. Add it to Atlas and Signal, or remove it from Proof Hub and the text resume. Fix "2 AWS certs" in Switchboard.
- [ ] Confirm SAA-C03 is still valid (earned 08/25/2022; three-year term).
- [ ] Reconcile "built from scratch" vs "assisted with the design" for the payment portal ([proof-hub.html:1533](proof-hub.html#L1533)).
- [ ] Remove internal review ratings ("Meets Expectations", "Exceeds") and internal team names from public pages, or make Proof Hub's Public Mode actually hide them in the Role Timeline.
- [ ] Delete author-facing notes that readers can see: [resume-switchboard.html:1031-1039](resume-switchboard.html#L1031-L1039), [:715-718](resume-switchboard.html#L715-L718), [proof-hub.html:991](proof-hub.html#L991), [:1045-1046](proof-hub.html#L1045-L1046), [:1716](proof-hub.html#L1716).
- [ ] Refresh stale dates: `now.html` ("Last refreshed 2026-05-28"), Proof Hub "Last updated: 2026-02-27", `sitemap.xml` lastmods, `AVAILABLE_UNTIL` in index.html (also parsed as UTC, so it hides a day early in US time zones).
- [ ] Decide whether [companies.json](companies.json) naming target employers is acceptable on a public site. If not, use opaque slugs.

## Phase 2 — Fix what readers actually do

- [ ] **Atlas PDF**: stop hiding `header` in print ([resume-atlas.html:256](resume-atlas.html#L256)) — it holds the name and contact details. Force light-theme variables under `@media print`. Add `break-inside: avoid` on `article.card` / `.rolehead`.
- [ ] **Signal print**: force light theme; print profile URLs, not bare words.
- [ ] **Proof Hub shortcuts** ([proof-hub.html:2892-2904](proof-hub.html#L2892-L2904)): return early when focus is in an input/textarea/contenteditable or a modifier key is held. Or drop single-key shortcuts entirely (also a WCAG 2.1.4 requirement).
- [ ] **Proof Hub case links**: on load and `hashchange`, open the `<details>` matching `location.hash` so `/case/<slug>/` lands on an expanded card instead of a one-line summary.
- [ ] **Switchboard**: remove the three `resume-switchboard-next.html` references ([:1061](resume-switchboard.html#L1061), [:1083](resume-switchboard.html#L1083), [:1092](resume-switchboard.html#L1092)) — the file doesn't exist. Fix the "Classic switchboard" self-link. Rename the title from "Switchboard+".
- [ ] **Home light mode**: the `html[data-atmosphere=…]` colour rules ([index.html:63+](index.html#L63)) override `:root` light values, leaving e.g. the hero phrase at ~1.2:1 contrast. Scope them to dark theme or add light variants. Dark-only atmospheres (ghost, void, graphite, ink, bronze, autumn, amethyst) need a light treatment or should force dark theme.
- [ ] **Home mobile**: the ⌘K button is hidden at ≤520px, so phones can't open the command palette. Add a visible trigger or a menu.
- [ ] **`/for/<slug>`**: generate `for/<slug>/index.html` stubs in `gen_cases.py` (like the case pages) so these return 200 with OG tags instead of being served by `404.html`.
- [ ] **Signal focus keys**: accept the README aliases (`leadership`, `enablement`, `genai`, `ops`) or fix the README. Real keys: `cloud, api, iot, data, opex, lead, enable, ai`. Add a `popstate` handler so Back updates the filters.
- [ ] Proof Hub small fixes: the `data-query="1200"` chip matches nothing (bullet text is "1,200+"); curly-quote `class=”mini”` at [:1165](proof-hub.html#L1165); `.bullet{padding-right:152px}` has no mobile override.

## Phase 3 — Robustness

- [ ] Wrap `localStorage` access in try/catch on Atlas, Signal, Switchboard and Proof Hub ([proof-hub.html:1732](proof-hub.html#L1732), [resume-signal.html:674](resume-signal.html#L674)). With storage blocked, the main script throws and every filter/copy button dies. Home already handles this.
- [ ] [shared-enhancements.js](shared-enhancements.js): `fxOn()` defaults effects **on** when `BSC_FX` is absent, so Switchboard ("low-motion") and Atlas get glow/tilt/sparks while Home keeps them off. Default off, or at minimum honour `?plain=1` for tilt. Pick one of `click`/`touchend` for sparks, not both (taps fire twice).
- [ ] Home Vanta loader ([index.html:2961-2985](index.html#L2961-L2985)): add a cancel token so a superseded `startVanta()` can't create a late FOG instance or leak a WebGL context.
- [ ] Home typing animation ([index.html:3341-3380](index.html#L3341-L3380)): re-call `tick()` on unlock so it doesn't freeze permanently.
- [ ] Home print: override the scroll-reveal `opacity:0` under `@media print` so unscrolled cards don't print blank.
- [ ] Hide the `?for=` badge and the injected stack-disclosure line in print on every page.
- [ ] Make copy fallbacks report failure instead of toasting "Copied" when `execCommand` fails.

## Phase 4 — README and tests tell the truth

- [ ] README: remove swipe-gesture claims (there is no gesture code in the repo or its history), change "18 tests" to the real count (16), fix the two broken `?focus=` examples.
- [ ] Fix the no-op tests: `test_fx_state_survives_reload` and `test_checkbox_syncs_with_programmatic_set` set `false` and assert `false`, which is the default. Set `true` so they actually exercise persistence.
- [ ] Delete the unused `swipe`, `slow_drag`, `click_target` helpers in [tests/harness.py](tests/harness.py), or implement swipe and use them.
- [ ] Add tests for: Signal `?focus=` actually filters; `#case-<slug>` opens the card; `/for/x` redirect; no 404'd resources (enable the CDP `Network` domain in the harness); Atlas print media shows the header (`Emulation.setEmulatedMedia`).

## Phase 5 — Polish

- [ ] Add `integrity` + `crossorigin` to the five CDN scripts in index.html.
- [ ] Only load Three/Vanta when the chosen effect needs them (not for still/leaves/plain/reduced-motion).
- [ ] Accessibility: labels on `#search`, `#jd` (Proof Hub) and `#q`, `#fastPitch` (Switchboard); `aria-live` on result counts; `aria-pressed` on filter buttons; focus trap in the command palette; stronger focus-ring contrast; remove `aria-live` from palette listboxes.
- [ ] [scripts/gen_og.py](scripts/gen_og.py): draw tag labels with `anchor="lm"` so they align vertically, and fail loudly if the Liberation fonts are missing instead of falling back to Pillow's bitmap font.

---

## Post-deploy checklist (every release)

- [ ] Six entry points load with no console errors
- [ ] Atlas → Print / Save PDF shows name + contact
- [ ] `/case/java-etl/` lands on an open card
- [ ] `?for=stripe` shows the badge and ticks Signal chips
- [ ] Light and dark themes readable on Home
- [ ] Phone: command palette reachable, Proof Hub bullets readable
