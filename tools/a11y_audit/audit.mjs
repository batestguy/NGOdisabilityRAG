// DRLCA H2 accessibility audit (WCAG 2.2 AA) -- axe matrix, keyboard pass, geometry.
//
// Replaces the playbook's manual chrome-devtools MCP clicking with a reproducible,
// pinned script (docs/accessibility.md "How to re-run"). It never enables the AI
// expander or the "AI-answer every new turn" switch: zero Gemini quota.
//
//   node audit.mjs --base=http://localhost:8501 --out=D:/NGORAG/runs/h2_after --mode=matrix
//   modes: matrix | keyboard | geometry | contrast | all      (default all)
//
// Browser: Playwright's chromium, or CHROME_PATH / the cached chromium-1234 build if
// present (offline machines: no second browser download).
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)=?(.*)$/); return m ? [m[1], m[2] || true] : [a, true];
}));
const BASE = (args.base || 'http://localhost:8501').replace(/\/$/, '');
const OUT = args.out || 'runs/h2_after';
const MODE = args.mode || 'all';
const ONLY = args.cells ? String(args.cells).split(',') : null;
fs.mkdirSync(OUT, { recursive: true });

const LEGAL_Q = 'What are the penalties under the Act?';
const HELP_Q = 'I need an organisation that can help me in Lagos';
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const IMPACTS = ['critical', 'serious', 'moderate', 'minor'];

function exePath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const cached = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
  return fs.existsSync(cached) ? cached : undefined;
}

// Matrix cells. 360/768/1280 are the playbook widths; 768 is exactly where the
// sidebar flips from drawer (<=767) to side-by-side (>=768). "zoom200" is 200 %
// browser zoom at a 360 px device (180 CSS px at deviceScaleFactor 2). "textmax"
// is the app's own Text size slider at its maximum (28 px root) at 360.
const CELLS = [];
for (const w of [360, 768, 1280]) for (const t of ['light', 'dark', 'hc'])
  CELLS.push({ id: `${w}_${t}`, width: w, theme: t, dsf: 1 });
CELLS.push({ id: '360_zoom200_light', width: 180, theme: 'light', dsf: 2 });
CELLS.push({ id: '360_textmax_light', width: 360, theme: 'light', dsf: 1, textmax: true });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitHealthy() {
  for (let i = 0; i < 120; i++) {
    try { const r = await fetch(BASE + '/_stcore/health'); if (r.ok) return; } catch { /* booting */ }
    await sleep(2000);
  }
  throw new Error('server never became healthy: ' + BASE);
}

async function waitIdle(page, extra = 1200) {
  await page.waitForFunction(() => {
    const a = document.querySelector('[data-testid="stApp"]');
    return a && a.getAttribute('data-test-script-state') === 'notRunning';
  }, null, { timeout: 180000 });
  await page.waitForTimeout(extra); // component iframes run their own scripts after mount
}

async function setTheme(page, theme) {
  const want = theme === 'dark' ? 'Dark' : 'Light';
  await page.click('[data-testid="stMainMenu"] button');
  await page.click(`[data-testid="stMainMenuItem-theme-${want}"]`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  const bg = await page.evaluate(() => getComputedStyle(document.querySelector('.stApp')).backgroundColor);
  const ok = theme === 'dark' ? bg === 'rgb(13, 17, 23)' : bg === 'rgb(255, 255, 255)';
  if (!ok) throw new Error(`theme ${theme} not applied, .stApp bg=${bg}`);
  return bg;
}

const sidebarExpanded = page => page.evaluate(() =>
  document.querySelector('section[data-testid="stSidebar"]').getAttribute('aria-expanded') === 'true');

async function openSidebar(page) {
  if (await sidebarExpanded(page)) return;
  // DOM click, not a pointer click: on the pre-H2 tree the header covers these
  // buttons at 360 px (the very defect H2 fixed), and at 1280 the collapse
  // button is shown only on hover. The audit needs the state, not the gesture.
  await page.locator('[data-testid="stExpandSidebarButton"]').evaluate(e => e.click());
  await page.waitForFunction(() => document.querySelector('section[data-testid="stSidebar"]').getAttribute('aria-expanded') === 'true');
  await page.waitForTimeout(600);
}
async function closeSidebar(page) {
  if (!(await sidebarExpanded(page))) return;
  await page.locator('[data-testid="stSidebarCollapseButton"] button').evaluate(e => e.click());
  await page.waitForFunction(() => document.querySelector('section[data-testid="stSidebar"]').getAttribute('aria-expanded') === 'false');
  await page.waitForTimeout(600);
}

async function applyCellControls(page, cell) {
  if (cell.theme !== 'hc' && !cell.textmax) return;
  const wasOpen = await sidebarExpanded(page);
  await openSidebar(page);
  if (cell.theme === 'hc') {
    await page.locator('section[data-testid="stSidebar"] label').filter({ hasText: 'High contrast mode' }).click();
    await page.waitForSelector('.drlca-hc-on', { state: 'attached', timeout: 60000 });
    await waitIdle(page, 500);
  }
  if (cell.textmax) {
    const thumb = page.locator('[data-testid="stSlider"] input[type="range"]');
    await thumb.focus();
    await page.keyboard.press('End');
    await page.waitForFunction(() => getComputedStyle(document.documentElement).fontSize === '28px', null, { timeout: 60000 });
    await waitIdle(page, 500);
  }
  if (!wasOpen) await closeSidebar(page);
}

async function openCell(browser, cell) {
  const ctx = await browser.newContext({
    viewport: { width: cell.width, height: cell.dsf === 2 ? 400 : 800 },
    deviceScaleFactor: cell.dsf,
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(BASE + '/');
  await page.waitForSelector('[data-testid="stChatInput"] textarea', { timeout: 180000 });
  await waitIdle(page);
  const bg = await setTheme(page, cell.theme === 'dark' ? 'dark' : 'light');
  await applyCellControls(page, cell);
  return { ctx, page, errors, bg };
}

async function ask(page, q, kind) {
  const ta = page.locator('[data-testid="stChatInput"] textarea');
  await ta.fill(q);
  await ta.press('Enter');
  const marker = kind === 'legal' ? 'Retrieved excerpts' : 'Help near you';
  await page.waitForFunction(m => document.body.innerText.includes(m), marker, { timeout: 180000 });
  await waitIdle(page, 1500);
  // Wait for the turn's read-aloud iframe to name itself (its script ran).
  await page.waitForFunction(() => [...document.querySelectorAll('iframe')]
    .some(f => (f.getAttribute('title') || '').includes('Read answer aloud')), null, { timeout: 60000 }).catch(() => {});
  return page.evaluate(k => {
    const txt = document.body.innerText;
    const m = txt.match(/Showing (\d+) contact\(s\)/);
    return {
      kind: k,
      clarify: txt.includes('❓'),
      helplines_in_turn: [...document.querySelectorAll('[data-testid="stChatMessage"] .drlca-banner')].length,
      contacts: m ? +m[1] : null,
      excerpt_cards: document.querySelectorAll('[data-testid="stChatMessage"] .drlca-answer').length,
    };
  }, kind);
}

function summarise(res) {
  const by = Object.fromEntries(IMPACTS.map(i => [i, 0]));
  const nodes = Object.fromEntries(IMPACTS.map(i => [i, 0]));
  for (const v of res.violations) { by[v.impact] = (by[v.impact] || 0) + 1; nodes[v.impact] = (nodes[v.impact] || 0) + v.nodes.length; }
  return {
    rules_by_impact: by, nodes_by_impact: nodes,
    rule_ids: res.violations.map(v => `${v.id}(${v.impact},${v.nodes.length})`),
    incomplete: res.incomplete.map(v => v.id),
  };
}

async function scan(page) {
  const res = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  return {
    url: res.url, testEngine: res.testEngine, timestamp: res.timestamp,
    violations: res.violations.map(v => ({
      id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl, tags: v.tags,
      nodes: v.nodes.map(n => ({ target: n.target, html: n.html.slice(0, 300), summary: (n.failureSummary || '').slice(0, 600) })),
    })),
    incomplete: res.incomplete.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
    passes: res.passes.length,
    pass_ids: res.passes.map(p => p.id),
  };
}

async function runMatrix(browser) {
  const summary = [];
  for (const cell of CELLS) {
    if (ONLY && !ONLY.includes(cell.id)) continue;
    for (const state of ['empty', 'legal', 'help']) {
      const t0 = Date.now();
      let ctx = null;
      try {
        const o = await openCell(browser, cell); ctx = o.ctx;
        const { page, errors, bg } = o;
        let turn = null;
        if (state === 'legal') turn = await ask(page, LEGAL_Q, 'legal');
        if (state === 'help') turn = await ask(page, HELP_Q, 'help');
        if (state === 'help' && (turn.clarify || !(turn.contacts >= 3)))
          throw new Error('help turn did not render helplines + NGO records: ' + JSON.stringify(turn));
        const res = await scan(page);
        const s = summarise(res);
        const row = { cell: cell.id, state, bg, hc: cell.theme === 'hc', turn, ...s, page_errors: errors, secs: Math.round((Date.now() - t0) / 1000) };
        fs.writeFileSync(path.join(OUT, `axe_${cell.id}_${state}.json`), JSON.stringify({ ...row, axe: res }, null, 1));
        await page.screenshot({ path: path.join(OUT, `shot_${cell.id}_${state}.png`) });
        summary.push(row);
        console.log(`${cell.id.padEnd(20)} ${state.padEnd(6)} C${s.rules_by_impact.critical} S${s.rules_by_impact.serious} M${s.rules_by_impact.moderate} m${s.rules_by_impact.minor}  ${s.rule_ids.join(' ')}`);
      } catch (e) {
        summary.push({ cell: cell.id, state, error: String(e) });
        console.log(`${cell.id} ${state} ERROR ${e}`);
      } finally { if (ctx) await ctx.close(); }
    }
  }
  // --cells re-runs merge into the existing summary (same cell+state replaced).
  const sp = path.join(OUT, 'summary.json');
  if (ONLY && fs.existsSync(sp)) {
    const old = JSON.parse(fs.readFileSync(sp, 'utf8')).rows || [];
    const fresh = new Set(summary.map(r => r.cell + '|' + r.state));
    const merged = old.filter(r => !fresh.has(r.cell + '|' + r.state)).concat(summary);
    const order = CELLS.map(c => c.id);
    merged.sort((x, y) => order.indexOf(x.cell) - order.indexOf(y.cell) || ['empty', 'legal', 'help'].indexOf(x.state) - ['empty', 'legal', 'help'].indexOf(y.state));
    summary.length = 0; summary.push(...merged);
  }
  const tot = Object.fromEntries(IMPACTS.map(i => [i, summary.reduce((a, r) => a + (r.rules_by_impact ? r.rules_by_impact[i] : 0), 0)]));
  fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify({ base: BASE, tags: AXE_TAGS, totals_rules_by_impact: tot, rows: summary }, null, 1));
  console.log('TOTAL rule-violations by impact (summed over cells):', JSON.stringify(tot));
  return summary;
}

// ---------------------------------------------------------------- keyboard
// Describe the deepest focused element (descending into same-origin iframes) and
// whether it shows a visible focus indicator: computed outline/box-shadow/border/
// background of the element and 4 ancestors, focused vs blurred. Any change = an
// indicator exists. Also whether its centre is the topmost element (2.4.11).
const DESCRIBE = () => {
  const el = document.activeElement;
  const PROPS = ['outlineStyle', 'outlineWidth', 'outlineColor', 'boxShadow', 'borderColor', 'backgroundColor'];
  const chain = []; for (let e = el, i = 0; e && i < 5; e = e.parentElement, i++) chain.push(e);
  const snap = () => chain.map(e => { const cs = getComputedStyle(e); return PROPS.map(p => cs[p]).join('|'); });
  const on = snap();
  const own = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const top = document.elementFromPoint(cx, cy);
  const inView = r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
  const uncovered = !!top && (top === el || el.contains(top) || top.contains(el));
  el.blur(); const off = snap(); el.focus({ preventScroll: true });
  const changed = [];
  chain.forEach((e, i) => { if (on[i] !== off[i]) { const a = on[i].split('|'), b = off[i].split('|'); PROPS.forEach((p, j) => { if (a[j] !== b[j]) changed.push(`${i}:${p}`); }); } });
  const testids = []; for (let e = el; e; e = e.parentElement) if (e.dataset && e.dataset.testid) testids.push(e.dataset.testid);
  const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') ||
    (el.labels && el.labels[0] && el.labels[0].innerText) || el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 80);
  // A stable per-element id: two stops with the same name (several "Link to
  // heading" anchors) must not look like a cycle.
  if (!el.dataset.kbid) { window.__kbn = (window.__kbn || 0) + 1; el.dataset.kbid = String(window.__kbn); }
  return {
    kbid: el.dataset.kbid,
    tag: el.tagName, role: el.getAttribute('role') || '', name, testids: testids.join('>'),
    outline: `${own.outlineStyle} ${own.outlineWidth}`, boxShadow: own.boxShadow.slice(0, 60),
    indicator: changed.length > 0, indicator_changes: changed.slice(0, 6),
    in_view: inView, centre_uncovered: uncovered, covered_by: uncovered || !top ? '' : (top.dataset?.testid || top.className || top.tagName).toString().slice(0, 60),
  };
};

async function activeDesc(page) {
  let frame = page.mainFrame(); let prefix = '';
  for (let depth = 0; depth < 3; depth++) {
    const h = await frame.evaluateHandle(() => document.activeElement);
    const tag = await h.evaluate(e => e && e.tagName);
    if (tag === 'IFRAME') {
      const f = await h.asElement().contentFrame();
      const innerTag = f ? await f.evaluate(() => document.activeElement && document.activeElement.tagName).catch(() => null) : null;
      if (f && innerTag && innerTag !== 'BODY') {
        const fid = await h.evaluate(e => { if (!e.dataset.kbid) { window.__kbn = (window.__kbn || 0) + 1; e.dataset.kbid = 'f' + window.__kbn; } return e.dataset.kbid; });
        prefix += `[iframe#${fid}] `; frame = f; continue;
      }
    }
    if (!tag || tag === 'BODY' || tag === 'HTML') return { tag: tag || 'NONE', name: '(document)', role: '', key: 'BODY' };
    const d = await frame.evaluate(DESCRIBE);
    d.frame = prefix.trim();
    d.key = `${prefix}${d.kbid}`;
    return d;
  }
}

async function tabWalk(page, max = 140) {
  await page.evaluate(() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); });
  await page.mouse.click(1, 120).catch(() => {}); // neutral point; puts the focus-navigation start at page top
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  const seq = []; let firstKey = null; let cycled = false; let trap = false;
  for (let i = 0; i < max; i++) {
    await page.keyboard.press('Tab');
    await page.waitForTimeout(120);
    const d = await activeDesc(page);
    seq.push(d);
    if (d.key === 'BODY') continue;
    if (firstKey === null) firstKey = d.key;
    else if (d.key === firstKey) { cycled = true; break; }
    const last5 = seq.slice(-5).map(x => x.key);
    if (last5.length === 5 && last5.every(k => k === d.key)) { trap = true; break; }
  }
  return { cycled, trap, stops: seq.length, seq };
}

function reach(seq) {
  const has = re => seq.some(d => re.test(`${d.name} ${d.testids} ${d.tag}`));
  return {
    chat_input: has(/stChatInput/),
    voice_expander: has(/Voice input/),
    read_aloud: has(/Read answer aloud/),
    ai_expander: has(/Answer with AI/),
    folded_excerpts: has(/more excerpt\(s\) retrieved/),
    sidebar_open_button: has(/stExpandSidebarButton/),
    sidebar_controls: has(/stSidebar/),
  };
}

async function runKeyboard(browser) {
  const out = {};
  for (const [label, width, sidebar] of [['1280', 1280, null], ['360', 360, null], ['360_sidebar_open', 360, 'open']]) {
    const { ctx, page } = await openCell(browser, { width, theme: 'light', dsf: 1 });
    try {
      await ask(page, LEGAL_Q, 'legal');
      if (sidebar === 'open') await openSidebar(page);
      const walk = await tabWalk(page);
      const stops = walk.seq.filter(d => d.key !== 'BODY');
      const res = {
        width, sidebar: sidebar || (await sidebarExpanded(page) ? 'open' : 'collapsed'),
        cycled: walk.cycled, trap: walk.trap, tab_presses: walk.stops,
        reach: reach(stops),
        no_indicator: stops.filter(d => !d.indicator).map(d => d.name || d.tag),
        obscured: stops.filter(d => !d.in_view || !d.centre_uncovered).map(d => `${d.name || d.tag} (${d.in_view ? 'covered by ' + d.covered_by : 'off-screen'})`),
        main_stops_while_drawer_open: sidebar === 'open' ? stops.filter(d => !/stSidebar/.test(d.testids) && d.key !== 'BODY').map(d => d.name || d.tag) : undefined,
        sequence: walk.seq.map(d => ({ name: d.name, role: d.role || d.tag, tag: d.tag, testids: d.testids, frame: d.frame, indicator: d.indicator, indicator_changes: d.indicator_changes, outline: d.outline, in_view: d.in_view, centre_uncovered: d.centre_uncovered, covered_by: d.covered_by })),
      };
      // Operability: folded excerpts + voice expander open from the keyboard.
      if (sidebar !== 'open') {
        res.operable = {};
        for (const [k, re] of [['folded_excerpts', /more excerpt\(s\) retrieved/], ['voice_expander', /Voice input/]]) {
          const sum = page.locator('[data-testid="stExpander"] summary').filter({ hasText: re }).last();
          await sum.focus(); await page.keyboard.press('Enter'); await waitIdle(page, 800);
          const open = await sum.evaluate(s => s.parentElement.open === true || s.getAttribute('aria-expanded') === 'true');
          res.operable[k] = open;
          if (k === 'voice_expander') {
            const inner = [];
            for (let i = 0; i < 4; i++) { await page.keyboard.press('Tab'); await page.waitForTimeout(150); const d = await activeDesc(page); inner.push(`${d.frame || ''} ${d.role || d.tag}: ${d.name}`.trim()); }
            res.operable.voice_inner_sequence = inner;
          }
        }
      }
      fs.writeFileSync(path.join(OUT, `keyboard_${label}.json`), JSON.stringify(res, null, 1));
      console.log(`keyboard ${label}: stops=${stops.length} cycled=${res.cycled} trap=${res.trap} reach=${JSON.stringify(res.reach)} no_indicator=${JSON.stringify(res.no_indicator)} obscured=${JSON.stringify(res.obscured)}${res.operable ? ' operable=' + JSON.stringify(res.operable) : ''}${res.main_stops_while_drawer_open ? ' main_while_drawer=' + JSON.stringify(res.main_stops_while_drawer_open) : ''}`);
      out[label] = res;
    } finally { await ctx.close(); }
  }
  return out;
}

// ---------------------------------------------------------------- geometry
// The general question (skill ui-geometry-audit step 4): bring every content
// element into view the way the browser does for focus (scroll-padding honoured),
// then sample its footprint and ask the DOM what is on top. The watermark and veil
// are pointer-events:none, which hit-testing skips, so they are made hit-testable
// FOR THE MEASUREMENT ONLY: a point whose topmost box is the veil is a point the
// veil paints over.
const GEOM = () => {
  const veils = [...document.querySelectorAll('.drlca-watermark,.drlca-veil')];
  veils.forEach(v => { v.dataset.pe = v.style.pointerEvents; v.style.pointerEvents = 'auto'; });
  // Native checkbox inputs are painted over by Streamlit's own proxy box, so the
  // label is what a user sees and what is checked; range inputs likewise (thumb).
  const sel = 'p,li,code,h1,h2,h3,button,textarea,input:not([type=checkbox]):not([type=range]),summary,[role=slider],iframe,.drlca-banner,.drlca-answer,[data-testid=stCaptionContainer],[data-testid=stCheckbox] label';
  const vis = e => { const cs = getComputedStyle(e); const r = e.getBoundingClientRect(); return cs.visibility !== 'hidden' && cs.display !== 'none' && r.width > 2 && r.height > 2; };
  const label = e => ((e.getAttribute('aria-label') || e.getAttribute('title') || e.innerText || e.tagName) + '').trim().replace(/\s+/g, ' ').slice(0, 50);
  const nameOf = t => !t ? 'nothing' : (t.classList.contains('drlca-veil') ? 'VEIL' : t.classList.contains('drlca-watermark') ? 'WATERMARK'
    : (t.closest('[data-testid=stBottom]') ? 'stBottom(chat bar)' : t.closest('[data-testid=stHeader]') ? 'stHeader' : t.closest('section[data-testid=stSidebar]') ? 'stSidebar'
      : (t.dataset?.testid || t.className || t.tagName).toString().slice(0, 40)));
  // Content of a CLOSED expander is not shown (and not in the accessibility tree)
  // even though Streamlit keeps it laid out; only the summary is on screen.
  const closed = e => { const d = e.closest('details:not([open])'); return !!d && !e.closest('summary'); };
  const sb0 = document.querySelector('section[data-testid=stSidebar]');
  // Close button BEFORE the loop: scrollIntoView on sidebar items scrolls the
  // sidebar's own content box, which carries its header (and the button) away.
  let closeBtn = null;
  const cb = document.querySelector('[data-testid=stSidebarCollapseButton] button');
  if (sb0.getAttribute('aria-expanded') === 'true' && cb) { const r = cb.getBoundingClientRect(); const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); closeBtn = { uncovered: !!t && (t === cb || cb.contains(t)), top: nameOf(t), rect: [r.left, r.top, r.width, r.height].map(Math.round) }; }
  const els = [...document.querySelectorAll(sel)].filter(e => !e.closest('[data-testid=stBottom],[data-testid=stHeader]') && !closed(e) && vis(e));
  const covered = []; let checked = 0;
  for (const el of els) {
    const H = innerHeight; let r = el.getBoundingClientRect();
    if (r.height > H * 0.45) continue; // taller than the free window: partial cover is scrolling, not hiding
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    r = el.getBoundingClientRect();
    if (r.bottom <= 0 || r.top >= H) continue;
    checked++;
    // Sample each line box: a wrapped inline <code> has a bounding box that also
    // spans its neighbours' text, which is not "covering".
    const pts = [];
    const boxes = getComputedStyle(el).display === 'inline' ? [...el.getClientRects()] : [r];
    for (const b of boxes) for (let i = 1; i <= 3; i++) for (let j = 1; j <= 3; j++) pts.push([b.left + b.width * i / 4, b.top + b.height * j / 4]);
    let bad = 0; const by = new Set();
    for (const [x, y] of pts) {
      if (x < 0 || y < 0 || x >= innerWidth || y >= H) { bad++; by.add('off-viewport'); continue; }
      const t = document.elementFromPoint(x, y);
      const same = t && (t === el || el.contains(t) || t.contains(el));
      if (!same) { bad++; by.add(nameOf(t)); }
    }
    if (bad) covered.push({ el: `${el.tagName}:${label(el)}`, pct: Math.round(100 * bad / pts.length), by: [...by] });
  }
  veils.forEach(v => { v.style.pointerEvents = v.dataset.pe; });
  // Sidebar
  const sb = document.querySelector('section[data-testid=stSidebar]');
  const exp = sb.getAttribute('aria-expanded') === 'true';
  const sr = sb.getBoundingClientRect();
  const bc = document.querySelector('.block-container').getBoundingClientRect();
  const sbFocusable = [...sb.querySelectorAll('button,input,textarea,[tabindex],a,summary,[role=slider]')].filter(e => getComputedStyle(e).visibility !== 'hidden');
  const overlapMain = Math.max(0, Math.min(sr.right, bc.right) - Math.max(sr.left, bc.left)) > 0 && sr.right > 0;
  // Behind an open drawer, ANY descendant that still computes visible is still
  // read and painted (a parent-only visibility:hidden is escaped by a child that
  // declares visibility:visible -- Streamlit's markdown wrapper does).
  const mainEl = document.querySelector('section.stMain');
  const leaks = [...mainEl.querySelectorAll('*'), ...document.querySelectorAll('[data-testid=stBottom] *')]
    .filter(e => getComputedStyle(e).visibility === 'visible' && e.getBoundingClientRect().width > 0 && (e.innerText || '').trim()).length;
  const mainHidden = getComputedStyle(mainEl).visibility === 'hidden' && leaks === 0;
  return {
    checked, covered,
    sidebar: { expanded: exp, rect: [Math.round(sr.left), Math.round(sr.right)], visible_focusables: exp ? undefined : sbFocusable.length, close_button: closeBtn, overlaps_main_column: overlapMain, main_hidden_behind_drawer: exp ? mainHidden : undefined, visible_main_descendants: exp ? leaks : undefined },
  };
};

function geomVerdict(g, width) {
  const issues = [];
  if (g.covered.length) issues.push(`covered: ${g.covered.map(c => `${c.el} ${c.pct}% by ${c.by.join('/')}`).join('; ')}`);
  const s = g.sidebar;
  if (!s.expanded && s.visible_focusables) issues.push(`collapsed sidebar keeps ${s.visible_focusables} visible focusables`);
  if (s.expanded && s.close_button && !s.close_button.uncovered) issues.push(`sidebar close button covered by ${s.close_button.top}`);
  if (s.expanded && width >= 768 && s.overlaps_main_column) issues.push('open sidebar overlaps main column');
  if (s.expanded && width < 768 && !s.main_hidden_behind_drawer) issues.push(`page behind open drawer still visible to AT/Tab (${s.visible_main_descendants} visible text elements)`);
  return issues;
}

// Break-tests: re-introduce each fixed defect; the check must name it.
const BREAKS = {
  no_scroll_padding: "[data-testid='stAppScrollToBottomContainer'],html{scroll-padding:0 !important}",
  veil_on_top: '.drlca-veil{z-index:999 !important}',
  // Higher specificity than the app's own !important rule, which is later in the
  // document and would otherwise win the cascade (the break would not apply).
  // The pre-fix parent-only drawer rule: a descendant re-declares visible.
  drawer_descendant_leak: "html body section.stMain.stMain.stMain .drlca-banner.drlca-banner{visibility:visible !important}",
  sidebar_under_header: "html body section[data-testid='stSidebar'][data-testid]{z-index:2 !important}",
};

// At >= 768 px Streamlit shows the sidebar's close button only on hover or focus
// (keyboard focus reveals it: keyboard pass). Hover first so the check measures
// the button a user can actually see, not its hidden resting state.
async function revealCloseButton(page) {
  if (await sidebarExpanded(page)) { await page.hover('section[data-testid="stSidebar"]'); await page.waitForTimeout(400); }
}

async function runGeometry(browser) {
  // Widths where the geometry flips: 360 (narrowest target), 480/481 (the
  // avatar-stack query), 767/768 (drawer <-> side-by-side), 1280 (desktop).
  const widths = [360, 480, 481, 767, 768, 1280];
  const results = [];
  for (const w of widths) for (const theme of (w === 360 ? ['light', 'hc'] : ['light'])) {
    const { ctx, page } = await openCell(browser, { width: w, theme, dsf: 1 });
    try {
      await ask(page, LEGAL_Q, 'legal');
      for (const sbState of ['as-loaded', 'toggled']) {
        if (sbState === 'toggled') { (await sidebarExpanded(page)) ? await closeSidebar(page) : await openSidebar(page); }
        await revealCloseButton(page);
        const g = await page.evaluate(GEOM);
        const issues = geomVerdict(g, w);
        results.push({ width: w, theme, sidebar: g.sidebar.expanded ? 'open' : 'collapsed', checked: g.checked, issues, raw: g });
        console.log(`geometry ${w} ${theme} sidebar=${g.sidebar.expanded ? 'open' : 'collapsed'} checked=${g.checked} ${issues.length ? 'FAIL ' + issues.join(' | ') : 'OK'}`);
      }
    } finally { await ctx.close(); }
  }
  // Break-tests at 360 (drawer case) and 1280.
  const breaks = [];
  for (const w of [360, 1280]) for (const [name, css] of Object.entries(BREAKS)) {
    const { ctx, page } = await openCell(browser, { width: w, theme: 'light', dsf: 1 });
    try {
      await ask(page, LEGAL_Q, 'legal');
      await page.addStyleTag({ content: css });
      await page.waitForTimeout(300);
      if (name === 'sidebar_under_header' || name === 'drawer_descendant_leak') await openSidebar(page);
      await revealCloseButton(page);
      const g = await page.evaluate(GEOM);
      const issues = geomVerdict(g, w);
      breaks.push({ width: w, break: name, detected: issues.length > 0, issues });
      console.log(`BREAK ${w} ${name}: ${issues.length ? 'DETECTED ' + issues.join(' | ').slice(0, 400) : 'NOT DETECTED'}`);
    } finally { await ctx.close(); }
  }
  fs.writeFileSync(path.join(OUT, 'geometry.json'), JSON.stringify({ results, breaks }, null, 1));
  return { results, breaks };
}

// ---------------------------------------------------------------- contrast
// axe cannot compute contrast over a background IMAGE (the watermark photo) and
// files those nodes as "incomplete", not as violations -- so "0 serious" says
// nothing about them. Measure them instead, from pixels:
//   shot A = the element as rendered; shot B = the same clip with the element's
//   own text made transparent (descendants that set their own colour, e.g. code
//   chips, are untouched and so cancel out). Pixels that differ are where THIS
//   element's glyphs are. Contrast is rendered-glyph vs background at those very
//   pixels, so it includes every overlay (photo, veil, scrim) that is really there.
// Verdict: text colour vs the background behind the glyph-core pixels (see
// below), 2nd percentile >= 4.5 (3 for large text) -- the photo varies under a
// glyph, so a near-worst case, not the average. min and median are reported.
async function measureNode(page, target) {
  const loc = page.locator(target).first();
  if (!(await loc.count())) return { target, error: 'not found' };
  const info = await loc.evaluate(el => {
    el.scrollIntoView({ block: 'center' });
    // getComputedStyle is LIVE: read everything before the text is hidden.
    const cs = getComputedStyle(el);
    const fg = cs.color, px = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 700;
    const r = el.getBoundingClientRect();
    return { fg, px, bold, large: px >= 24 || (bold && px >= 18.66), text: (el.innerText || '').trim().slice(0, 60),
      rect: { x: Math.max(0, r.left), y: Math.max(0, r.top), width: Math.min(r.width, innerWidth - Math.max(0, r.left)), height: Math.min(r.height, innerHeight - Math.max(0, r.top)) } };
  });
  if (!(info.rect.width >= 1 && info.rect.height >= 1)) return { target, ...info, error: 'off-viewport' };
  await page.waitForTimeout(150);
  const shotA = (await page.screenshot({ clip: info.rect })).toString('base64');
  await loc.evaluate(el => {
    const st = document.createElement('style'); st.id = 'drlca-measure'; el.dataset.measure = '1';
    st.textContent = "[data-measure='1']{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important;text-decoration-color:transparent !important}"
      + "[data-measure='1'] *{text-decoration-color:transparent !important}";
    document.head.appendChild(st);
  });
  await page.waitForTimeout(150);
  const shotB = (await page.screenshot({ clip: info.rect })).toString('base64');
  await loc.evaluate(el => { delete el.dataset.measure; document.getElementById('drlca-measure')?.remove(); });
  const stats = await page.evaluate(async ({ a64, b64, fg }) => {
    const load = async b => { const img = new Image(); img.src = 'data:image/png;base64,' + b; await img.decode();
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
      const g = c.getContext('2d'); g.drawImage(img, 0, 0); return g.getImageData(0, 0, c.width, c.height).data; };
    const A = await load(a64), B = await load(b64);
    const lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const L = (d, i) => 0.2126 * lin(d[i]) + 0.7152 * lin(d[i + 1]) + 0.0722 * lin(d[i + 2]);
    // A text pixel is one the element's text colour painted: A = B + k*(F - B),
    // F = the (alpha-composited) text colour over that pixel's background B,
    // 0 < k <= 1 being glyph coverage. Colour emoji and children's own paint do
    // not lie on that line and are excluded. Glyph core = coverage >= 0.6.
    const m = fg.match(/[\d.]+/g).map(Number); const fa = m.length > 3 ? m[3] : 1;
    const core = [], rendered = []; let changed = 0, offLine = 0;
    for (let i = 0; i < A.length; i += 4) {
      const diff = Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]);
      if (diff <= 30) continue;
      changed++;
      const F = [0, 1, 2].map(j => m[j] * fa + B[i + j] * (1 - fa));
      const dv = [0, 1, 2].map(j => F[j] - B[i + j]), av = [0, 1, 2].map(j => A[i + j] - B[i + j]);
      const dd = dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2;
      const k = dd < 1 ? 1 : (av[0] * dv[0] + av[1] * dv[1] + av[2] * dv[2]) / dd;
      const res = Math.sqrt([0, 1, 2].reduce((t, j) => t + (av[j] - k * dv[j]) ** 2, 0));
      if (res > 40 || k > 1.25) { offLine++; continue; }
      if (k < 0.6) continue;
      // WCAG compares the TEXT COLOUR with the background colour, so the verdict
      // ratio is F vs B at this glyph pixel. The rendered (anti-aliased) glyph vs
      // B is kept as information only: anti-aliasing lowers it for any colour.
      const lf = 0.2126 * lin(F[0]) + 0.7152 * lin(F[1]) + 0.0722 * lin(F[2]), lb = L(B, i), la = L(A, i);
      core.push((Math.max(lf, lb) + 0.05) / (Math.min(lf, lb) + 0.05));
      rendered.push((Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05));
    }
    if (!core.length) return { changed, offLine, n: 0 };
    core.sort((x, y) => x - y); rendered.sort((x, y) => x - y);
    return { changed, offLine, n: core.length, p02: core[Math.floor(core.length * 0.02)], min: core[0], median: core[Math.floor(core.length / 2)],
      rendered_median: rendered[Math.floor(rendered.length / 2)] };
  }, { a64: shotA, b64: shotB, fg: info.fg });
  if (!stats.n) return { target, text: info.text, fg: info.fg, changed_px: stats.changed, error: 'no text-colour glyph pixels (text painted by children only)' };
  const need = info.large ? 3 : 4.5;
  return { target, text: info.text, fg: info.fg, px: info.px, large: info.large, need, changed_px: stats.changed, off_line_px: stats.offLine, core_px: stats.n,
    p02: +stats.p02.toFixed(2), min: +stats.min.toFixed(2), median: +stats.median.toFixed(2), rendered_median: +stats.rendered_median.toFixed(2), pass: stats.p02 >= need };
}

async function runContrast(browser) {
  const rows = [];
  for (const cell of CELLS) {
    if (ONLY && !ONLY.includes(cell.id)) continue;
    for (const state of ['empty', 'legal', 'help']) {
      let ctx = null;
      try {
        const o = await openCell(browser, cell); ctx = o.ctx; const page = o.page;
        if (state === 'legal') await ask(page, LEGAL_Q, 'legal');
        if (state === 'help') await ask(page, HELP_Q, 'help');
        const res = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
        const nodes = (res.incomplete.find(v => v.id === 'color-contrast') || { nodes: [] }).nodes;
        for (const n of nodes) {
          if (n.target.length !== 1) { rows.push({ cell: cell.id, state, target: n.target, error: 'in iframe, not measured' }); continue; }
          const m = await measureNode(page, n.target[0]);
          rows.push({ cell: cell.id, state, axe_reason: (n.any[0] || {}).message, ...m });
        }
        const bad = rows.filter(r => r.cell === cell.id && r.state === state && r.pass === false);
        console.log(`contrast ${cell.id.padEnd(20)} ${state.padEnd(6)} incomplete=${nodes.length} fail=${bad.length} ${bad.map(r => `"${r.text}" p02=${r.p02} min=${r.min} median=${r.median} need=${r.need}`).join('; ')}`);
      } catch (e) { rows.push({ cell: cell.id, state, error: String(e) }); console.log(`contrast ${cell.id} ${state} ERROR ${e}`); }
      finally { if (ctx) await ctx.close(); }
    }
  }
  fs.writeFileSync(path.join(OUT, 'contrast_over_image.json'), JSON.stringify(rows, null, 1));
  const fails = rows.filter(r => r.pass === false).length, measured = rows.filter(r => typeof r.pass === 'boolean').length;
  console.log(`CONTRAST-OVER-IMAGE: measured ${measured}, failing ${fails}, unmeasured ${rows.length - measured}`);
}

const browser = await chromium.launch({ executablePath: exePath() });
try {
  await waitHealthy();
  if (MODE === 'matrix' || MODE === 'all') await runMatrix(browser);
  if (MODE === 'keyboard' || MODE === 'all') await runKeyboard(browser);
  if (MODE === 'geometry' || MODE === 'all') await runGeometry(browser);
  if (MODE === 'contrast' || MODE === 'all') await runContrast(browser);
} finally { await browser.close(); }
