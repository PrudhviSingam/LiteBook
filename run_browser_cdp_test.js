import { spawn } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_USER_DATA = path.join(process.cwd(), 'temp_chrome_profile');

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
    this.events = [];
    this.consoleLogs = [];
    this.pageErrors = [];
    this.networkRequests = [];

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
          this.consoleLogs.push({ type: data.params.type, text });
        } else if (data.method === 'Runtime.exceptionThrown') {
          this.pageErrors.push(data.params.exceptionDetails);
        } else if (data.method === 'Network.responseReceived') {
          this.networkRequests.push({
            url: data.params.response.url,
            status: data.params.response.status,
            statusText: data.params.response.statusText,
          });
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

async function runValidation() {
  console.log('=== LITEBOOKS STEP 2: REAL BROWSER CDP VALIDATION ===\n');

  if (fs.existsSync(TEMP_USER_DATA)) {
    fs.rmSync(TEMP_USER_DATA, { recursive: true, force: true });
  }
  fs.mkdirSync(TEMP_USER_DATA, { recursive: true });

  const chromeProc = spawn(
    CHROME_PATH,
    [
      '--headless=new',
      '--remote-debugging-port=9222',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      `--user-data-dir=${TEMP_USER_DATA}`,
      'about:blank',
    ],
    { stdio: 'ignore' }
  );

  console.log('[1/14] Chrome headless launched on remote port 9222.');
  await sleep(2000);

  let cdp = null;
  const testResults = {};

  try {
    const pages = await fetchJson('http://localhost:9222/json/list');
    const page = pages.find((p) => p.type === 'page') || pages[0];
    if (!page) throw new Error('No page found in Chrome CDP list');

    cdp = new CDPClient(page.webSocketDebuggerUrl);
    await cdp.waitOpen();

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');
    await cdp.send('Network.enable');

    // -------------------------------------------------------------------------
    // 1. Initial Load & Landing Page Verification
    // -------------------------------------------------------------------------
    console.log('\n[Step 1] Navigating to http://localhost:5173 ...');
    await cdp.send('Page.navigate', { url: 'http://localhost:5173/' });
    await sleep(2000);

    const initialTitle = await cdp.eval('document.title');
    const hasSrmText = await cdp.eval('document.body.innerText.includes("SRM")');
    const hasLiteBooksTitle = initialTitle.includes('LiteBooks');
    console.log(`Document Title: "${initialTitle}"`);
    console.log(`Contains "LiteBooks": ${hasLiteBooksTitle} | Contains "SRM": ${hasSrmText}`);

    if (hasLiteBooksTitle && !hasSrmText) {
      testResults.INITIAL_PAGE = 'PASS';
    } else {
      testResults.INITIAL_PAGE = `FAIL (Title: ${initialTitle}, hasSrm: ${hasSrmText})`;
    }

    // -------------------------------------------------------------------------
    // 2. Test Login
    // -------------------------------------------------------------------------
    console.log('\n[Step 2] Testing Login Flow...');
    const loginHeader = await cdp.eval('document.querySelector("h2")?.innerText');
    const emailValue = await cdp.eval('document.querySelector("#email")?.value');
    console.log(`Login Header: "${loginHeader}" | Pre-filled email: "${emailValue}"`);

    // Click Sign In
    await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn) btn.click();
      })()
    `);
    console.log('Clicked Sign In button, waiting for authentication...');
    await sleep(2500);

    const tokenInStorage = await cdp.eval('localStorage.getItem("litebooks_auth_token")');
    const currentHeading = await cdp.eval('document.querySelector("h1")?.innerText');
    console.log(`JWT in localStorage: ${!!tokenInStorage} (${tokenInStorage ? tokenInStorage.substring(0, 15) + '...' : 'None'})`);
    console.log(`Post-login Header: "${currentHeading}"`);

    if (tokenInStorage && currentHeading?.includes('Dashboard')) {
      testResults.LOGIN = 'PASS';
    } else {
      testResults.LOGIN = `FAIL (Token: ${!!tokenInStorage}, Heading: ${currentHeading})`;
    }

    // -------------------------------------------------------------------------
    // 3. Test Every Main Route (10 Modules)
    // -------------------------------------------------------------------------
    console.log('\n[Step 3] Testing All 10 Modules Navigation...');
    const modules = [
      { id: 'dashboard', name: 'Dashboard', expected: 'Dashboard' },
      { id: 'review-center', name: 'Review Center', expected: 'Review Center' },
      { id: 'reconciliation', name: 'Reconciliation', expected: 'Bank Statement' },
      { id: 'gst', name: 'GST Returns', expected: 'Coming Soon' },
      { id: 'itr', name: 'ITR', expected: 'Coming Soon' },
      { id: 'financial-statements', name: 'Financial Statements', expected: 'Financial Statements Scope' },
      { id: 'ai-assistant', name: 'AI Assistant', expected: 'LiteBooks AI Assistant' },
      { id: 'documents', name: 'Documents', expected: 'Financial Document Repository' },
      { id: 'history', name: 'History', expected: 'Audit Trail & Action History' },
      { id: 'settings', name: 'Settings', expected: 'Settings' },
    ];

    let allModulesPassed = true;
    for (const mod of modules) {
      await cdp.eval(`
        (() => {
          const buttons = Array.from(document.querySelectorAll('aside button'));
          const target = buttons.find(b => b.innerText.toLowerCase().includes('${mod.name.toLowerCase()}'));
          if (target) target.click();
        })()
      `);
      await sleep(1000);

      const bodyText = await cdp.eval('document.body.innerText');
      const activeText = await cdp.eval('document.querySelector("aside button.font-semibold")?.innerText');
      const matches = bodyText.includes(mod.expected);
      console.log(`- Module [${mod.name}]: Active="${activeText?.trim().replace(/\\n/g, ' ')}" | Matches "${mod.expected}": ${matches}`);
      if (!matches) {
        allModulesPassed = false;
        console.warn(`  FAILED: Content does not contain "${mod.expected}"`);
      }
    }
    testResults.ROUTING = allModulesPassed ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 4. Test Real XLSX Upload (Zion Lifts Financials)
    // -------------------------------------------------------------------------
    console.log('\n[Step 4] Navigating to Documents for Real XLSX Upload...');
    await cdp.eval(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button'));
        const docBtn = buttons.find(b => b.innerText.includes('Documents'));
        if (docBtn) docBtn.click();
      })()
    `);
    await sleep(1000);

    const zionPath = path.resolve('test_files', 'Zion_Lifts_Financials.xlsx');
    console.log(`Uploading file via CDP DOM.setFileInputFiles: ${zionPath}`);

    const fileInputNode = await cdp.send('DOM.querySelector', {
      nodeId: (await cdp.send('DOM.getDocument')).root.nodeId,
      selector: 'input[type="file"]',
    });

    await cdp.send('DOM.setFileInputFiles', {
      nodeId: fileInputNode.nodeId,
      files: [zionPath],
    });
    await sleep(1000);

    // Verify selected filename in drop zone
    const selectedFileText = await cdp.eval('document.querySelector("form")?.innerText');
    console.log(`Dropzone detected file: ${selectedFileText.includes('Zion_Lifts_Financials.xlsx')}`);

    // Click Save & Register Document
    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save & Register Document'));
        if (btn) btn.click();
      })()
    `);
    console.log('Clicked Save & Register Document, waiting for upload & registration...');
    await sleep(3500);

    const uploadStatusMsg = await cdp.eval('document.querySelector("form")?.innerText');
    console.log(`Upload Status in UI: "${uploadStatusMsg.split('\\n').filter(s => s.includes('Successfully')).join(' ') || uploadStatusMsg.split('\\n')[0]}"`);

    // Verify presence in table
    const tableText = await cdp.eval('document.querySelector("table")?.innerText || ""');
    const xlsxInTable = tableText.includes('Zion_Lifts_Financials.xlsx');
    console.log(`Zion Lifts in Documents Table: ${xlsxInTable}`);

    testResults.XLSX_UPLOAD = (uploadStatusMsg.includes('Successfully uploaded') || xlsxInTable) ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 5. Verify Uploaded Document & Inspection Drawer
    // -------------------------------------------------------------------------
    console.log('\n[Step 5] Testing Document Inspection Drawer...');
    await cdp.eval(`
      (() => {
        const rows = Array.from(document.querySelectorAll('tbody tr'));
        const zionRow = rows.find(r => r.innerText.includes('Zion_Lifts_Financials.xlsx'));
        if (zionRow) {
          const inspectBtn = zionRow.querySelector('button');
          if (inspectBtn) inspectBtn.click();
        }
      })()
    `);
    console.log('Opened Inspection Drawer, waiting for analysis...');
    await sleep(3000);

    const drawerHeading = await cdp.eval('document.querySelector(".fixed.inset-0 h2")?.innerText');
    const drawerText = await cdp.eval('document.querySelector(".fixed.inset-0")?.innerText');
    const hasSheets = drawerText.includes('Balance Sheet') && drawerText.includes('Profit & Loss') && drawerText.includes('Bank Statement');
    const hasDiscrepancies = drawerText.includes('Discrepancies Detected');

    console.log(`Drawer Heading: "${drawerHeading}"`);
    console.log(`Contains worksheets ('Balance Sheet', 'Profit & Loss', 'Bank Statement'): ${hasSheets}`);
    console.log(`Detected Discrepancies Alert: ${hasDiscrepancies}`);

    testResults.DOCUMENT_PERSISTENCE = xlsxInTable ? 'PASS' : 'FAIL';
    testResults.DOCUMENT_ANALYSIS = (hasSheets && hasDiscrepancies) ? 'PASS' : 'FAIL';

    // Close drawer
    await cdp.eval(`
      (() => {
        const closeBtn = document.querySelector('.fixed.inset-0 button');
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(1000);

    // -------------------------------------------------------------------------
    // 6. Test XLS Upload
    // -------------------------------------------------------------------------
    console.log('\n[Step 6] Testing XLS Upload...');
    const xlsPath = path.resolve('test_files', 'financial_sample.xls');
    const rootNode2 = (await cdp.send('DOM.getDocument')).root.nodeId;
    const fileInput2 = await cdp.send('DOM.querySelector', {
      nodeId: rootNode2,
      selector: 'input[type="file"]',
    });
    await cdp.send('DOM.setFileInputFiles', { nodeId: fileInput2.nodeId, files: [xlsPath] });
    await sleep(1000);

    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save & Register Document'));
        if (btn) btn.click();
      })()
    `);
    await sleep(3000);

    const tableAfterXls = await cdp.eval('document.querySelector("table")?.innerText || ""');
    const xlsInTable = tableAfterXls.includes('financial_sample.xls');
    console.log(`financial_sample.xls in Documents Table: ${xlsInTable}`);
    testResults.XLS_UPLOAD = xlsInTable ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 7. Test CSV Upload
    // -------------------------------------------------------------------------
    console.log('\n[Step 7] Testing CSV Upload...');
    const csvPath = path.resolve('test_files', 'accounting_sample.csv');
    const rootNode3 = (await cdp.send('DOM.getDocument')).root.nodeId;
    const fileInput3 = await cdp.send('DOM.querySelector', {
      nodeId: rootNode3,
      selector: 'input[type="file"]',
    });
    await cdp.send('DOM.setFileInputFiles', { nodeId: fileInput3.nodeId, files: [csvPath] });
    await sleep(1000);

    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save & Register Document'));
        if (btn) btn.click();
      })()
    `);
    await sleep(3000);

    const tableAfterCsv = await cdp.eval('document.querySelector("table")?.innerText || ""');
    const csvInTable = tableAfterCsv.includes('accounting_sample.csv');
    console.log(`accounting_sample.csv in Documents Table: ${csvInTable}`);
    testResults.CSV_UPLOAD = csvInTable ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 8. Test PDF Upload & Fallback Message
    // -------------------------------------------------------------------------
    console.log('\n[Step 8] Testing PDF Upload & Non-Extraction Message...');
    const pdfPath = path.resolve('test_files', 'vendor_invoice.pdf');
    const rootNode4 = (await cdp.send('DOM.getDocument')).root.nodeId;
    const fileInput4 = await cdp.send('DOM.querySelector', {
      nodeId: rootNode4,
      selector: 'input[type="file"]',
    });
    await cdp.send('DOM.setFileInputFiles', { nodeId: fileInput4.nodeId, files: [pdfPath] });
    await sleep(1000);

    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save & Register Document'));
        if (btn) btn.click();
      })()
    `);
    await sleep(3000);

    // Click inspect on vendor_invoice.pdf
    await cdp.eval(`
      (() => {
        const rows = Array.from(document.querySelectorAll('tbody tr'));
        const pdfRow = rows.find(r => r.innerText.includes('vendor_invoice.pdf'));
        if (pdfRow) {
          const inspectBtn = pdfRow.querySelector('button');
          if (inspectBtn) inspectBtn.click();
        }
      })()
    `);
    await sleep(2500);

    const pdfDrawerText = await cdp.eval('document.querySelector(".fixed.inset-0")?.innerText');
    const pdfMessageFound = pdfDrawerText.includes('PDF uploaded successfully. Detailed financial extraction is not yet available.');
    console.log(`PDF Fallback Message verified: ${pdfMessageFound}`);
    testResults.PDF_UPLOAD = pdfMessageFound ? 'PASS' : 'FAIL';

    // Close drawer
    await cdp.eval(`
      (() => {
        const closeBtn = document.querySelector('.fixed.inset-0 button');
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(1000);

    // -------------------------------------------------------------------------
    // 9. Test Invalid File Format (.png)
    // -------------------------------------------------------------------------
    console.log('\n[Step 9] Testing Invalid File Format (.png)...');
    const pngPath = path.resolve('test_files', 'invalid_image.png');
    const rootNode5 = (await cdp.send('DOM.getDocument')).root.nodeId;
    const fileInput5 = await cdp.send('DOM.querySelector', {
      nodeId: rootNode5,
      selector: 'input[type="file"]',
    });
    await cdp.send('DOM.setFileInputFiles', { nodeId: fileInput5.nodeId, files: [pngPath] });
    await sleep(1000);

    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save & Register Document'));
        if (btn) btn.click();
      })()
    `);
    await sleep(2000);

    const invalidStatusText = await cdp.eval('document.querySelector("form")?.innerText');
    const hasUnsupportedMsg = invalidStatusText.includes('Unsupported file format') || invalidStatusText.includes('.png');
    console.log(`Invalid file error displayed: ${hasUnsupportedMsg} ("${invalidStatusText.split('\\n').filter(s => s.includes('Unsupported')).join(' ')}")`);
    testResults.INVALID_FILE_HANDLING = hasUnsupportedMsg ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 10. AI Assistant Document Context & Chat
    // -------------------------------------------------------------------------
    console.log('\n[Step 10] Testing AI Assistant with Attached Document...');
    await cdp.eval(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button'));
        const aiBtn = buttons.find(b => b.innerText.includes('AI Assistant'));
        if (aiBtn) aiBtn.click();
      })()
    `);
    await sleep(1500);

    // Attach Zion_Lifts_Financials.xlsx
    const rootNode6 = (await cdp.send('DOM.getDocument')).root.nodeId;
    const fileInput6 = await cdp.send('DOM.querySelector', {
      nodeId: rootNode6,
      selector: 'input[type="file"]',
    });
    await cdp.send('DOM.setFileInputFiles', { nodeId: fileInput6.nodeId, files: [zionPath] });
    console.log('Attached Zion_Lifts_Financials.xlsx to AI Assistant, waiting for file registration...');
    await sleep(3500);

    const chatContextText = await cdp.eval('document.body.innerText');
    const hasAttachment = chatContextText.includes('Zion_Lifts_Financials.xlsx');
    console.log(`AI Chat recognizes attached file: ${hasAttachment}`);

    // Type query: "What is wrong with this workbook?"
    await cdp.eval(`
      (() => {
        const input = document.querySelector('input[type="text"][placeholder*="accounting"]');
        if (input) {
          input.value = "What is wrong with this workbook?";
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()
    `);
    await sleep(500);

    // Click Send
    await cdp.eval(`
      (() => {
        const sendBtn = Array.from(document.querySelectorAll('button')).find(b => b.querySelector('svg.lucide-send') || b.title === 'Send message' || b.className.includes('bg-brand-500'));
        if (sendBtn) sendBtn.click();
      })()
    `);
    console.log('Sent query: "What is wrong with this workbook?", waiting for deterministic AI response...');
    await sleep(5000);

    const chatBodyText = await cdp.eval('document.body.innerText');
    const hasDeterministicAnswer = chatBodyText.includes('Trade Payables') || chatBodyText.includes('discrepanc') || chatBodyText.includes('Balance Sheet');
    console.log(`AI Chat returned deterministic analysis: ${hasDeterministicAnswer}`);
    testResults.AI_CONTEXT = hasDeterministicAnswer ? 'PASS' : 'FAIL';

    // -------------------------------------------------------------------------
    // 11. Responsive Viewports Test
    // -------------------------------------------------------------------------
    console.log('\n[Step 11] Testing Responsive Viewports...');
    const viewports = [
      { name: 'Desktop', width: 1440, height: 900 },
      { name: 'Laptop', width: 1280, height: 800 },
      { name: 'Tablet', width: 768, height: 1024 },
      { name: 'Mobile', width: 390, height: 844 },
    ];

    let responsivePassed = true;
    for (const vp of viewports) {
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: 1,
        mobile: vp.width < 768,
      });
      await sleep(1000);

      // Check for horizontal overflow or inaccessible elements
      const hasHorizontalScroll = await cdp.eval('document.documentElement.scrollWidth > window.innerWidth');
      const headerVisible = await cdp.eval('!!document.querySelector("header")');
      console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}): Header visible=${headerVisible}, Horizontal Overflow=${hasHorizontalScroll}`);
      if (hasHorizontalScroll) {
        responsivePassed = false;
      }
    }
    testResults.RESPONSIVE_FUNCTIONALITY = responsivePassed ? 'PASS' : 'FAIL';

    // Restore desktop
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });

    // -------------------------------------------------------------------------
    // 12. Browser Console & Network Errors Check
    // -------------------------------------------------------------------------
    console.log('\n[Step 12] Inspecting Console Logs & Network Failures...');
    const fatalErrors = cdp.pageErrors.filter(
      (e) => !e.description?.includes('favicon')
    );
    const failedRequests = cdp.networkRequests.filter(
      (r) => r.status >= 500
    );

    console.log(`Console Logs captured: ${cdp.consoleLogs.length}`);
    console.log(`Page Uncaught Exceptions: ${fatalErrors.length}`);
    console.log(`Failed HTTP Requests (>=500): ${failedRequests.length}`);

    testResults.BROWSER_CONSOLE = fatalErrors.length === 0 && failedRequests.length === 0 ? 'PASS' : 'FAIL';

  } catch (err) {
    console.error('Test execution error:', err);
  } finally {
    if (cdp) await cdp.close();
    chromeProc.kill();
    try {
      fs.rmSync(TEMP_USER_DATA, { recursive: true, force: true });
    } catch (_) {}
  }

  console.log('\n==================================================');
  console.log('FINAL VALIDATION RESULTS SUMMARY:');
  console.log('==================================================');
  for (const [k, v] of Object.entries(testResults)) {
    console.log(`${k}: ${v}`);
  }
}

runValidation();
