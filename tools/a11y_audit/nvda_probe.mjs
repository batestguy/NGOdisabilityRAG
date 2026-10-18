// NVDA probe for the H2 owner checklist (docs/accessibility.md §7 A).
// Drives a headed Chrome with Playwright, sends NVDA gestures as OS-level keys
// (oskeys.py), and slices NVDA's IO log (--log-level=12) into per-step speech.
//
//   node nvda_probe.mjs --log=<nvda.log> --keys=<oskeys.py> --out=<dir> [--steps=a1,a2,...]
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)=?(.*)$/); return m ? [m[1], m[2] || true] : [a, true];
}));
const BASE = args.base || 'http://localhost:8501';
const LOG = args.log, KEYS = args.keys, OUT = args.out || '.';
const PY = 'C:\\conda-envs\\drlca-rag\\python.exe';
const STEPS = args.steps ? String(args.steps).split(',') : null;
fs.mkdirSync(OUT, { recursive: true });

const sleep = ms => new Promise(r => setTimeout(r, ms));
// --title guard: oskeys refuses (exit 3) unless the DRLCA window is focused
const os = (...chords) => execFileSync(PY, [KEYS, '--title=DRLCA', ...chords]);
const mark = () => fs.statSync(LOG).size;
function spoken(from) {
  const fd = fs.openSync(LOG, 'r'); const len = fs.statSync(LOG).size - from;
  const buf = Buffer.alloc(Math.max(len, 0)); fs.readSync(fd, buf, 0, buf.length, from); fs.closeSync(fd);
  return buf.toString('utf8').split(/\r?\n/).filter(l => l.startsWith('Speaking ')).map(l => l.slice(9));
}
const results = {};
async function step(name, fn) {
  if (STEPS && !STEPS.includes(name)) return;
  const m = mark(); await fn(); await sleep(800);
  results[name] = spoken(m);
  console.log(`\n=== ${name} (${results[name].length} utterances)`);
  for (const s of results[name]) console.log('  ' + s.slice(0, 220));
}

const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const browser = await chromium.launch({ headless: false, executablePath: fs.existsSync(exe) ? exe : undefined,
  args: ['--force-renderer-accessibility', '--window-position=0,0', '--window-size=1300,900'] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
await page.goto(BASE); await page.getByText('National helplines').first().waitFor({ timeout: 60000 });
await sleep(3000);
await page.bringToFront();
// real OS click on the page body so the Chrome window is foreground for NVDA
await page.locator('h1').first().waitFor({ state: 'visible', timeout: 30000 });
const box = await page.locator('h1').first().boundingBox();
await page.mouse.click(box.x + 5, box.y + box.height + 120);
await sleep(1500);

// leave focus mode first (a focused textarea turns say-all into "blank")
const sayAll = async ms => {
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await sleep(800); os('escape', 'control+home', 'sleep:0.5', 'insert+down'); await sleep(ms); os('control');
};
const ask = async q => {
  const ta = page.getByTestId('stChatInputTextArea');
  await ta.focus(); await ta.fill(q); await sleep(300); await ta.press('Enter');
  await page.locator('[data-testid="stChatMessage"]').last().getByText('National helplines').waitFor({ timeout: 60000 });
};

await step('a1_load_sayall', () => sayAll(+(args.a1ms || 25000)));
await step('a2_announce', async () => { await ask('What are the penalties under the Act?'); await sleep(8000); });
await step('a3_turn_sayall', () => sayAll(+(args.a3ms || 60000)));
await step('a4_fold', async () => {
  const s = page.locator('summary', { hasText: 'more excerpt' }).last();
  await s.focus(); await sleep(1500); os('enter'); await sleep(2500);
  os('down', 'down', 'down', 'down', 'down', 'down', 'down', 'down'); await sleep(6000);
  await s.focus(); await sleep(800); os('enter'); await sleep(2000);
});
await step('a5_sidebar_tab', async () => {
  await page.getByRole('checkbox', { name: 'High contrast mode' }).focus(); await sleep(2500);
  for (let i = 0; i < 12; i++) { await page.keyboard.press('Tab'); await sleep(1800); }
});
await step('a6_help', async () => {
  await ask('I need an organisation that can help me in Lagos'); await sleep(3000);
  const msgs = page.locator('[data-testid="stChatMessage"]');
  await msgs.last().scrollIntoViewIfNeeded();
  // read the last assistant turn from its first line: focus it, then say-all from caret
  await msgs.last().evaluate(e => { e.tabIndex = -1; e.focus(); });
  await sleep(1500); os('insert+down'); await sleep(35000); os('control');
});

fs.writeFileSync(path.join(OUT, 'nvda_speech.json'), JSON.stringify(results, null, 1));
await browser.close();
