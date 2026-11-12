/* shared-enhancements.js — the one script every page loads (last in <body>).

   What it provides, in the order it runs:
     1. BSC_STORE   localStorage access that never throws (private mode, blocked
                    storage) so a missing preference can never kill a page.
     2. A print-only stylesheet that hides the overlays below.
     3. A toast, and a clipboard helper (window.bscCopy) that reports failure
        instead of pretending the copy worked.
     4. A shared command palette (Ctrl/Cmd+K) on pages that have none of their own.
     5. A shared "Resume modes" dock on pages that have none of their own.
     6. Optional desktop effects (cursor glow, card tilt, click sparks), but only
        on Home, where the FX panel exists and the reader can switch them on.
     7. "Copy share link" buttons on each case study (ids case-<slug>).
     8. ?for=<company> personalization driven by companies.json.
     9. The "Built with…" line in Home's footer.

   Everything is wrapped in one IIFE so nothing leaks except the few window.*
   helpers that pages and tests use (BSC_STORE, bscCopy, bscOpenPalette,
   bscSharedToast). Plain ES5-style code on purpose: no build step, old browsers
   degrade gracefully. */
(function(){
  'use strict';
  var html = document.documentElement;
  var params = new URLSearchParams(location.search);
  // Readers who ask the OS for less motion, or who opened ?plain=1, get no effects.
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var plain = html.classList.contains('plain') || params.get('plain') === '1';
  // The file name identifies the page ("" at the site root means index.html).
  var page = ((location.pathname.split('/').pop() || 'index.html').replace(/[?#].*/, '')) || 'index.html';
  var isHome = page === 'index.html';
  // The site map used by the palette and the dock. Order is the reading order.
  var PAGES = [
    {file:'index.html',              label:'Home',        desc:'Routing page'},
    {file:'resume-atlas.html',       label:'Atlas',       desc:'Classic recruiter / PDF view'},
    {file:'resume-signal.html',      label:'Signal',      desc:'Interactive tailored resume'},
    {file:'proof-hub.html',          label:'Proof Hub',   desc:'Cases, bullets, and hard evidence'},
    {file:'resume-switchboard.html', label:'Switchboard', desc:'Plain routing hub'},
    {file:'now.html',                label:'Now',         desc:'What I\'m building, learning, reading'}
  ];

  /* ── storage that never throws ───────────────────────────────── */
  var store = {
    get: function(k){ try { return localStorage.getItem(k); } catch(e){ return null; } },
    set: function(k, v){ try { localStorage.setItem(k, v); return true; } catch(e){ return false; } },
    remove: function(k){ try { localStorage.removeItem(k); } catch(e){} }
  };
  window.BSC_STORE = store;

  // window.BSC_FX is defined by Home's inline script before this file runs and
  // holds the FX panel toggles. Where it is absent (every other page) an effect
  // is simply off; nothing here ever defaults an effect on.
  function fxOn(key){
    return !!(window.BSC_FX && window.BSC_FX.get(key));
  }
  function accentColor(){
    return getComputedStyle(html).getPropertyValue('--accent').trim() || '#86a6ff';
  }
  function addStyle(id, css){
    if(document.getElementById(id)) return;
    var st = document.createElement('style'); st.id = id; st.textContent = css;
    document.head.appendChild(st);
  }
  // In-site links keep ?plain=1 so a reader who chose the calm mode keeps it
  // when they move between pages.
  function siteLink(file){
    return plain ? file + (file.indexOf('?') > -1 ? '&' : '?') + 'plain=1' : file;
  }

  // None of the overlays this script creates belong on paper.
  addStyle('bsc-shared-print-style',
    '@media print{.bsc-dock,#cmd-pal,#bsc-toast,#cursor-glow,[data-for-badge],[data-bsc-stack],[data-case-share]{display:none !important}}');
  // The Proof Hub case share buttons (created further down) are small icons
  // next to each case title; on phones and touch screens they grow to a 40px
  // tap target. A stylesheet rule, not an inline style, so pages can override it.
  addStyle('bsc-share-style',
    '[data-case-share]{min-width:32px;min-height:28px}' +
    '@media(max-width:640px),(hover:none) and (pointer:coarse){[data-case-share]{min-width:40px;min-height:40px}}');

  /* ── toast ───────────────────────────────────────────────────── */
  function toast(msg){
    var t = document.getElementById('bsc-toast');
    if(!t){
      addStyle('bsc-toast-style',
        '#bsc-toast{position:fixed;left:50%;bottom:72px;transform:translateX(-50%) translateY(8px);z-index:100000;' +
        'padding:.55rem .9rem;border-radius:999px;font:600 .85rem/1.2 system-ui,sans-serif;background:#111827;color:#f9fafb;' +
        'box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;pointer-events:none;transition:opacity .18s ease,transform .18s ease}' +
        '#bsc-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}');
      t = document.createElement('div'); t.id = 'bsc-toast'; t.setAttribute('role','status'); t.setAttribute('aria-live','polite');
      document.body.appendChild(t);
    }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._timer); t._timer = setTimeout(function(){ t.classList.remove('show'); }, 1800);
  }
  window.bscSharedToast = toast;

  /* ── clipboard with honest feedback ──────────────────────────── */
  // navigator.clipboard only exists in secure contexts (https, localhost) and can
  // reject; execCommand('copy') is the fallback and returns false when it fails.
  // Callers get a boolean promise and show a failure toast instead of "Copied".
  function legacyCopy(text){
    var ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly',''); ta.setAttribute('aria-hidden','true');
    ta.style.cssText = 'position:fixed;left:-9999px;top:0';
    document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = !!document.execCommand('copy'); } catch(e){ ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function copyText(text){
    if(navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext){
      return navigator.clipboard.writeText(text).then(function(){ return true; }, function(){ return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }
  window.bscCopy = copyText;
  var COPY_FAIL = 'Copy failed. Select the text and copy it manually.';

  /* ── shared command palette (pages without their own) ────────── */
  // Home has a richer palette of its own (atmosphere and effect actions), so this
  // one injects itself only where no #cmd-pal exists. Commands come from three
  // lists: NAV (the other pages), ACT (print, copy email, profiles) and JMP
  // (this page's own h2 headings, discovered from the DOM at load time).
  (function palette(){
    if(document.getElementById('cmd-pal')) return; // Home ships its own palette
    addStyle('bsc-cp-style', [
      '#cmd-pal{position:fixed;inset:0;z-index:99998;display:flex;align-items:flex-start;justify-content:center;padding-top:clamp(48px,9vh,130px)}',
      '#cmd-pal[hidden]{display:none !important}',
      '#cmd-pal{--cp-bg:#fff;--cp-border:#e5e7eb;--cp-text:#111827;--cp-muted:#6b7280;--cp-sub:#f9fafb;--cp-hover:#eff6ff;--cp-cat:#6b7280;--cp-bdrop:rgba(0,0,0,.48)}',
      'html[data-theme="dark"] #cmd-pal{--cp-bg:#0f172a;--cp-border:#1e3a5f;--cp-text:#e2e8f0;--cp-muted:#94a3b8;--cp-sub:#071224;--cp-hover:rgba(37,99,235,.18);--cp-cat:#94a3b8;--cp-bdrop:rgba(0,0,0,.72)}',
      '@media(prefers-color-scheme:dark){html:not([data-theme="light"]) #cmd-pal{--cp-bg:#0f172a;--cp-border:#1e3a5f;--cp-text:#e2e8f0;--cp-muted:#94a3b8;--cp-sub:#071224;--cp-hover:rgba(37,99,235,.18);--cp-cat:#94a3b8;--cp-bdrop:rgba(0,0,0,.72)}}',
      '#cmd-bg{position:absolute;inset:0;background:var(--cp-bdrop);backdrop-filter:blur(4px)}',
      '#cmd-box{position:relative;width:min(620px,92vw);background:var(--cp-bg);border-radius:16px;box-shadow:0 28px 70px rgba(0,0,0,.22);overflow:hidden;border:1px solid var(--cp-border)}',
      '#cmd-sr{display:flex;align-items:center;gap:.65rem;padding:.9rem 1rem;border-bottom:1px solid var(--cp-border)}',
      '#cmd-q{flex:1;border:none;outline:none;font-size:1rem;background:transparent;color:var(--cp-text);font-family:inherit}',
      '#cmd-q::placeholder{color:var(--cp-cat)}',
      '#cmd-esk{font-size:.7rem;padding:.18rem .42rem;border:1px solid var(--cp-border);border-radius:4px;color:var(--cp-cat);background:var(--cp-sub);font-family:inherit;white-space:nowrap;cursor:pointer}',
      '#cmd-list{margin:0;padding:.3rem 0;list-style:none;max-height:min(380px,52vh);overflow-y:auto}',
      '#cmd-list:empty::after{content:"No results";display:block;padding:.9rem 1.1rem;color:var(--cp-cat);font-size:.88rem}',
      '.cpcat{padding:.5rem 1.1rem .15rem;font-size:.7rem;font-weight:760;letter-spacing:.1em;text-transform:uppercase;color:var(--cp-cat)}',
      '.cpi{display:flex;align-items:center;gap:.65rem;padding:.58rem 1.1rem;cursor:pointer;user-select:none}',
      '.cpi:hover,.cpi[aria-selected="true"]{background:var(--cp-hover)}',
      '.cpi-lbl{font-size:.93rem;font-weight:560;color:var(--cp-text)}',
      '.cpi-desc{font-size:.8rem;color:var(--cp-muted);margin-left:auto;white-space:nowrap;padding-left:.5rem}',
      '#cmd-foot{display:flex;gap:1rem;padding:.5rem 1rem;border-top:1px solid var(--cp-border);background:var(--cp-sub)}',
      '#cmd-foot span{font-size:.73rem;color:var(--cp-cat);display:flex;align-items:center;gap:.25rem}',
      '@media(hover:none) and (pointer:coarse){#cmd-foot{display:none}}',
      '#cmd-foot kbd{font-size:.69rem;padding:.12rem .32rem;border:1px solid var(--cp-border);border-radius:4px;background:var(--cp-bg);font-family:inherit}'
    ].join('\n'));

    var pal = document.createElement('div');
    pal.id = 'cmd-pal'; pal.setAttribute('role','dialog'); pal.setAttribute('aria-modal','true'); pal.setAttribute('aria-label','Command palette'); pal.hidden = true;
    pal.innerHTML =
      '<div id="cmd-bg"></div>' +
      '<div id="cmd-box">' +
        '<div id="cmd-sr">' +
          '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' +
          '<input id="cmd-q" type="text" placeholder="Search commands, navigate, jump to section…" autocomplete="off" spellcheck="false" aria-label="Command search" aria-controls="cmd-list" aria-autocomplete="list" />' +
          '<kbd id="cmd-esk">ESC</kbd>' +
        '</div>' +
        '<ul id="cmd-list" role="listbox" aria-label="Commands"></ul>' +
        '<div id="cmd-foot" aria-hidden="true"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>' +
      '</div>';
    document.body.appendChild(pal);
    var bg = document.getElementById('cmd-bg'), inp = document.getElementById('cmd-q'), lst = document.getElementById('cmd-list');

    var NAV = PAGES.filter(function(p){ return p.file !== page; }).map(function(p){ return {cat:'Navigate', label:p.label, desc:p.desc, url:siteLink(p.file)}; });
    var ACT = [
      {cat:'Action', label:'Print / Save PDF', desc: page === 'resume-atlas.html' ? 'Open print dialog' : 'Opens Atlas, the print-ready resume', action:'print'},
      {cat:'Action', label:'Copy email address', desc:'bsc_pro@protonmail.com', action:'copy-email'},
      {cat:'Action', label:'View GitHub', desc:'NorthwoodsCode', url:'https://github.com/NorthwoodsCode', ext:true},
      {cat:'Action', label:'View LinkedIn', desc:'brandon-c-it-industry', url:'https://www.linkedin.com/in/brandon-c-it-industry', ext:true}
    ];
    var JMP = [], seen = {};
    Array.prototype.forEach.call(document.querySelectorAll('h2[id], section[id] > h2, section[id] > .card > h2, main h2'), function(h){
      var target = h.id ? h.id : (h.closest('section[id]') ? h.closest('section[id]').id : '');
      var label = (h.textContent || '').replace(/\s+/g,' ').trim();
      if(!target || !label || seen[target]) return;
      seen[target] = true;
      JMP.push({cat:'Jump to', label: label.slice(0, 48), anchor:'#' + target});
    });
    var CMDS = NAV.concat(ACT).concat(JMP);
    var activeIdx = -1, prevFocus = null, filtered = [];
    function flt(q){ q = (q||'').toLowerCase().trim(); if(!q) return CMDS.slice(); return CMDS.filter(function(c){ return (c.label+' '+(c.desc||'')+' '+(c.cat||'')).toLowerCase().indexOf(q) > -1; }); }
    function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function mkItem(c, i){
      var li = document.createElement('li'); li.className = 'cpi'; li.setAttribute('role','option'); li.id = 'cpi-' + i; li.setAttribute('aria-selected','false');
      li.innerHTML = '<span class="cpi-lbl">' + esc(c.label) + '</span>' + (c.desc ? '<span class="cpi-desc">' + esc(c.desc) + '</span>' : '');
      li.addEventListener('mousedown', function(e){ e.preventDefault(); execute(c); });
      return li;
    }
    function render(q){
      filtered = flt(q); lst.innerHTML = ''; var lastCat = null;
      filtered.forEach(function(c, i){
        if(c.cat !== lastCat){ var h = document.createElement('li'); h.className = 'cpcat'; h.setAttribute('role','presentation'); h.textContent = c.cat; lst.appendChild(h); lastCat = c.cat; }
        lst.appendChild(mkItem(c, i));
      });
      setActive(-1);
    }
    function setActive(i){
      activeIdx = i;
      var items = lst.querySelectorAll('.cpi');
      items.forEach(function(el, j){ el.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
      if(i >= 0 && items[i]) items[i].scrollIntoView({block:'nearest'});
      if(i >= 0) inp.setAttribute('aria-activedescendant', 'cpi-' + i); else inp.removeAttribute('aria-activedescendant');
    }
    function execute(cmd){
      closePal();
      if(cmd.action === 'print'){
        if(page === 'resume-atlas.html') window.print(); else location.href = siteLink('resume-atlas.html?print=1');
        return;
      }
      if(cmd.action === 'copy-email'){
        copyText('bsc_pro@protonmail.com').then(function(ok){ toast(ok ? 'Email copied' : COPY_FAIL); });
        return;
      }
      if(cmd.anchor){ var el = document.querySelector(cmd.anchor); if(el){ el.scrollIntoView({behavior: reduced ? 'auto' : 'smooth', block:'start'}); if(el.tabIndex < 0) el.tabIndex = -1; el.focus({preventScroll:true}); } return; }
      if(cmd.url){ if(cmd.ext){ window.open(cmd.url, '_blank', 'noopener'); } else { location.href = cmd.url; } }
    }
    function openPal(){ prevFocus = document.activeElement; pal.hidden = false; render(''); inp.value = ''; setTimeout(function(){ inp.focus(); }, 30); document.body.style.overflow = 'hidden'; }
    function closePal(){ pal.hidden = true; document.body.style.overflow = ''; if(prevFocus && prevFocus.focus) prevFocus.focus(); }
    inp.addEventListener('input', function(){ render(inp.value); });
    inp.addEventListener('keydown', function(e){
      var items = lst.querySelectorAll('.cpi');
      if(e.key === 'ArrowDown'){ e.preventDefault(); setActive(Math.min(activeIdx + 1, items.length - 1)); }
      else if(e.key === 'ArrowUp'){ e.preventDefault(); setActive(Math.max(activeIdx - 1, 0)); }
      else if(e.key === 'Enter'){ if(activeIdx >= 0 && filtered[activeIdx]) execute(filtered[activeIdx]); else if(filtered[0]) execute(filtered[0]); }
      else if(e.key === 'Escape'){ closePal(); }
      else if(e.key === 'Tab'){ e.preventDefault(); } // the dialog is modal: Tab must not escape it
    });
    bg.addEventListener('mousedown', closePal);
    document.getElementById('cmd-esk').addEventListener('click', closePal);
    document.addEventListener('keydown', function(e){
      if((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); if(pal.hidden) openPal(); else closePal(); }
      else if(!pal.hidden && e.key === 'Escape') closePal();
    });
    window.bscOpenPalette = openPal;
  })();

  /* ── shared "Resume modes" dock (pages without their own) ─────── */
  // A fixed <details> in the bottom-right corner listing all six pages, with
  // aria-current on the one you are reading. The panel is absolutely positioned
  // above the pill (a <details> always renders its <summary> first, so flex
  // order cannot do this), so the pill stays put under the thumb when it opens;
  // the panel is capped to the dynamic viewport height and scrolls internally,
  // so it never spills off a phone (even in landscape). A tap
  // outside or Escape closes it, and a last "Search pages" button opens the
  // command palette, since touch devices have no Ctrl/Cmd+K.
  // Clicking a link remembers it as bsc_last_resume_mode for the Switchboard.
  (function dock(){
    if(document.querySelector('.bsc-dock')) return; // Home ships its own dock markup
    addStyle('bsc-dock-style', [
      '.bsc-dock{--dk-bg:#fff;--dk-fg:#111827;--dk-muted:#6b7280;--dk-border:#e5e7eb;--dk-hover:#eff6ff;--dk-accent:#2563eb;position:fixed;right:16px;bottom:16px;z-index:9990;padding:0;margin:0;border:0;background:none;pointer-events:none;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}',
      'html[data-theme="dark"] .bsc-dock{--dk-bg:#0f172a;--dk-fg:#e2e8f0;--dk-muted:#94a3b8;--dk-border:#1e3a5f;--dk-hover:rgba(37,99,235,.18);--dk-accent:#8ab4ff}',
      '@media(prefers-color-scheme:dark){html:not([data-theme="light"]) .bsc-dock{--dk-bg:#0f172a;--dk-fg:#e2e8f0;--dk-muted:#94a3b8;--dk-border:#1e3a5f;--dk-hover:rgba(37,99,235,.18);--dk-accent:#8ab4ff}}',
      '.bsc-dock summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:.4rem;padding:.6rem .95rem;border-radius:999px;background:var(--dk-bg);color:var(--dk-fg);border:1px solid var(--dk-border);box-shadow:0 10px 30px rgba(0,0,0,.25);font-weight:700;font-size:.9rem;pointer-events:auto}',
      '.bsc-dock summary::-webkit-details-marker{display:none}',
      '.bsc-dock summary:focus-visible{outline:3px solid var(--dk-accent);outline-offset:3px}',
      '.bsc-dock-panel{position:absolute;right:0;bottom:calc(100% + 10px);width:min(300px,calc(100vw - 32px));box-sizing:border-box;pointer-events:auto;background:var(--dk-bg);color:var(--dk-fg);border:1px solid var(--dk-border);border-radius:16px;box-shadow:0 18px 50px rgba(0,0,0,.3);padding:12px;max-height:calc(100vh - 96px);max-height:calc(100dvh - 96px);overflow:auto;overscroll-behavior:contain}',
      '.bsc-dock-kicker{font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--dk-muted);margin:2px 4px 8px}',
      '.bsc-dock-grid{display:grid;gap:6px}',
      '.bsc-dock-link{display:grid;gap:1px;padding:8px 10px;border-radius:10px;text-decoration:none;color:var(--dk-fg);border:1px solid transparent}',
      '.bsc-dock-link:hover,.bsc-dock-link:focus-visible{background:var(--dk-hover);border-color:var(--dk-border);outline:none}',
      'button.bsc-dock-link{width:100%;min-height:40px;font:inherit;text-align:left;background:none;cursor:pointer;margin-top:6px;border-top-color:var(--dk-border)}',
      '.bsc-dock-link strong{font-size:.9rem}',
      '.bsc-dock-link span{font-size:.76rem;color:var(--dk-muted)}',
      '.bsc-dock-link[aria-current="page"]{border-color:var(--dk-accent)}',
      '.bsc-dock-link[aria-current="page"] strong::after{content:" • you are here";font-weight:500;color:var(--dk-muted);font-size:.74rem}',
      // phones: tighter rows so the six pages plus Search fit under the viewport
      '@media(max-width:520px){.bsc-dock-panel{padding:8px}.bsc-dock-kicker{margin:0 4px 4px}.bsc-dock-grid{gap:2px}.bsc-dock-link{padding:6px 10px}.bsc-dock-link strong{font-size:.86rem}.bsc-dock-link span{font-size:.75rem;line-height:1.25}.bsc-dock-kicker{font-size:.75rem}button.bsc-dock-link{margin-top:2px}}'
    ].join('\n'));
    var d = document.createElement('details'); d.className = 'bsc-dock';
    d.innerHTML = '<summary aria-label="Open resume modes menu">Resume modes</summary>' +
      '<div class="bsc-dock-panel"><div class="bsc-dock-kicker">Same story, five views</div><div class="bsc-dock-grid">' +
      PAGES.map(function(p){
        return '<a class="bsc-dock-link" href="' + siteLink(p.file) + '" data-page="' + p.file + '"' + (p.file === page ? ' aria-current="page"' : '') + '><strong>' + p.label + '</strong><span>' + p.desc + '</span></a>';
      }).join('') + '<button type="button" class="bsc-dock-link" id="bsc-dock-search"><strong>Search pages</strong><span>Jump to any page or action</span></button></div></div>';
    document.body.appendChild(d);
    d.querySelectorAll('.bsc-dock-link').forEach(function(link){
      link.addEventListener('click', function(){ store.set('bsc_last_resume_mode', link.getAttribute('data-page')); });
    });
    // bind lazily: the palette may not exist yet when the dock is injected
    d.querySelector('#bsc-dock-search').addEventListener('click', function(){
      d.open = false;
      if(window.bscOpenPalette) window.bscOpenPalette();
    });
    // Escape closes the dock, unless the palette is open on top of it (then the
    // palette's own handler takes that keypress, so one Escape closes one layer).
    document.addEventListener('keydown', function(e){
      var pal = document.getElementById('cmd-pal');
      if(e.key === 'Escape' && d.open && !(pal && !pal.hidden)) d.open = false;
    });
    document.addEventListener('pointerdown', function(e){ if(d.open && !d.contains(e.target)) d.open = false; });
    document.addEventListener('click', function(e){ if(d.open && !d.contains(e.target)) d.open = false; });
  })();

  /* ── optional desktop effects (only where Home's FX panel exists) ── */
  // All three effects are set up only on Home and only when motion is welcome.
  // Each handler still checks fxOn() on every event, so toggling in the panel
  // takes effect immediately without reloading.
  if(window.BSC_FX && !reduced && !plain){
    /* cursor glow (desktop only) */
    if(window.matchMedia('(pointer:fine)').matches){
      var glow = document.getElementById('cursor-glow');
      if(!glow){
        glow = document.createElement('div');
        glow.id = 'cursor-glow';
        glow.setAttribute('aria-hidden','true');
        document.body.appendChild(glow);
      }
      addStyle('bsc-glow-style', [
        '#cursor-glow{position:fixed;pointer-events:none;width:320px;height:320px;border-radius:50%;',
        'background:radial-gradient(circle,color-mix(in srgb,var(--accent) 16%,transparent) 0%,transparent 65%);',
        'transform:translate(-50%,-50%);z-index:2;transition:left .1s linear,top .1s linear,opacity .4s ease,background .3s ease;',
        'mix-blend-mode:screen;opacity:0;will-change:left,top}',
        'html[data-theme="light"] #cursor-glow{display:none}'
      ].join(''));
      var glowActive = false;
      document.addEventListener('mousemove', function(e){
        if(!fxOn('spotlight')){ if(glowActive){ glowActive = false; glow.style.opacity = '0'; } return; }
        glow.style.left = e.clientX + 'px'; glow.style.top = e.clientY + 'px';
        if(!glowActive){ glowActive = true; glow.style.opacity = '1'; }
      }, {passive:true});
      document.addEventListener('mouseleave', function(){ glowActive = false; glow.style.opacity = '0'; });
      window.addEventListener('bsc-fx-change', function(ev){
        if(ev.detail && ev.detail.key === 'spotlight' && !ev.detail.value){ glowActive = false; glow.style.opacity = '0'; }
      });
    }

    /* card 3D tilt */
    (function tilt(){
      var hasFinePointer = window.matchMedia('(pointer:fine)').matches;
      var hasCoarsePointer = window.matchMedia('(pointer:coarse)').matches;
      document.querySelectorAll('.card').forEach(function(card){
        if(card.querySelector('input,textarea,select')) return; // never tilt a form
        if(hasFinePointer){
          card.addEventListener('mousemove', function(e){
            if(!fxOn('tilt')) return;
            var r = card.getBoundingClientRect();
            var x = (e.clientX - r.left) / r.width - 0.5;
            var y = (e.clientY - r.top) / r.height - 0.5;
            card.style.willChange = 'transform';
            card.style.transform = 'perspective(700px) rotateX(' + (-y*7) + 'deg) rotateY(' + (x*7) + 'deg) translateZ(6px)';
            card.style.boxShadow = 'var(--shadow-hover,var(--shadow))';
            card.style.transition = 'transform .12s ease,box-shadow .18s ease';
          });
          card.addEventListener('mouseleave', function(){ card.style.transform = ''; card.style.boxShadow = ''; card.style.willChange = ''; });
        }
        if(hasCoarsePointer){
          card.addEventListener('touchmove', function(e){
            if(!fxOn('tilt')) return;
            var t = e.touches[0]; var r = card.getBoundingClientRect();
            var x = (t.clientX - r.left) / r.width - 0.5; var y = (t.clientY - r.top) / r.height - 0.5;
            card.style.willChange = 'transform';
            card.style.transform = 'perspective(700px) rotateX(' + (-y*4) + 'deg) rotateY(' + (x*4) + 'deg)';
            card.style.transition = 'none';
          }, {passive:true});
          card.addEventListener('touchend', function(){ card.style.transform = ''; card.style.willChange = ''; card.style.transition = 'transform .28s ease'; });
        }
      });
      window.addEventListener('bsc-fx-change', function(ev){
        if(ev.detail && ev.detail.key === 'tilt' && !ev.detail.value){
          document.querySelectorAll('.card').forEach(function(card){ card.style.transform = ''; card.style.boxShadow = ''; card.style.willChange = ''; });
        }
      });
    })();

    /* click sparks. Listening to click only: a tap fires click as well, and a
       touchend listener would also spark at the end of every scroll gesture. */
    (function sparks(){
      function spawnSparks(cx, cy){
        var count = 10, color = accentColor();
        for(var i = 0; i < count; i++){
          (function(idx){
            var angle = (Math.PI*2*idx/count) + (Math.random()-0.5)*0.9;
            var speed = 48 + Math.random()*72;
            var vx = Math.cos(angle)*speed, vy = Math.sin(angle)*speed - 28;
            var size = 3 + Math.random()*3;
            var s = document.createElement('div');
            s.setAttribute('aria-hidden','true');
            s.style.cssText = 'position:fixed;pointer-events:none;z-index:9999;width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:' + color + ';left:' + cx + 'px;top:' + cy + 'px;opacity:1';
            document.body.appendChild(s);
            var start = null, dur = 520 + Math.random()*280;
            (function frame(ts){
              if(!start) start = ts;
              var p = (ts - start) / dur;
              if(p >= 1){ s.remove(); return; }
              s.style.left = (cx + vx*p) + 'px';
              s.style.top = (cy + vy*p + 145*p*p) + 'px';
              s.style.opacity = Math.max(0, 1 - p*p);
              requestAnimationFrame(frame);
            })(performance.now());
          })(i);
        }
      }
      document.addEventListener('click', function(e){
        if(!fxOn('sparks')) return;
        if(e.target.closest('a,button,input,select,textarea,summary,label')) return;
        spawnSparks(e.clientX, e.clientY);
      });
    })();
  }

  /* ── per-case "copy share link" buttons ─────────────────────── */
  // Proof Hub's case studies carry ids like case-payment-portal. Each gets a
  // small button that copies the short, unfurl-friendly URL /case/<slug>/
  // (a stub page generated at deploy by scripts/gen_cases.py).
  (function caseShareLinks(){
    var cases = document.querySelectorAll('[id^="case-"]');
    if(!cases.length) return;
    var origin = location.origin + location.pathname.replace(/[^/]*$/, '');
    cases.forEach(function(el){
      var slug = el.id.replace(/^case-/, '');
      if(!slug) return;
      var summary = el.querySelector('summary');
      var host = summary || el;
      if(host.querySelector('[data-case-share]')) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-case-share','');
      btn.setAttribute('aria-label','Copy shareable link to this case study');
      btn.title = 'Copy shareable link';
      btn.textContent = '🔗';
      btn.style.cssText = 'margin-left:8px;font-size:.85em;padding:2px 8px;border:1px solid currentColor;border-radius:6px;background:transparent;color:inherit;opacity:.6;cursor:pointer;vertical-align:middle;line-height:1.4';
      btn.addEventListener('mouseenter', function(){ btn.style.opacity = '1'; });
      btn.addEventListener('mouseleave', function(){ btn.style.opacity = '.6'; });
      btn.addEventListener('focus', function(){ btn.style.opacity = '1'; });
      btn.addEventListener('blur', function(){ btn.style.opacity = '.6'; });
      btn.addEventListener('click', function(ev){
        ev.preventDefault(); ev.stopPropagation();
        copyText(origin + 'case/' + slug + '/').then(function(ok){
          if(ok){ var prev = btn.textContent; btn.textContent = '✓'; setTimeout(function(){ btn.textContent = prev; }, 1400); }
          toast(ok ? 'Link copied' : COPY_FAIL);
        });
      });
      host.appendChild(btn);
    });
  })();

  /* ── ?for=<company> personalization ─────────────────────────── */
  // Pretty links such as /for/stripe land on 404.html, which rewrites them to
  // /?for=stripe. Here the slug is looked up in companies.json; a known company
  // pins an atmosphere, pre-ticks matching focus chips on pages that have them,
  // and shows a "Tailored for …" badge. Unknown slugs do nothing, silently.
  (function personalize(){
    var slug = (params.get('for') || '').toLowerCase().replace(/[^a-z0-9-]/g, '');
    if(!slug) return;
    fetch('companies.json', {cache:'force-cache'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(data){
        if(!data || !data[slug]) return;
        var co = data[slug];
        if(co.atmosphere) html.setAttribute('data-atmosphere', co.atmosphere);
        if(co.focus){
          var values = co.focus.split(',').map(function(s){ return s.trim(); }).filter(Boolean);
          var changed = false;
          document.querySelectorAll('input[type="checkbox"][value]').forEach(function(inp){
            if(values.indexOf(inp.value) !== -1 && !inp.checked){
              inp.checked = true;
              inp.dispatchEvent(new Event('change', {bubbles:true}));
              changed = true;
            }
          });
          // Signal reads ?focus= on load; mirror it into the URL only there.
          if(!changed && page === 'resume-signal.html'){
            var u = new URLSearchParams(location.search);
            u.set('focus', co.focus);
            history.replaceState(null, '', location.pathname + '?' + u.toString());
          }
        }
        if(document.querySelector('[data-for-badge]')) return;
        var b = document.createElement('div');
        b.setAttribute('data-for-badge','');
        b.setAttribute('role','status');
        b.setAttribute('aria-label','Personalized view for ' + co.name);
        b.style.cssText = [
          'position:fixed','left:14px','bottom:14px','z-index:20',
          'display:inline-flex','align-items:center','gap:8px',
          'padding:7px 13px','border-radius:999px',
          'background:color-mix(in srgb,var(--accent,#2563eb) 14%,#111827)',
          'border:1px solid color-mix(in srgb,var(--accent,#2563eb) 45%,transparent)',
          'color:#f9fafb','font-size:.78rem','font-weight:600',
          'box-shadow:0 6px 20px rgba(0,0,0,.22)','letter-spacing:.02em','line-height:1'
        ].join(';');
        var dot = document.createElement('span');
        dot.setAttribute('aria-hidden','true');
        dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:var(--accent,#2563eb);box-shadow:0 0 8px var(--accent,#2563eb)';
        b.appendChild(dot);
        var txt = document.createElement('span');
        txt.textContent = 'Tailored for ' + co.name;
        b.appendChild(txt);
        document.body.appendChild(b);
      })
      .catch(function(){ /* never break the page over a missing file */ });
  })();

  /* ── stack-disclosure line (Home footer only; never printed) ──── */
  // A one-line "how it is built" note for technical readers. It is appended by
  // script so the resume pages themselves stay free of meta commentary.
  (function injectStack(){
    if(!isHome || document.querySelector('[data-bsc-stack]')) return;
    var footer = document.querySelector('footer');
    if(!footer) return;
    var p = document.createElement('p');
    p.setAttribute('data-bsc-stack','');
    p.className = 'mono';
    p.style.cssText = 'margin:10px 0 0;font-size:.78rem;opacity:.62;line-height:1.55';
    p.innerHTML = 'Built with HTML + vanilla JS + CSS · Hosted on GitHub Pages · CI: GitHub Actions + headless Chrome · ' +
      '<a href="https://github.com/NorthwoodsCode/resume" rel="noopener" target="_blank" style="color:inherit;text-decoration:underline;text-underline-offset:3px">Source</a>.';
    footer.appendChild(p);
  })();
})();
