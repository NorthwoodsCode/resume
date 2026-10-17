/* shared-enhancements.js — cursor glow, card tilt, click sparks, touch support */
(function(){
  'use strict';
  var html = document.documentElement;
  var params = new URLSearchParams(location.search);
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var plain = html.classList.contains('plain') || params.get('plain') === '1';

  function fxOn(key){
    // Default-on when no FX system is present (e.g. on sub-pages without the panel).
    return !window.BSC_FX || window.BSC_FX.get(key);
  }

  function accentColor(){
    return getComputedStyle(html).getPropertyValue('--accent').trim() || '#86a6ff';
  }

  /* ── cursor glow (desktop only) ──────────────────────────────── */
  if(!reduced && !plain && window.matchMedia('(pointer:fine)').matches){
    var glow = document.getElementById('cursor-glow');
    if(!glow){
      glow = document.createElement('div');
      glow.id = 'cursor-glow';
      glow.setAttribute('aria-hidden','true');
      document.body.appendChild(glow);
    }
    if(!document.getElementById('bsc-glow-style')){
      var st = document.createElement('style');
      st.id = 'bsc-glow-style';
      st.textContent = [
        '#cursor-glow{',
          'position:fixed;pointer-events:none;',
          'width:320px;height:320px;border-radius:50%;',
          'background:radial-gradient(circle,color-mix(in srgb,var(--accent) 16%,transparent) 0%,transparent 65%);',
          'transform:translate(-50%,-50%);',
          'z-index:2;',
          'transition:left .1s linear,top .1s linear,opacity .4s ease,background .3s ease;',
          'mix-blend-mode:screen;opacity:0;will-change:left,top;',
        '}',
        'html[data-theme="light"] #cursor-glow{display:none}',
      ].join('');
      document.head.appendChild(st);
    }
    var glowActive = false;
    document.addEventListener('mousemove',function(e){
      if(!fxOn('spotlight')){
        if(glowActive){ glowActive = false; glow.style.opacity = '0'; }
        return;
      }
      glow.style.left = e.clientX+'px';
      glow.style.top  = e.clientY+'px';
      if(!glowActive){ glowActive=true; glow.style.opacity='1'; }
    },{passive:true});
    document.addEventListener('mouseleave',function(){ glowActive=false; glow.style.opacity='0'; });
    // Hide immediately when the user toggles spotlight off via the FX panel
    window.addEventListener('bsc-fx-change', function(ev){
      if(ev.detail && ev.detail.key === 'spotlight' && !ev.detail.value){
        glowActive = false;
        glow.style.opacity = '0';
      }
    });
  }

  /* ── card 3D tilt ────────────────────────────────────────────── */
  if(!reduced){
    var hasFinePointer = window.matchMedia('(pointer:fine)').matches;
    var hasCoarsePointer = window.matchMedia('(pointer:coarse)').matches;

    document.querySelectorAll('.card').forEach(function(card){
      if(hasFinePointer){
        card.addEventListener('mousemove',function(e){
          if(!fxOn('tilt')) return;
          var r = card.getBoundingClientRect();
          var x = (e.clientX - r.left) / r.width  - 0.5;
          var y = (e.clientY - r.top)  / r.height - 0.5;
          card.style.willChange  = 'transform';
          card.style.transform   = 'perspective(700px) rotateX('+(-y*7)+'deg) rotateY('+(x*7)+'deg) translateZ(6px)';
          card.style.boxShadow   = 'var(--shadow-hover,var(--shadow))';
          card.style.transition  = 'transform .12s ease,box-shadow .18s ease';
        });
        card.addEventListener('mouseleave',function(){
          card.style.transform  = '';
          card.style.boxShadow  = '';
          card.style.willChange = '';
        });
      }
      if(hasCoarsePointer){
        card.addEventListener('touchmove',function(e){
          if(!fxOn('tilt')) return;
          var t = e.touches[0];
          var r = card.getBoundingClientRect();
          var x = (t.clientX - r.left) / r.width  - 0.5;
          var y = (t.clientY - r.top)  / r.height - 0.5;
          card.style.willChange  = 'transform';
          card.style.transform   = 'perspective(700px) rotateX('+(-y*4)+'deg) rotateY('+(x*4)+'deg)';
          card.style.transition  = 'none';
        },{passive:true});
        card.addEventListener('touchend',function(){
          card.style.transform   = '';
          card.style.willChange  = '';
          card.style.transition  = 'transform .28s ease';
        });
      }
    });
    // Snap all cards back when tilt is turned off mid-hover
    window.addEventListener('bsc-fx-change', function(ev){
      if(ev.detail && ev.detail.key === 'tilt' && !ev.detail.value){
        document.querySelectorAll('.card').forEach(function(card){
          card.style.transform = '';
          card.style.boxShadow = '';
          card.style.willChange = '';
        });
      }
    });
  }

  /* ── per-case "copy share link" buttons ─────────────────────── */
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
      btn.setAttribute('aria-label','Copy shareable link to '+slug+' case');
      btn.title = 'Copy shareable link';
      btn.textContent = '🔗';
      btn.style.cssText = [
        'margin-left:8px','font-size:.85em','padding:1px 8px',
        'border:1px solid currentColor','border-radius:6px',
        'background:transparent','color:inherit','opacity:.5',
        'cursor:pointer','vertical-align:middle','line-height:1.4'
      ].join(';');
      btn.addEventListener('mouseenter', function(){ btn.style.opacity = '1'; });
      btn.addEventListener('mouseleave', function(){ btn.style.opacity = '.5'; });
      btn.addEventListener('focus',      function(){ btn.style.opacity = '1'; });
      btn.addEventListener('blur',       function(){ btn.style.opacity = '.5'; });
      btn.addEventListener('click', function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        var url = origin + 'case/' + slug + '/';
        var done = function(){
          var prev = btn.textContent;
          btn.textContent = '✓';
          setTimeout(function(){ btn.textContent = prev; }, 1400);
          var toast = document.getElementById('toast');
          if(toast){ toast.textContent = 'Link copied'; toast.classList.add('show'); setTimeout(function(){ toast.classList.remove('show'); }, 1600); }
        };
        if(navigator.clipboard && navigator.clipboard.writeText){
          navigator.clipboard.writeText(url).then(done, function(){ fallback(); });
        } else { fallback(); }
        function fallback(){
          var ta = document.createElement('textarea');
          ta.value = url;
          ta.style.position = 'fixed';
          ta.style.left = '-9999px';
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); done(); } catch(e){}
          document.body.removeChild(ta);
        }
      });
      host.appendChild(btn);
    });
  })();

  /* ── ?for=<company> personalization ─────────────────────────── */
  (function personalize(){
    var slug = (params.get('for') || '').toLowerCase().replace(/[^a-z0-9-]/g,'');
    if(!slug) return;
    fetch('companies.json', {cache:'force-cache'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(data){
        if(!data || !data[slug]) return;
        var co = data[slug];

        // 1. Pin atmosphere (existing CSS-var system)
        if(co.atmosphere){
          html.setAttribute('data-atmosphere', co.atmosphere);
        }

        // 2. Apply focus chips (resume-signal mechanism: checkboxes with [value])
        if(co.focus){
          var values = co.focus.split(',').map(function(s){return s.trim();}).filter(Boolean);
          var changed = false;
          document.querySelectorAll('input[type="checkbox"][value]').forEach(function(inp){
            if(values.indexOf(inp.value) !== -1 && !inp.checked){
              inp.checked = true;
              inp.dispatchEvent(new Event('change', {bubbles:true}));
              changed = true;
            }
          });
          // Some pages init filters from URL only; nudge them by also pushing ?focus=
          if(!changed){
            var u = new URLSearchParams(location.search);
            u.set('focus', co.focus);
            history.replaceState(null, '', location.pathname + '?' + u.toString());
          }
        }

        // 3. "Tailored for <Co>" badge — fixed top-right, accessible
        if(document.querySelector('[data-for-badge]')) return;
        var b = document.createElement('div');
        b.setAttribute('data-for-badge','');
        b.setAttribute('role','status');
        b.setAttribute('aria-label','Personalized view for ' + co.name);
        b.style.cssText = [
          'position:fixed','top:14px','right:14px','z-index:20',
          'display:inline-flex','align-items:center','gap:8px',
          'padding:7px 13px','border-radius:999px',
          'background:color-mix(in srgb,var(--accent) 14%,transparent)',
          'border:1px solid color-mix(in srgb,var(--accent) 45%,transparent)',
          'color:var(--fg,#fff)','font-size:.78rem','font-weight:600',
          'box-shadow:0 6px 20px rgba(0,0,0,.22)',
          'letter-spacing:.02em','line-height:1'
        ].join(';');
        var dot = document.createElement('span');
        dot.setAttribute('aria-hidden','true');
        dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent)';
        b.appendChild(dot);
        var txt = document.createElement('span');
        txt.textContent = 'Tailored for ' + co.name;
        b.appendChild(txt);
        document.body.appendChild(b);
      })
      .catch(function(){ /* silent — never break the page over a missing file */ });
  })();

  /* ── stack-disclosure line in footer ────────────────────────── */
  (function injectStack(){
    if(document.querySelector('[data-bsc-stack]')) return;
    var p = document.createElement('p');
    p.setAttribute('data-bsc-stack','');
    p.className = 'mono';
    p.style.cssText = 'margin:10px 0 0;font-size:.78rem;opacity:.62;line-height:1.55';
    p.innerHTML = 'Built with HTML + vanilla JS + CSS · FX by Three.js / Vanta · '+
                  'OG art via Pillow · Hosted on GitHub Pages · '+
                  'CI: GitHub Actions + headless Chrome · '+
                  '<a href="https://github.com/NorthwoodsCode/resume" rel="noopener" target="_blank" style="color:inherit;text-decoration:underline;text-underline-offset:3px">Zero build, zero deps</a>.';
    var footer = document.querySelector('footer');
    if(footer){
      footer.appendChild(p);
    } else {
      var f = document.createElement('footer');
      f.style.cssText = 'margin:48px auto 0;padding:24px 16px;text-align:center;max-width:960px';
      f.appendChild(p);
      (document.querySelector('main') || document.body).appendChild(f);
    }
  })();

  /* ── click / tap sparks ──────────────────────────────────────── */
  if(!reduced && !plain){
    function spawnSparks(cx,cy){
      var count = 10;
      var color = accentColor();
      for(var i=0;i<count;i++){
        (function(idx){
          var angle = (Math.PI*2*idx/count)+(Math.random()-0.5)*0.9;
          var speed = 48+Math.random()*72;
          var vx = Math.cos(angle)*speed;
          var vy = Math.sin(angle)*speed-28;
          var size = 3+Math.random()*3;
          var s = document.createElement('div');
          s.setAttribute('aria-hidden','true');
          s.style.cssText = [
            'position:fixed','pointer-events:none','z-index:9999',
            'width:'+size+'px','height:'+size+'px',
            'border-radius:50%','background:'+color,
            'left:'+cx+'px','top:'+cy+'px','opacity:1'
          ].join(';');
          document.body.appendChild(s);
          var start=null, dur=520+Math.random()*280;
          (function frame(ts){
            if(!start) start=ts;
            var p=(ts-start)/dur;
            if(p>=1){s.remove();return;}
            s.style.left=(cx+vx*p)+'px';
            s.style.top =(cy+vy*p+145*p*p)+'px';
            s.style.opacity=Math.max(0,1-p*p);
            requestAnimationFrame(frame);
          })(performance.now());
        })(i);
      }
    }

    document.addEventListener('click',function(e){
      if(!fxOn('sparks')) return;
      if(e.target.closest('a,button,input,select,textarea,summary,label')) return;
      spawnSparks(e.clientX,e.clientY);
    });

    document.addEventListener('touchend',function(e){
      if(!fxOn('sparks')) return;
      if(e.target.closest('a,button,input,select,textarea,summary,label')) return;
      var t = e.changedTouches[0];
      spawnSparks(t.clientX,t.clientY);
    },{passive:true});
  }

})();
