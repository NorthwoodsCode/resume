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
    10. Evidence: receipts behind every headline number ([data-receipt]) and
        the decisions / incidents / answers lists ([data-evidence-list]), both
        read from evidence.json.

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
        // While Home's Embers backdrop runs it exposes window.bscEmbers; a spray on its
        // canvas replaces the DOM sparks. Looked up per click, so it follows effect switches.
        if(window.bscEmbers && typeof window.bscEmbers.poke === 'function'){
          try{ if(window.bscEmbers.poke(e.clientX, e.clientY)) return; }catch(_e){}
        }
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

  /* ── cross-page view transitions ─────────────────────────────── */
  // Same-origin navigations crossfade instead of flashing white, and the floating
  // dock keeps its own transition name so it stays put while the page fades.
  // Browsers without cross-document view transitions ignore all of this. Reduced
  // motion switches the opt-in off, and plain mode (the calm mode) skips it in JS.
  addStyle('bsc-vt-style',
    '@view-transition{navigation:auto}' +
    '::view-transition-old(root),::view-transition-new(root){animation-duration:220ms}' +
    '.bsc-dock{view-transition-name:bsc-dock}' +
    '@media(prefers-reduced-motion:reduce){@view-transition{navigation:none}}');
  ['pageswap','pagereveal'].forEach(function(name){
    window.addEventListener(name, function(e){
      if(plain && e && e.viewTransition && e.viewTransition.skipTransition){
        try { e.viewTransition.skipTransition(); } catch(err){}
      }
    });
  });

  /* ── mail subjects ───────────────────────────────────────────── */
  // A recruiter's message arrives already naming the role and the page (mode)
  // they came from. Links that carry their own query are left alone.
  (function mailSubjects(){
    var label = 'Resume';
    PAGES.forEach(function(p){ if(p.file === page) label = p.label; });
    var subject = encodeURIComponent('Senior Software Engineer — from your ' + label + ' page');
    var links = document.querySelectorAll('a[href^="mailto:"]');
    for(var i = 0; i < links.length; i++){
      var href = links[i].getAttribute('href');
      if(href.indexOf('?') === -1) links[i].setAttribute('href', href + '?subject=' + subject);
    }
  })();

  /* ── share ───────────────────────────────────────────────────── */
  // The native share sheet where the browser has one (phones), otherwise copy the
  // link and say so. Buttons are marked [data-bsc-share] (optionally with
  // data-bsc-share-url); the pages own the markup, this owns the behaviour.
  addStyle('bsc-share-style', '@media print{[data-bsc-share]{display:none !important}}');
  // The address worth passing on: the page itself, without the reader's own
  // ?plain=1 / ?sw=1 switches (a ?for= link is the personalised one, so it
  // stays), and without the hash except on Proof Hub, where #case-... links
  // are deep links to a case.
  function shareUrl(){
    try{
      var u = new URL(location.href);
      u.searchParams.delete('plain');
      u.searchParams.delete('sw');
      if(page !== 'proof-hub.html') u.hash = '';
      return u.href;
    }catch(e){
      return location.href.replace(/#.*$/, '');
    }
  }
  function bscShare(opts){
    opts = opts || {};
    var title = opts.title || document.title;
    var url = opts.url || shareUrl();
    var fallback = function(){
      return copyText(url).then(function(ok){
        toast(ok ? 'Link copied' : 'Copy failed, the address is: ' + url);
        return ok;
      });
    };
    if(navigator.share){
      var sharing;
      try{ sharing = navigator.share({title: title, url: url}); }catch(e){ return fallback(); }
      return Promise.resolve(sharing).then(function(){ return true; }, function(err){
        // AbortError means the reader closed the sheet: nothing to do. Any other
        // failure (not allowed, bad data) falls back to copying the link.
        if(err && err.name === 'AbortError') return false;
        return fallback();
      });
    }
    return fallback();
  }
  window.bscShare = bscShare;
  // Delegated, so buttons added later (or by other scripts) work too.
  document.addEventListener('click', function(e){
    var el = e.target && e.target.closest ? e.target.closest('[data-bsc-share]') : null;
    if(!el) return;
    e.preventDefault();
    bscShare({url: el.getAttribute('data-bsc-share-url') || undefined});
  });

  /* ── evidence: receipts behind the numbers, and the evidence lists ── */
  // evidence.json holds a receipt for every headline number (baseline, method,
  // where, confidence) plus, once written, the decisions, incidents and
  // screen-call answers shown on Proof Hub. Two hooks, both markup-driven:
  //   data-receipt="<id>"                       the element opens that receipt
  //   data-evidence-list="decisions|incidents|answers"   filled with cards
  // Entries still marked "draft": true render with a DRAFT badge here and are
  // removed before deploy by scripts/strip_drafts.py, so the live site never
  // shows unfinished content. scripts/check_evidence.py fails the build when a
  // page claims a receipt that does not exist.
  var evidencePromise = null;
  function loadEvidence(){
    if(!evidencePromise){
      evidencePromise = fetch('evidence.json')
        .then(function(r){ return r.ok ? r.json() : null; })
        .catch(function(){ return null; });
    }
    return evidencePromise;
  }
  window.bscEvidence = loadEvidence;
  function escapeHtml(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function draftBadge(entry){
    return entry && entry.draft === true ? ' <span class="bsc-draft" title="Author draft: removed from the published site until finished">DRAFT</span>' : '';
  }
  // Cards and the receipt panel share one small stylesheet. Colours are plain
  // values with a dark override, because each page names its own tokens.
  addStyle('bsc-evidence-style',
    '.bsc-receipt{cursor:help;text-decoration:underline dotted;text-decoration-thickness:2px;text-underline-offset:.16em;text-decoration-color:#2f64ff}' +
    'html[data-theme="dark"] .bsc-receipt{text-decoration-color:#86a6ff}' +
    '.bsc-receipt:hover,.bsc-receipt:focus-visible{text-decoration-style:solid;text-decoration-color:currentColor}' +
    '.bsc-receipt:focus-visible{outline:3px solid rgba(47,100,255,.6);outline-offset:3px;border-radius:4px}' +
    '.bsc-draft{display:inline-block;font:800 .75rem/1 system-ui,sans-serif;letter-spacing:.1em;padding:.22rem .45rem;border-radius:6px;background:#fde68a;color:#78350f;vertical-align:middle}' +
    '#bsc-receipt{position:fixed;inset:0;z-index:100001;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(5,9,20,.55);backdrop-filter:blur(6px)}' +
    '#bsc-receipt[hidden]{display:none}' +
    '.bsc-rc-card{position:relative;width:min(600px,100%);max-height:min(88vh,88dvh);overflow:auto;overscroll-behavior:contain;padding:22px 24px 20px;border-radius:20px;background:#fff;color:#0b1325;border:1px solid rgba(86,109,145,.25);box-shadow:0 30px 90px rgba(0,0,0,.4);font:1rem/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    'html[data-theme="dark"] .bsc-rc-card{background:#0f172a;color:#e5e7eb;border-color:rgba(203,220,255,.16)}' +
    '@media(prefers-color-scheme:dark){html[data-theme="auto"] .bsc-rc-card{background:#0f172a;color:#e5e7eb;border-color:rgba(203,220,255,.16)}}' +
    '.bsc-rc-kicker{display:flex;align-items:center;justify-content:space-between;gap:10px;font:800 .72rem/1 system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;opacity:.7}' +
    '.bsc-rc-close{appearance:none;border:1px solid currentColor;background:transparent;color:inherit;border-radius:999px;width:36px;height:36px;font-size:1.1rem;cursor:pointer;opacity:.8}' +
    '.bsc-rc-close:hover,.bsc-rc-close:focus-visible{opacity:1}' +
    '.bsc-rc-head{margin:.65rem 0 .25rem;font-size:1.55rem;line-height:1.15;letter-spacing:-.02em;font-weight:850}' +
    '.bsc-rc-claim{margin:0 0 .9rem;font-size:1.02rem;opacity:.92}' +
    '.bsc-rc-conf{display:inline-flex;align-items:center;gap:.45rem;padding:.3rem .7rem;border-radius:999px;font:800 .72rem/1 system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase}' +
    '.bsc-rc-conf.measured{background:rgba(16,185,129,.16);color:#047857}.bsc-rc-conf.logged{background:rgba(37,99,235,.14);color:#1d4ed8}' +
    '.bsc-rc-conf.reported{background:rgba(245,158,11,.18);color:#92400e}.bsc-rc-conf.stated{background:rgba(139,92,246,.16);color:#5b21b6}.bsc-rc-conf.estimated{background:rgba(107,114,128,.18);color:#374151}' +
    'html[data-theme="dark"] .bsc-rc-conf.measured{color:#6ee7b7}html[data-theme="dark"] .bsc-rc-conf.logged{color:#93c5fd}html[data-theme="dark"] .bsc-rc-conf.reported{color:#fcd34d}html[data-theme="dark"] .bsc-rc-conf.stated{color:#d8b4fe}html[data-theme="dark"] .bsc-rc-conf.estimated{color:#d1d5db}' +
    '@media(prefers-color-scheme:dark){html[data-theme="auto"] .bsc-rc-conf.measured{color:#6ee7b7}html[data-theme="auto"] .bsc-rc-conf.logged{color:#93c5fd}html[data-theme="auto"] .bsc-rc-conf.reported{color:#fcd34d}html[data-theme="auto"] .bsc-rc-conf.stated{color:#d8b4fe}html[data-theme="auto"] .bsc-rc-conf.estimated{color:#d1d5db}html[data-theme="auto"] .bsc-receipt{text-decoration-color:#86a6ff}}' +
    '.bsc-rc-rows{margin:0;display:grid;grid-template-columns:minmax(96px,auto) 1fr;gap:.45rem 1rem;font-size:.94rem}' +
    '.bsc-rc-rows dt{margin:0;font-weight:800;opacity:.7}.bsc-rc-rows dd{margin:0}' +
    '.bsc-rc-rows dd.muted{opacity:.62;font-style:italic}' +
    '.bsc-rc-foot{margin:1rem 0 0;padding-top:.8rem;border-top:1px solid rgba(128,128,128,.25);font-size:.8rem;line-height:1.5;opacity:.72}' +
    '.bsc-rc-link{display:inline-block;margin-top:.9rem;font-weight:800;text-decoration:underline;text-underline-offset:.15em;color:inherit}' +
    '@media(max-width:560px){.bsc-rc-card{padding:18px 16px 16px;border-radius:16px}.bsc-rc-rows{grid-template-columns:1fr;gap:.15rem .5rem}.bsc-rc-rows dt{margin-top:.5rem}}' +
    '.bsc-ev-list{display:grid;gap:12px;margin:12px 0 0}' +
    '.bsc-ev-card{padding:14px 16px;border:1px solid rgba(128,128,128,.28);border-radius:14px;background:rgba(127,127,127,.06)}' +
    '.bsc-ev-card h3{margin:0 0 .5rem;font-size:1.02rem;line-height:1.3}' +
    '.bsc-ev-card p{margin:.3rem 0}.bsc-ev-card ul{margin:.2rem 0 .4rem;padding-left:1.2rem}' +
    '.bsc-ev-card .bsc-ev-k{font-weight:800;opacity:.75;margin-right:.35rem}' +
    '.bsc-ev-actions{display:flex;flex-wrap:wrap;gap:.5rem .9rem;margin-top:.6rem;font-size:.9rem}' +
    '.bsc-ev-actions button{appearance:none;border:1px solid currentColor;background:transparent;color:inherit;border-radius:999px;padding:.3rem .7rem;font:700 .82rem/1.2 system-ui,sans-serif;cursor:pointer;opacity:.85}' +
    '.bsc-ev-actions button:hover,.bsc-ev-actions button:focus-visible{opacity:1}' +
    '@media(max-width:640px),(hover:none) and (pointer:coarse){.bsc-ev-actions button,.bsc-rc-close{min-height:40px}.bsc-ev-actions button{min-width:40px}' +
    '.bsc-ev-actions a{display:inline-flex;align-items:center;min-height:40px}' +
    /* Receipt numbers sit inside sentences and tiles: pad the tap target without moving the line (negative margins cancel the padding). */
    '.bsc-receipt{display:inline-block;box-sizing:border-box;min-height:40px;padding:.55rem 0;margin:-.55rem 0}}' +
    '@media print{.bsc-receipt{text-decoration:none}#bsc-receipt,.bsc-ev-actions{display:none !important}}');

  /* receipts: any [data-receipt] opens the matching receipt in a panel */
  (function receipts(){
    var panel = null, lastFocus = null;
    var levelsFallback = {measured:'timed or counted directly', logged:'from logs or dashboards', reported:'a figure reported by others', estimated:'calculated from assumptions'};
    function build(){
      if(panel) return panel;
      panel = document.createElement('div');
      panel.id = 'bsc-receipt'; panel.hidden = true;
      panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
      panel.setAttribute('aria-labelledby', 'bsc-rc-title');
      panel.innerHTML = '<div class="bsc-rc-card" tabindex="-1"></div>';
      panel.addEventListener('click', function(e){ if(e.target === panel) close(); });
      document.addEventListener('keydown', function(e){
        if(panel.hidden) return;
        if(e.key === 'Escape'){ e.preventDefault(); close(); return; }
        if(e.key !== 'Tab') return;
        // Keep focus inside the dialog while it is open.
        var focusables = panel.querySelectorAll('button,[href],[tabindex]:not([tabindex="-1"])');
        if(!focusables.length) return;
        var first = focusables[0], last = focusables[focusables.length - 1];
        var inside = panel.contains(document.activeElement) && document.activeElement !== panel.firstChild;
        if(!inside){ e.preventDefault(); (e.shiftKey ? last : first).focus(); return; }
        if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
        else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
      });
      document.body.appendChild(panel);
      return panel;
    }
    function row(label, value, muted){
      if(value == null || value === '') return '';
      return '<dt>' + escapeHtml(label) + '</dt><dd' + (muted ? ' class="muted"' : '') + '>' + escapeHtml(value) + '</dd>';
    }
    function render(id, r, levels){
      var conf = String(r.confidence || 'estimated');
      var levelText = (levels && levels[conf]) || levelsFallback[conf] || '';
      var artifact = r.artifact && r.artifact.href
        ? '<dt>Artifact</dt><dd><a href="' + escapeHtml(r.artifact.href) + '" rel="noopener" target="_blank">' + escapeHtml(r.artifact.label || 'Open') + '</a></dd>'
        : '';
      var legend = [];
      var lv = levels || levelsFallback;
      for(var k in lv){ if(Object.prototype.hasOwnProperty.call(lv, k)) legend.push('<b>' + escapeHtml(k) + '</b> ' + escapeHtml(lv[k])); }
      return '<div class="bsc-rc-kicker"><span>Receipt · ' + escapeHtml(id) + '</span>' +
        '<button class="bsc-rc-close" type="button" aria-label="Close receipt">×</button></div>' +
        '<h2 class="bsc-rc-head" id="bsc-rc-title">' + escapeHtml(r.headline) + draftBadge(r) + '</h2>' +
        '<p class="bsc-rc-claim">' + escapeHtml(r.claim) + '</p>' +
        '<p><span class="bsc-rc-conf ' + escapeHtml(conf) + '">' + escapeHtml(conf) + '</span> <span style="font-size:.86rem;opacity:.8">' + escapeHtml(levelText) + '</span></p>' +
        '<dl class="bsc-rc-rows">' +
          row('Baseline', r.baseline) + row('Result', r.result) + row('Method', r.method || 'Not documented yet.', !r.method) +
          row('Where', r.where) + row('My role', r.role) + row('Caveat', r.confidence_note) + artifact +
        '</dl>' +
        (r.case ? '<a class="bsc-rc-link" href="' + escapeHtml(siteLink('proof-hub.html')) + '#case-' + escapeHtml(r.case) + '">Read the case study →</a>' : '') +
        '<p class="bsc-rc-foot">Confidence levels: ' + legend.join(' · ') + '.</p>';
    }
    function open(id, trigger){
      return loadEvidence().then(function(d){
        var r = d && d.receipts && d.receipts[id];
        if(!r){ toast('No receipt published for this number yet'); return false; }
        build();
        lastFocus = trigger || document.activeElement;
        var card = panel.firstChild;
        card.innerHTML = render(id, r, d.confidence_levels);
        card.querySelector('.bsc-rc-close').addEventListener('click', close);
        panel.hidden = false;
        document.documentElement.style.overflow = 'hidden';
        card.scrollTop = 0;
        card.querySelector('.bsc-rc-close').focus();
        return true;
      });
    }
    function close(){
      if(!panel || panel.hidden) return;
      panel.hidden = true;
      document.documentElement.style.overflow = '';
      if(lastFocus && lastFocus.focus){ try{ lastFocus.focus(); }catch(e){} }
    }
    function decorate(root){
      var els = (root || document).querySelectorAll('[data-receipt]:not(.bsc-receipt)');
      for(var i = 0; i < els.length; i++){
        var el = els[i];
        el.classList.add('bsc-receipt');
        if(!/^(button|a)$/i.test(el.tagName)){ el.setAttribute('role', 'button'); el.setAttribute('tabindex', '0'); }
        el.setAttribute('aria-haspopup', 'dialog');
        if(!el.getAttribute('title')) el.setAttribute('title', 'How this number was measured');
      }
      return els.length;
    }
    document.addEventListener('click', function(e){
      var el = e.target && e.target.closest ? e.target.closest('[data-receipt]') : null;
      if(!el) return;
      e.preventDefault();
      open(el.getAttribute('data-receipt'), el);
    });
    document.addEventListener('keydown', function(e){
      if(e.key !== 'Enter' && e.key !== ' ') return;
      var el = e.target && e.target.closest ? e.target.closest('[data-receipt]') : null;
      if(!el || /^(button|a)$/i.test(el.tagName)) return;
      e.preventDefault();
      open(el.getAttribute('data-receipt'), el);
    });
    decorate(document);
    window.bscReceipts = {open: open, close: close, decorate: decorate, data: loadEvidence};
  })();

  /* evidence lists: decisions, incidents and screen-call answers on Proof Hub */
  (function evidenceLists(){
    var hosts = document.querySelectorAll('[data-evidence-list]');
    if(!hosts.length) return;
    function caseLink(slug){
      return slug ? '<a href="' + escapeHtml(siteLink('proof-hub.html')) + '#case-' + escapeHtml(slug) + '">Case study →</a>' : '';
    }
    function field(label, value){
      return value ? '<p><span class="bsc-ev-k">' + escapeHtml(label) + '</span>' + escapeHtml(value) + '</p>' : '';
    }
    var renderers = {
      decisions: function(d){
        var opts = (d.options || []).map(function(o){ return '<li>' + escapeHtml(o) + '</li>'; }).join('');
        return '<article class="bsc-ev-card" id="decision-' + escapeHtml(d.id) + '">' +
          '<h3>' + escapeHtml(d.title) + draftBadge(d) + '</h3>' +
          field('Context', d.context) +
          (opts ? '<p><span class="bsc-ev-k">Options considered</span></p><ul>' + opts + '</ul>' : '') +
          field('Choice', d.choice) + field('What it cost', d.cost) + field('How it held up', d.verdict_later) +
          '<div class="bsc-ev-actions">' + caseLink(d.case) + '</div></article>';
      },
      incidents: function(i){
        return '<article class="bsc-ev-card" id="incident-' + escapeHtml(i.id) + '">' +
          '<h3>' + escapeHtml(i.year) + ' · ' + escapeHtml(i.system) + draftBadge(i) + '</h3>' +
          field('What happened', i.what) + field('Detected by', i.detected_by) + field('Impact', i.impact) +
          field('Fix', i.fix) + field('Guard added', i.guard) + '</article>';
      },
      answers: function(a){
        var refs = (a.evidence || []).map(function(ref){
          if(ref.indexOf('case:') === 0) return caseLink(ref.slice(5));
          return '<button type="button" data-receipt="' + escapeHtml(ref) + '">Receipt: ' + escapeHtml(ref) + '</button>';
        }).join('');
        return '<article class="bsc-ev-card" id="answer-' + escapeHtml(a.id) + '">' +
          '<h3>' + escapeHtml(a.q) + draftBadge(a) + '</h3><p>' + escapeHtml(a.a) + '</p>' +
          '<div class="bsc-ev-actions"><button type="button" data-bsc-copy-answer="' + escapeHtml(a.id) + '">Copy answer</button>' + refs + '</div></article>';
      }
    };
    function renderLists(d){
      for(var i = 0; i < hosts.length; i++){
        var host = hosts[i];
        var kind = host.getAttribute('data-evidence-list');
        var items = (d && d[kind]) || [];
        var section = host.closest('section') || host;
        if(!items.length || !renderers[kind]){
          // Nothing published yet: hide the section and any chip that points at it.
          section.hidden = true;
          if(section.id){
            var chips = document.querySelectorAll('a[href="#' + section.id + '"]');
            for(var c = 0; c < chips.length; c++){ chips[c].hidden = true; chips[c].style.display = 'none'; }
          }
          continue;
        }
        section.hidden = false;
        if(section.id){
          var shown = document.querySelectorAll('a[href="#' + section.id + '"]');
          for(var s2 = 0; s2 < shown.length; s2++){ shown[s2].hidden = false; shown[s2].style.display = ''; }
        }
        host.classList.add('bsc-ev-list');
        host.innerHTML = items.map(renderers[kind]).join('');
        if(window.bscReceipts) window.bscReceipts.decorate(host);
      }
      document.dispatchEvent(new CustomEvent('bsc-evidence-rendered'));
    }
    loadEvidence().then(renderLists);
    // Exposed for the test suite, which re-renders from an empty data set to
    // check that unfilled sections disappear.
    window.bscRenderEvidence = renderLists;
    document.addEventListener('click', function(e){
      var btn = e.target && e.target.closest ? e.target.closest('[data-bsc-copy-answer]') : null;
      if(!btn) return;
      var card = btn.closest('article');
      var q = card ? card.querySelector('h3').textContent.replace(/\s*DRAFT\s*$/, '').trim() : '';
      var a = card ? card.querySelector('p').textContent.trim() : '';
      copyText(q + '\n' + a).then(function(ok){ toast(ok ? 'Answer copied' : COPY_FAIL); });
    });
  })();

  /* Proof Hub: a job description pasted into Home's fit check carries over */
  (function carryJdToProofHub(){
    if(page !== 'proof-hub.html') return;
    var jd = document.getElementById('jd');
    if(!jd || jd.value) return;
    var text = null;
    try{ text = sessionStorage.getItem('bsc_fit_jd'); }catch(e){ text = null; }
    if(!text) return;
    try{ sessionStorage.removeItem('bsc_fit_jd'); }catch(e){}
    var tools = jd.closest('details');
    if(tools) tools.open = true;
    jd.value = text;
    jd.dispatchEvent(new Event('input', {bubbles:true}));
  })();

  /* ── offline + installable ───────────────────────────────────── */
  // sw.js caches the pages so the resume opens with no signal. Registered only
  // over https (GitHub Pages) or when the URL opts in with ?sw=1, so the local
  // test suite on http://localhost never gets a worker by default.
  (function registerWorker(){
    if(!('serviceWorker' in navigator)) return;
    if(location.protocol !== 'https:' && params.get('sw') !== '1') return;
    try {
      navigator.serviceWorker.register('sw.js').catch(function(){ /* optional feature */ });
    } catch(e){}
  })();
})();
