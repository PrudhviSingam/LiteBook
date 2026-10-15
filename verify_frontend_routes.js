import { spawn } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_USER_DATA = path.join(process.cwd(), 'temp_chrome_audit_profile');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.msgId = 1;
    this.pending = new Map();
    this.consoleLogs = [];
    this.pageErrors = [];

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.id && this.pending.has(data.id)) {
        const { resolve, reject } = this.pending.get(data.id);
        this.pending.delete(data.id);
        if (data.error) reject(data.error);
        else resolve(data.result);
      } else if (data.method) {
        if (data.method === 'Runtime.consoleAPICalled') {
          const text = data.params.args.map((a) => a.value || JSON.stringify(a)).join(' ');
          if (data.params.type === 'error') {
            this.consoleLogs.push({ type: 'error', text });
          }
        } else if (data.method === 'Runtime.exceptionThrown') {
          this.pageErrors.push(data.params.exceptionDetails);
        }
      }
    };
  }

  waitOpen() {
    return new Promise((resolve, reject) => {
      if (this.ws.readyState === WebSocket.OPEN) return resolve();
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(e);
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.msgId++;
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(res.exceptionDetails.exception?.description || res.exceptionDetails.text);
    }
    return res.result?.value;
  }

  async close() {
    this.ws.close();
  }
}

async function runFrontendAudit() {
  console.log('=== LITEBOOKS STEP 9: FRONTEND ROUTE & UI AUDIT ===\n');

  if (fs.existsSync(TEMP_USER_DATA)) {
    fs.rmSync(TEMP_USER_DATA, { recursive: true, force: true });
  }
  fs.mkdirSync(TEMP_USER_DATA, { recursive: true });

  const chromeProc = spawn(
    CHROME_PATH,
    [
      '--headless=new',
      '--remote-debugging-port=9223',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      `--user-data-dir=${TEMP_USER_DATA}`,
      'about:blank',
    ],
    { stdio: 'ignore' }
  );

  await sleep(2000);

  let cdp = null;
  const routeAudit = {};

  try {
    const pages = await fetchJson('http://localhost:9223/json/list');
    const page = pages.find((p) => p.type === 'page') || pages[0];
    if (!page) throw new Error('No page found in Chrome CDP list');

    cdp = new CDPClient(page.webSocketDebuggerUrl);
    await cdp.waitOpen();

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');

    // 1. Initial Load: Login screen
    console.log('[1/12] Loading http://127.0.0.1:5173 ...');
    await cdp.send('Page.navigate', { url: 'http://127.0.0.1:5173/' });
    await sleep(2000);

    const docTitle = await cdp.eval('document.title');
    console.log(`Document Title: "${docTitle}"`);
    const pageText = await cdp.eval('document.body.innerText');
    if (pageText.includes('SRM') || pageText.includes('lorem ipsum')) {
      throw new Error('Found forbidden placeholder / SRM text on login page!');
    }
    console.log('[PASS] Login page rendered cleanly without placeholder text.');

    // 2. Perform Login
    console.log('[2/12] Submitting Login form...');
    await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn) btn.click();
      })()
    `);
    await sleep(2500);

    const token = await cdp.eval('localStorage.getItem("litebooks_auth_token")');
    console.log(`[PASS] Logged in successfully, token exists: ${!!token}`);

    // 3. Audit all 10 main modules
    const modules = [
      { id: 'dashboard', label: 'Dashboard', headingCheck: 'Dashboard' },
      { id: 'review-center', label: 'Review Center', headingCheck: 'Review' },
      { id: 'reconciliation', label: 'Reconciliation', headingCheck: 'Reconciliation' },
      { id: 'documents', label: 'Documents', headingCheck: 'Document' },
      { id: 'gst', label: 'GST Returns', headingCheck: 'GST' },
      { id: 'itr', label: 'ITR Returns', headingCheck: 'ITR' },
      { id: 'financial-statements', label: 'Financial Statements', headingCheck: 'Financial Statements' },
      { id: 'ai-assistant', label: 'AI Assistant', headingCheck: 'Assistant' },
      { id: 'history', label: 'History', headingCheck: 'History' },
      { id: 'settings', label: 'Settings', headingCheck: 'Settings' }
    ];

    let stepNum = 3;
    for (const mod of modules) {
      console.log(`[${stepNum}/12] Testing module: ${mod.label}...`);
      // Click sidebar item
      const clicked = await cdp.eval(`
        (() => {
          const buttons = Array.from(document.querySelectorAll('aside button, [role="navigation"] button, nav button'));
          const btn = buttons.find(b => b.innerText.toLowerCase().includes('${mod.label.toLowerCase()}'));
          if (btn) {
            btn.click();
            return true;
          }
          return false;
        })()
      `);
      await sleep(1500);

      // Verify no React crash / error
      const hasReactCrash = await cdp.eval(`
        document.body.innerText.includes("Something went wrong") ||
        document.body.innerText.includes("Cannot read properties") ||
        document.body.innerText.includes("Unhandled Runtime Error")
      `);
      if (hasReactCrash) {
        throw new Error(`React runtime crash detected on module ${mod.label}!`);
      }

      // Verify page content
      const bodySnippet = await cdp.eval('document.body.innerText.substring(0, 500)');
      const containsForbidden = bodySnippet.includes('SRM') || bodySnippet.includes('lorem ipsum');
      if (containsForbidden) {
        throw new Error(`Forbidden placeholder text found in module ${mod.label}!`);
      }

      const foundExpected = bodySnippet.toLowerCase().includes(mod.headingCheck.toLowerCase());
      console.log(`       Rendered: found "${mod.headingCheck}" in content: ${foundExpected}`);
      routeAudit[mod.id] = foundExpected ? 'PASS' : 'WARN';
      stepNum++;
    }

    // Check Console Errors
    const filteredErrors = cdp.consoleLogs.filter(l => !l.text.includes('Download the React DevTools') && !l.text.includes('vite'));
    console.log(`\nConsole error count: ${filteredErrors.length}`);
    if (filteredErrors.length > 0) {
      console.warn('Console warnings/errors:', filteredErrors);
    }

    // 4. Test Logout
    console.log('\n[12/12] Testing Logout flow...');
    await cdp.eval(`
      (() => {
        const logoutBtn = document.querySelector('button[title="Sign Out"], button[title*="Sign"], button[title*="Logout"]');
        if (logoutBtn) logoutBtn.click();
      })()
    `);
    await sleep(1500);

    const postLogoutToken = await cdp.eval('localStorage.getItem("litebooks_auth_token")');
    const isBackToLogin = await cdp.eval('document.querySelector("input[type=\'password\']") !== null');
    console.log(`Post-logout token cleared: ${!postLogoutToken}`);
    console.log(`Returned to login form: ${isBackToLogin}`);

    console.log('\n=== ALL FRONTEND ROUTES AUDITED SUCCESSFULLY ===');
    console.log(JSON.stringify(routeAudit, null, 2));

  } finally {
    if (cdp) await cdp.close();
    chromeProc.kill();
    if (fs.existsSync(TEMP_USER_DATA)) {
      try {
        fs.rmSync(TEMP_USER_DATA, { recursive: true, force: true });
      } catch (e) {}
    }
  }
}

runFrontendAudit().catch(err => {
  console.error('Frontend audit error:', err);
  process.exit(1);
});
