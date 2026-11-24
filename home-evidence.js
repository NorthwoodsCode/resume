/* home-evidence.js — Home only, loaded after shared-enhancements.js.

   Two things that make the first screen prove its claims instead of decorating them:

     1. Fit check. The reader pastes a job description; the posting's skills are
        detected, scored against the plain-text resume (resume-ats.txt, fetched
        once) and shown as strong matches, partial matches and, in the open, the
        skills the resume does not have. Everything runs in the browser; the
        text is never sent anywhere. Handing the posting on to Proof Hub uses
        sessionStorage, where shared-enhancements.js picks it up.

     2. Verified chip. tests-latest.json is written by the CI test run and
        published with each deploy; the chip shows the last run and a button
        executes a handful of checks live, in this browser, so the reader sees
        pass/fail on their own device rather than a badge image.

   Plain ES5-style code on purpose, like the rest of the site: no build step. */
(function(){
  'use strict';

  /* ── skills the fit check can recognise ──
     Each entry is a display name and a regex source; the boundary wrapper below
     stops "java" matching "javascript" and lets symbols like c# and .net match. */
  var SKILLS = [
    ['AWS', 'aws|amazon web services'], ['Lambda', 'lambda'], ['API Gateway', 'api gateway'],
    ['Step Functions', 'step functions?'], ['DynamoDB', 'dynamo ?db'], ['DocumentDB', 'document ?db'],
    ['S3', 's3'], ['SQS', 'sqs'], ['SNS', 'sns'], ['EventBridge', 'eventbridge|event bridge'], ['Kinesis', 'kinesis'],
    ['CloudWatch', 'cloudwatch'], ['IAM', 'iam'], ['Secrets Manager', 'secrets manager'], ['IoT Core', 'iot core|aws iot'],
    ['IoT', 'iot|internet of things'], ['MQTT', 'mqtt'], ['RDS', 'rds|aurora'], ['ECS / EKS', 'ecs|eks|fargate'],
    ['CloudFormation / CDK', 'cloudformation|cdk|aws sam'], ['Azure', 'azure'], ['GCP', 'gcp|google cloud'],
    ['Terraform', 'terraform'], ['Infrastructure as Code', 'infrastructure as code|iac'],
    ['Kubernetes', 'kubernetes|k8s'], ['Docker', 'docker|containeri[sz]ation'], ['Helm', 'helm'],
    ['CI/CD', 'ci\\/cd|ci cd|continuous (?:integration|delivery|deployment)'], ['GitHub Actions', 'github actions'],
    ['Jenkins', 'jenkins'], ['GitLab CI', 'gitlab'], ['Linux', 'linux'], ['Bash', 'bash|shell scripting'],
    ['Python', 'python'], ['TypeScript', 'typescript'], ['JavaScript', 'javascript|es6'], ['Node.js', 'node\\.?js|node(?=\\s*(?:,|/|and|or)\\s*(?:typescript|javascript|express|react|python|java))'],
    ['Java', 'java'], ['C#', 'c#'], ['.NET', '\\.net|dotnet'], ['Go', 'golang|go-?lang|go \\(golang\\)|go(?=\\s*(?:,|/|and|or)\\s*(?:rust|python|java|kotlin|scala|c\\+\\+|typescript|node|ruby))'], ['Rust', 'rust'], ['C++', 'c\\+\\+'],
    ['Kotlin', 'kotlin'], ['Scala', 'scala'], ['Ruby', 'ruby'], ['PHP', 'php'],
    ['SQL', 'sql'], ['SQL Server / T-SQL', 'sql server|t-sql|mssql'], ['PostgreSQL', 'postgres(?:ql)?'], ['MySQL', 'mysql'],
    ['MongoDB', 'mongo(?:db)?'], ['Redis', 'redis'], ['Elasticsearch', 'elasticsearch|opensearch'],
    ['Kafka', 'kafka'], ['Spark', 'apache spark|pyspark|spark (?:jobs?|sql|streaming)'], ['Airflow', 'airflow'], ['Snowflake', 'snowflake'], ['Databricks', 'databricks'],
    ['ETL', 'etl|elt|data pipelines?'], ['Data modelling', 'data model(?:l)?ing|schema design'],
    ['REST APIs', 'restful|rest(?:ful)? (?:apis?|endpoints?|services?)'], ['GraphQL', 'graphql'], ['gRPC', 'grpc'], ['OpenAPI / Swagger', 'openapi|swagger'],
    ['OAuth / OIDC', 'oauth|oidc|openid'], ['JWT', 'jwt'], ['Auth0', 'auth0'], ['Okta', 'okta'], ['SAML', 'saml'],
    ['WebSockets', 'websockets?'], ['React', 'react\\.?js|react native|react (?:hooks|components?|front-?end)|react(?=\\s*(?:,|/)\\s*(?:angular|vue|typescript|javascript|node|next))'], ['Angular', 'angular'], ['Vue', 'vue(?:\\.js)?'], ['Next.js', 'next\\.?js'],
    ['Microservices', 'microservices?'], ['Serverless', 'serverless'], ['Event-driven', 'event[- ]driven'],
    ['Distributed systems', 'distributed systems?'], ['Observability', 'observability|monitoring|alerting'],
    ['SLAs / SLOs', 'slas?|slos?|slis?'], ['On-call', 'on[- ]call|incident (?:response|management)|postmortems?|pagerduty'],
    ['Security', 'security[- ]first|security (?:best practices|reviews?|controls|engineering|-minded)|secure (?:coding|by default|design)|least privilege|threat model(?:l)?ing|security-minded'], ['Testing', 'unit test(?:s|ing)?|tdd|integration tests?'],
    ['Agile', 'agile|scrum|kanban'], ['Mentoring', 'mentor(?:ing|ship)?'], ['Documentation', 'documentation|technical writing|runbooks?'],
    ['Code review', 'code reviews?'], ['System design', 'system design|architecture'],
    ['Machine learning', 'machine learning|ml (?:models?|pipelines?|engineering)|mlops'], ['LLMs / GenAI', 'llms?|generative ai|genai|retrieval[- ]augmented|rag pipelines?|prompt engineering'],
    ['Payments / fintech', 'payments?|fintech'], ['Embedded / firmware', 'embedded (?:systems?|software|devices?|linux)|firmware']
  ].map(function(pair){
    return {name: pair[0], rx: new RegExp('(?:^|[^a-z0-9+#.])(?:' + pair[1] + ')(?=$|[^a-z0-9+#])', 'i')};
  });

  var corpusPromise = null;
  // resume-ats.txt is the one plain-text source of the bullets; role headers are
  // the lines like "Milwaukee Tool - Senior Software Engineer | ... | 2025-Present".
  function loadCorpus(){
    if(!corpusPromise){
      corpusPromise = fetch('resume-ats.txt').then(function(r){ if(!r.ok) throw new Error('resume text ' + r.status); return r.text(); })
        .then(function(txt){
          if(!/EXPERIENCE/.test(txt)) throw new Error('resume text incomplete');
          var bullets = [], role = '', section = '';
          txt.split(/\r?\n/).forEach(function(line){
            var t = line.trim();
            if(!t) return;
            if(/^[A-Z][A-Z \/&]+$/.test(t)){ section = t; role = ''; return; }
            if(t.indexOf('- ') === 0){
              if(/EXPERIENCE/.test(section)) bullets.push({role: role, text: t.slice(2)});
              return;
            }
            if(/EXPERIENCE/.test(section)){
              // "Company - Title | Team | Years | Place" -> "Company · Years"
              var parts = t.split('|').map(function(s){ return s.trim(); });
              var company = parts[0].split(' - ')[0].trim();
              var years = '';
              parts.forEach(function(p){ if(/\d{4}/.test(p)) years = years || p; });
              role = company + (years ? ' · ' + years : '');
            }
          });
          return {text: txt, bullets: bullets};
        })
        .catch(function(err){ corpusPromise = null; throw err; });   // try again next time, never score against nothing
    }
    return corpusPromise;
  }

  function detect(jd){
    var found = [];
    SKILLS.forEach(function(s){ if(s.rx.test(jd)) found.push(s); });
    // "5+ years", "3-5 years of experience", "at least 4 years building": the lower number, and only
    // with an experience cue nearby, so "a 20 year old company" is not read as a requirement.
    var years = null, m = /(\d{1,2})(?:\s*(?:-|–|to)\s*\d{1,2})?\s*\+?\s*(?:or more\s+)?(?:years?|yrs?)[^.\n]{0,40}?\b(?:experience|exp|of|in|with|building|working|professional|hands-on)\b/i.exec(jd);
    if(m) years = parseInt(m[1], 10);
    return {skills: found, yearsAsked: years};
  }

  function analyse(jd, corpus, facts){
    var det = detect(jd);
    var have = [], gaps = [];
    det.skills.forEach(function(s){ (s.rx.test(corpus.text) ? have : gaps).push(s); });
    var scored = corpus.bullets.map(function(b){
      var hits = have.filter(function(s){ return s.rx.test(b.text); });
      return {bullet: b, hits: hits, score: hits.length};
    }).filter(function(x){ return x.score > 0; }).sort(function(a, b){ return b.score - a.score; });
    var since = facts && facts.career_since ? parseInt(facts.career_since, 10) : 2016;
    var yearsHave = new Date().getFullYear() - since;
    return {
      skillsFound: det.skills, have: have, gaps: gaps,
      strong: scored.filter(function(x){ return x.score >= 2; }).slice(0, 6),
      partial: scored.filter(function(x){ return x.score === 1; }).slice(0, 4),
      yearsAsked: det.yearsAsked, yearsHave: yearsHave, since: since
    };
  }

  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function clip(s, n){ return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : s; }

  function renderFit(res){
    function item(x){
      var q = encodeURIComponent(x.hits[0].name.split(' /')[0]);
      return '<li><span class="fit-role">' + esc(x.bullet.role) + '</span> ' + esc(clip(x.bullet.text, 170)) +
        ' <span class="fit-hits">' + x.hits.map(function(h){ return esc(h.name); }).join(' · ') + '</span>' +
        ' <a href="resume-signal.html?q=' + q + '" aria-label="Open ' + esc(x.hits[0].name) + ' bullets in Signal">Signal →</a></li>';
    }
    var html = '';
    if(!res.skillsFound.length){
      return '<p class="fit-empty">No recognisable skills in that text yet. Paste the requirements section of the posting.</p>';
    }
    html += '<h2 class="sr-only">Fit check results</h2>';
    html += '<p class="fit-sum"><b>' + res.skillsFound.length + '</b> skills named in the posting: <b>' + res.have.length + '</b> on this resume, <b>' + res.gaps.length + '</b> not.' +
      (res.yearsAsked ? ' The posting asks for ' + res.yearsAsked + '+ years; I have worked in software since ' + res.since + '.' : '') + '</p>';
    html += '<div class="fit-grid">';
    html += '<section class="fit-col"><h3>Strong matches</h3>' + (res.strong.length ? '<ul>' + res.strong.map(item).join('') + '</ul>' : '<p class="fit-empty">No bullet matches two or more of the posting\'s skills.</p>') + '</section>';
    html += '<section class="fit-col"><h3>Also relevant</h3>' + (res.partial.length ? '<ul>' + res.partial.map(item).join('') + '</ul>' : '<p class="fit-empty">Nothing further.</p>') + '</section>';
    html += '<section class="fit-col fit-gaps"><h3>Not on this resume</h3>' + (res.gaps.length
      ? '<p>' + res.gaps.map(function(s){ return '<span class="fit-chip">' + esc(s.name) + '</span>'; }).join(' ') + '</p><p class="fit-note">Honest gaps. If one is essential, ask me how I would ramp.</p>'
      : '<p class="fit-note">Every skill the posting names appears on this resume.</p>') + '</section>';
    html += '</div>';
    html += '<p class="fit-actions"><a class="btn lift small" id="fitToProof" href="proof-hub.html#turbo">Open these matches in Proof Hub →</a> <a class="btn lift small" href="resume-signal.html">Tailored view</a></p>';
    return html;
  }

  (function fitCheck(){
    var form = document.getElementById('fitCheck');
    if(!form) return;
    var ta = document.getElementById('fitJd'), out = document.getElementById('fitOut'),
        status = document.getElementById('fitStatus'), runBtn = document.getElementById('fitRun'),
        clearBtn = document.getElementById('fitClear');
    var idle = 'Runs in your browser. Nothing is sent anywhere.';
    var facts = null;
    if(window.bscEvidence) window.bscEvidence().then(function(d){ facts = d && d.facts; });

    var runId = 0;
    function run(text, opts){
      opts = opts || {};
      text = String(text || '');
      var mine = ++runId;
      if(text.trim().length < 20){
        if(!opts.silent){ out.hidden = true; status.textContent = text.trim() ? 'Paste a few more lines of the posting.' : idle; }
        return Promise.resolve(null);
      }
      if(!opts.silent) status.textContent = 'Reading the posting…';
      return loadCorpus().then(function(corpus){
        var res = analyse(text, corpus, facts);
        // A later run or a Clear makes this result stale: do not paint it.
        if(!opts.silent && mine === runId && ta.value === text){
          out.innerHTML = renderFit(res);
          out.hidden = false;
          status.textContent = res.skillsFound.length
            ? res.skillsFound.length + ' skills named, ' + res.have.length + ' on this resume, ' + res.gaps.length + ' not. ' + idle
            : idle;
          var toProof = document.getElementById('fitToProof');
          if(toProof) toProof.addEventListener('click', function(){
            try{ sessionStorage.setItem('bsc_fit_jd', text); }catch(e){}
          });
        }
        return res;
      }, function(){
        if(!opts.silent && mine === runId){ out.hidden = true; status.textContent = 'Could not load the resume text just now. Try again in a moment.'; }
        return null;
      });
    }
    var timer = null;
    ta.addEventListener('input', function(){
      clearTimeout(timer);
      if(ta.value.trim().length >= 80) timer = setTimeout(function(){ run(ta.value); }, 500);
    });
    ta.addEventListener('keydown', function(e){
      if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); run(ta.value); }
    });
    // The button is type=button and the form never submits (a submit would reload Home and lose the text).
    form.addEventListener('submit', function(e){ e.preventDefault(); run(ta.value); });
    runBtn.addEventListener('click', function(){ run(ta.value); ta.focus(); });
    if(clearBtn) clearBtn.addEventListener('click', function(){ clearTimeout(timer); runId++; ta.value = ''; out.hidden = true; out.innerHTML = ''; status.textContent = idle; ta.focus(); });
    window.bscFit = {run: run, detect: detect, skills: SKILLS.length};
  })();

  /* ── facts strip: keep "N years" current from evidence.json ── */
  (function yearsFact(){
    var el = document.querySelector('[data-fact="years"]');
    if(!el || !window.bscEvidence) return;
    window.bscEvidence().then(function(d){
      var since = d && d.facts && parseInt(d.facts.career_since, 10);
      if(!since) return;
      var n = new Date().getFullYear() - since;
      if(n >= 1) el.textContent = n + ' years';
      var from = d.facts.available_from, avail = document.querySelector('[data-fact="available"]');
      if(from && avail) avail.textContent = 'Available from ' + from;
    });
  })();

  /* ── verified chip + live checks ── */
  (function verified(){
    var text = document.getElementById('verifiedText'), list = document.getElementById('verifiedList'),
        meta = document.getElementById('verifiedMeta'), liveBtn = document.getElementById('liveRun'),
        live = document.getElementById('liveChecks'), summary = document.getElementById('verifiedSummary');
    if(!text) return;
    fetch('tests-latest.json', {cache: 'no-cache'}).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
      .then(function(rep){
        if(!rep || !rep.tests || !rep.tests.length){
          summary.textContent = 'These checks cover this site, not my work: every deploy runs the UI test suite in headless Chrome, and the report from the last run is published here with the site.';
          return;
        }
        var passed = rep.tests.filter(function(t){ return t.ok; }).length;
        text.textContent = 'Site self-test: ' + passed + '/' + rep.tests.length + ' passed in real Chrome · ' + (rep.date || '').slice(0, 10);
        summary.textContent = 'These checks cover this site, not my work: the UI test suite ran in headless Chrome before this version was published.';
        meta.textContent = (rep.commit ? 'commit ' + String(rep.commit).slice(0, 7) : '') + (rep.browser ? ' · ' + rep.browser : '') + (rep.duration_ms ? ' · ' + Math.round(rep.duration_ms / 1000) + ' s' : '');
        list.innerHTML = rep.tests.map(function(t){
          return '<li class="' + (t.ok ? 'ok' : 'bad') + '"><span>' + (t.ok ? '✓' : '✗') + '</span> ' + esc(t.name) + (t.ms != null ? ' <small>' + Math.round(t.ms) + ' ms</small>' : '') + '</li>';
        }).join('');
      });

    function fetchOk(url){ return fetch(url, {cache: 'no-cache'}).then(function(r){ if(!r.ok) throw new Error(url + ' ' + r.status); return r; }); }
    var CHECKS = [
      ['Every underlined number on this page has a receipt', function(){
        return window.bscEvidence().then(function(d){
          var ids = Array.prototype.map.call(document.querySelectorAll('[data-receipt]'), function(e){ return e.getAttribute('data-receipt'); });
          if(!d || !ids.length) throw new Error('no evidence or no receipts on page');
          var missing = ids.filter(function(id){ return !d.receipts[id]; });
          if(missing.length) throw new Error('missing ' + missing.join(', '));
          return ids.length + ' receipts';
        });
      }],
      ['Structured data (JSON-LD) parses and names Brandon S. Clark', function(){
        var s = document.querySelector('script[type="application/ld+json"]');
        var j = JSON.parse(s.textContent);
        if(!/Brandon S\. Clark/.test(j.name || (j.mainEntity && j.mainEntity.name) || '')) throw new Error('name missing');
        return 'ok';
      }],
      ['Fit check finds a strong match for "Terraform, AWS Lambda, Python"', function(){
        return window.bscFit.run('Senior backend engineer with 5+ years. Terraform, AWS Lambda, Python, API Gateway, Step Functions. Kubernetes a plus.', {silent: true})
          .then(function(res){ if(!res || !res.strong.length) throw new Error('no strong match'); return res.strong.length + ' strong, gaps: ' + res.gaps.map(function(g){ return g.name; }).join(', '); });
      }],
      ['Web app manifest loads with icons', function(){
        return fetchOk('site.webmanifest').then(function(r){ return r.json(); }).then(function(m){ if(!m.icons || !m.icons.length) throw new Error('no icons'); return m.icons.length + ' icons'; });
      }],
      ['vCard downloads as a valid card', function(){
        return fetchOk('brandon-clark.vcf').then(function(r){ return r.text(); }).then(function(t){ if(t.indexOf('BEGIN:VCARD') !== 0) throw new Error('not a vCard'); return 'ok'; });
      }],
      ['Plain-text resume is reachable', function(){
        return fetchOk('resume-ats.txt').then(function(r){ return r.text(); }).then(function(t){ if(t.indexOf('EXPERIENCE') < 0) throw new Error('unexpected content'); return Math.round(t.length / 1024) + ' KB'; });
      }],
      ['No horizontal overflow at this viewport', function(){
        var w = document.documentElement.scrollWidth, v = window.innerWidth;
        if(w > v + 1) throw new Error(w + ' > ' + v); return v + ' px';
      }]
    ];
    function runLive(){
      if(!live) return Promise.resolve([]);
      live.innerHTML = '';
      var results = [];
      var chain = Promise.resolve();
      CHECKS.forEach(function(c){
        chain = chain.then(function(){
          var t0 = performance.now();
          return Promise.resolve().then(c[1]).then(function(detail){ return {name: c[0], ok: true, detail: String(detail), ms: performance.now() - t0}; },
            function(err){ return {name: c[0], ok: false, detail: String(err && err.message || err), ms: performance.now() - t0}; })
            .then(function(r){
              results.push(r);
              var li = document.createElement('li');
              li.className = r.ok ? 'ok' : 'bad';
              li.innerHTML = '<span>' + (r.ok ? '✓' : '✗') + '</span> ' + esc(r.name) + ' <small>' + esc(r.detail) + ' · ' + Math.round(r.ms) + ' ms</small>';
              live.appendChild(li);
            });
        });
      });
      return chain.then(function(){
        var ok = results.filter(function(r){ return r.ok; }).length;
        var li = document.createElement('li');
        li.className = 'sum';
        li.textContent = ok + ' of ' + results.length + ' passed on your device just now.';
        live.appendChild(li);
        return results;
      });
    }
    if(liveBtn) liveBtn.addEventListener('click', function(){ liveBtn.disabled = true; runLive().then(function(){ liveBtn.disabled = false; }); });
    window.bscLiveChecks = runLive;
  })();
})();
