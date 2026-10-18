// Automated stand-ins for the H2 owner checklist items B, C, D (docs/accessibility.md §7).
// Never touches the AI expander: zero Gemini quota. C1 sends the fake-mic clip to the
// app's normal Google speech-recognition path (needs internet), exactly as a user would.
//
//   node owner_checks.mjs --wav=<clip.wav> --out=<dir> [--only=b1,b2,b3,c1,c2,d1,d2]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)=?(.*)$/); return m ? [m[1], m[2] || true] : [a, true];
}));
const BASE = args.base || 'http://localhost:8501';
const OUT = args.out || '.'; fs.mkdirSync(OUT, { recursive: true });
const ONLY = args.only ? String(args.only).split(',') : null;
const LEGAL_Q = 'What are the penalties under the Act?';
const HELP_Q = 'I need an organisation that can help me in Lagos';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const res = {};
const log = (k, v) => { res[k] = v; console.log(`\n=== ${k}\n` + JSON.stringify(v, null, 1)); };

const CHROMIUM = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
async function open({ edge = false, extra = [], vp = { width: 1280, height: 800 }, perms = [] } = {}) {
  // occluded automation windows get throttled, and streamlit components never size themselves
  const noThrottle = ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
    '--disable-background-timer-throttling', '--disable-features=CalculateNativeWinOcclusion'];
  const browser = await chromium.launch({ headless: false, args: [...noThrottle, ...extra],
    ...(edge ? { channel: 'msedge' } : args.chrome ? { channel: 'chrome' } : { executablePath: fs.existsSync(CHROMIUM) ? CHROMIUM : undefined }) });
  const ctx = await browser.newContext({ viewport: vp, permissions: perms });
  const page = await ctx.newPage();
  await page.goto(BASE); await page.getByText('National helplines').first().waitFor({ timeout: 60000 });
  await sleep(2000);
  return { browser, ctx, page };
}
async function ask(page, q) {
  const n = await page.locator('[data-testid="stChatMessage"]').count();
  const ta = page.getByTestId('stChatInputTextArea');
  await ta.fill(q); await ta.press('Enter');
  await page.waitForFunction(k => document.querySelectorAll('[data-testid="stChatMessage"]').length >= k + 2, n, { timeout: 60000 });
  await sleep(2500);
}
const desc = () => {
  const a = document.activeElement; if (!a) return 'none';
  return a.tagName + ':' + (a.title || a.getAttribute('aria-label') || a.innerText || a.placeholder || '').trim().replace(/\s+/g, ' ').slice(0, 50);
};
const want = k => !ONLY || ONLY.includes(k);

// ---- B1 + B2: keyboard reach and focus visibility (1280) -----------------
if (want('b1') || want('b2')) {
  const { browser, page } = await open();
  await ask(page, LEGAL_Q);
  // start from the address bar equivalent: blur everything, then Tab through the page
  await page.evaluate(() => document.activeElement.blur());
  const stops = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab'); await sleep(120);
    let d = await page.evaluate(desc);
    if (d.startsWith('IFRAME')) {   // which control inside the frame holds focus?
      const inner = [];
      for (const f of page.frames()) { if (f === page.mainFrame()) continue;
        try { const x = await f.evaluate(() => document.hasFocus() && document.activeElement ? document.activeElement.tagName + ':' + document.activeElement.innerText.trim().slice(0, 30) : null); if (x) inner.push(x); } catch {} }
      d += ' -> ' + inner.join(',');
    }
    stops.push(d);
    if (want('b2') && /Type your question|more excerpt|High contrast|Read answer aloud|Switch to help|Voice input/.test(d)) {
      await page.screenshot({ path: path.join(OUT, `focus_${String(i).padStart(2, '0')}.png`) });
    }
  }
  log('b1_tab_order', stops);
  // Voice expander: Enter opens it, then Tab reaches Record (iframe), draft box, Send
  const vs = page.locator('summary', { hasText: 'Voice input' });
  await vs.focus(); await page.keyboard.press('Enter'); await sleep(1500);
  const inside = [];
  for (let i = 0; i < 4; i++) { await page.keyboard.press('Tab'); await sleep(150); inside.push(await page.evaluate(desc)); }
  log('b1_voice_expander', inside);
  await browser.close();
}

// ---- B3: drawer focus trap at 360 ----------------------------------------
if (want('b3')) {
  const { browser, page } = await open({ vp: { width: 360, height: 740 } });
  const openBtn = page.locator('[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button').first();
  await openBtn.click(); await sleep(1200);
  const inSidebar = () => !!document.activeElement.closest('[data-testid="stSidebar"]');
  const stops = [];
  await page.getByRole('checkbox', { name: 'High contrast mode' }).focus();
  for (let i = 0; i < 25; i++) { await page.keyboard.press('Tab'); await sleep(120);
    stops.push((await page.evaluate(inSidebar) ? 'IN ' : 'OUT ') + await page.evaluate(desc)); }
  const sidebarOpen = () => { const s = document.querySelector('[data-testid="stSidebar"]'); const r = s.getBoundingClientRect(); return r.right > 50 && getComputedStyle(s).visibility !== 'hidden'; };
  const before = await page.evaluate(sidebarOpen);
  await page.keyboard.press('Escape'); await sleep(1200);
  const afterEsc = await page.evaluate(sidebarOpen);
  const focusAfterEsc = await page.evaluate(desc);
  let afterClose = null;
  if (afterEsc) { // fall back to the close button
    await page.locator('[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarHeader"] button').first().click(); await sleep(1200);
    afterClose = await page.evaluate(sidebarOpen);
  }
  await page.screenshot({ path: path.join(OUT, 'b3_after_close.png') });
  log('b3_drawer', { stops, openBefore: before, openAfterEsc: afterEsc, focusAfterEsc, openAfterCloseBtn: afterClose });
  await browser.close();
}

// ---- C1: live mic path with a fake microphone (Chromium, then Edge) -------
async function c1(edge) {
  const key = edge ? 'c1_edge' : 'c1_chrome';
  const { browser, page } = await open({ edge, perms: ['microphone'], extra: ['--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${args.wav}`] });
  try {
    await page.locator('summary', { hasText: 'Voice input' }).click(); await sleep(2500);
    const mic = page.frameLocator('iframe[title*="mic_recorder"]');
    // automation windows leave this component iframe at height 0 (real Chrome: 38 px),
    // so press its button from inside the frame instead of by pointer
    const micFrame = await page.locator('iframe[title*="mic_recorder"]').elementHandle().then(h => h.contentFrame());
    const press = t => micFrame.evaluate(t => { const b = [...document.querySelectorAll('button')].find(b => b.innerText.includes(t)); b.click(); return b.innerText; }, t);
    await press('Record question');
    await sleep(5000);
    await press('Stop recording');
    const heard = await page.getByText(/^Heard:|Could not transcribe/).first().textContent({ timeout: 40000 });
    const draft = page.getByRole('textbox', { name: 'Type your question here' }).first();
    await page.waitForFunction(() => [...document.querySelectorAll('input[aria-label="Type your question here"]')].some(i => i.value), null, { timeout: 15000 }).catch(() => {});
    const draftValue = await draft.inputValue();
    // edit it, then Send
    await draft.fill(draftValue.replace(/\?*$/, '') + ' in school?'); await draft.press('Tab');
    await sleep(800);
    await page.getByRole('button', { name: 'Send this question' }).click();
    await page.locator('[data-testid="stChatMessage"]').nth(1).waitFor({ timeout: 60000 }); await sleep(2500);
    const msgs = await page.locator('[data-testid="stChatMessage"]').allInnerTexts();
    log(key, { heard, draftValue, sent: msgs[0]?.replace(/\s+/g, ' ').slice(0, 80),
      answerHead: msgs[1]?.replace(/\s+/g, ' ').slice(0, 160), legal: /Your rights/.test(msgs[1] || '') });
    await page.screenshot({ path: path.join(OUT, `${key}.png`) });
  } catch (e) { log(key, { error: String(e).slice(0, 300) }); await page.screenshot({ path: path.join(OUT, `${key}_err.png`) }); }
  await browser.close();
}
if (want('c1')) { await c1(false); await c1(true); }

// ---- C2: microphone permission DENIED ------------------------------------
async function c2(edge) {
  const key = edge ? 'c2_edge' : 'c2_chrome';
  const { browser, ctx, page } = await open({ edge });
  const errs = []; page.on('pageerror', e => errs.push(String(e).slice(0, 150)));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 150)); });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Browser.setPermission', { permission: { name: 'microphone' }, setting: 'denied', origin: BASE });
  await page.reload(); await page.getByText('National helplines').first().waitFor({ timeout: 60000 }); await sleep(2000);
  await page.locator('summary', { hasText: 'Voice input' }).click(); await sleep(2500);
  const mic = page.frameLocator('iframe[title*="mic_recorder"]');
  let clicked = true;
  try { const mf = await page.locator('iframe[title*="mic_recorder"]').elementHandle().then(h => h.contentFrame());
    await mf.evaluate(() => [...document.querySelectorAll('button')].find(b => b.innerText.includes('Record question')).click()); } catch { clicked = false; }
  await sleep(5000);
  const expanderText = await page.locator('[data-testid="stExpander"]', { hasText: 'Voice input' }).innerText();
  let micText = ''; try { micText = await mic.locator('body').innerText({ timeout: 3000 }); } catch {}
  const errorPage = await page.locator('[data-testid="stException"]').count();
  await page.screenshot({ path: path.join(OUT, `${key}.png`) });
  // the text box must still work
  await ask(page, LEGAL_Q);
  const answered = /Your rights/.test(await page.locator('[data-testid="stChatMessage"]').last().innerText());
  log(key, { clicked, micText: micText.trim(), expanderText: expanderText.replace(/\s+/g, ' ').slice(0, 300),
    exceptionBlocks: errorPage, textBoxStillAnswers: answered, errs: errs.slice(0, 6) });
  await browser.close();
}
if (want('c2')) { await c2(false); await c2(true); }

// ---- D1 / D2: what Read answer aloud speaks, in order --------------------
async function readAloud(q, key) {
  const { browser, page } = await open();
  await ask(page, q);
  const frames = page.locator('iframe[title*="Read answer aloud"]');
  const fr = await frames.last().elementHandle().then(h => h.contentFrame());
  const spoken = await fr.evaluate(async () => {
    const said = []; speechSynthesis.speak = u => said.push(u.text);
    document.querySelector('button').click(); await new Promise(r => setTimeout(r, 1000)); return said;
  });
  const cards = await page.locator('[data-testid="stChatMessage"]').last().evaluate(e =>
    (e.textContent.match(/\[(?:Act cl\.|Constitution s\.|Factsheet Section) [^\]]+\]/g) || []));
  log(key, { spoken: spoken.map(s => s.replace(/\d{5}-\d{4}-\d+/g, '<num>')), visibleTags: cards });
  await browser.close();
}
if (want('d1')) await readAloud(LEGAL_Q, 'd1_legal');
if (want('d2')) await readAloud(HELP_Q, 'd2_help');

fs.writeFileSync(path.join(OUT, 'owner_checks.json'), JSON.stringify(res, null, 1));
