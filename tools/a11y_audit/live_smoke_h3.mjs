// Post-deploy smoke for H3 on the live site (read-only; never opens the AI expander).
//   node live_smoke_h3.mjs [--base=https://ngodisabilityrag.onrender.com]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=https://ngodisabilityrag.onrender.com').slice(7);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(BASE, { timeout: 180000 });
await p.getByText('National helplines').first().waitFor({ timeout: 180000 });
await p.waitForTimeout(3000);
const ta = p.getByTestId('stChatInputTextArea');
await ta.fill('I need autism support for my son in Owerri'); await ta.press('Enter');
const t = p.locator('[data-testid="stChatMessage"]').nth(1);
await t.locator('iframe[title*="Read answer aloud"]').waitFor({ timeout: 180000 });
await p.waitForTimeout(2000);
const txt = await t.innerText();
const filterControls = await t.locator('summary', { hasText: 'Filter or sort' }).count();
console.log(JSON.stringify({
  olgShown: txt.includes('OLG Autism'), nenesShown: txt.includes("Nene's Centre"),
  helplinesFirst: txt.indexOf('08000-3000-100') > -1 && txt.indexOf('08000-3000-100') < txt.indexOf('OLG'),
  filterControls, liveRegion: await p.locator('#drlca-live').textContent().catch(() => null),
  pageErrors: errs.length,
}, null, 1));
await b.close();
