// Post-deploy smoke for the 2026-10-21 a11y fixes on the live site. Asks NO question, so it writes nothing to telemetry.
//   node live_smoke_a11y.mjs [--base=https://ngodisabilityrag.onrender.com]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=https://ngodisabilityrag.onrender.com').slice(7);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(BASE, { timeout: 180000 });
await p.getByText(/National helplines?/).first().waitFor({ timeout: 180000 });
await p.waitForTimeout(4000);
const aria = await p.locator('body').ariaSnapshot();
await p.keyboard.press('Tab');
const skip = await p.evaluate(() => {
  const a = document.getElementById('drlca-skip'); if (!a || document.activeElement !== a) return 'not-focused';
  const r = a.getBoundingClientRect(); const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { onTop: top === a || a.contains(top), text: a.textContent };
});
await p.keyboard.press('Enter'); await p.waitForTimeout(500);
const h1Focused = await p.evaluate(() => document.activeElement && document.activeElement.tagName === 'H1');
const sb = p.getByTestId('stSidebar');
// Scope to the route group: the language switcher (2026-10-25) is now the first sidebar radio.
const rg = sb.locator('[data-testid="stRadio"]', { hasText: 'How should I handle' });
const radio = rg.getByRole('radio', { checked: true }).first();
const routeBefore = await radio.evaluate(e => (e.closest('label') || e).innerText.trim());
await radio.focus(); await p.keyboard.press('ArrowUp'); await p.waitForTimeout(3000);
const routeAfter = await rg.getByRole('radio', { checked: true }).first().evaluate(e => (e.closest('label') || e).innerText.trim());
const focusAfter = await p.evaluate(() => document.activeElement && document.activeElement.tagName + ':' + document.activeElement.type);
const caption = (await sb.innerText()).match(/Next question: (\w+)/)?.[1];
const text = await p.locator('body').innerText();
console.log(JSON.stringify({
  // 2026-10-25: toll-free only (WhatsApp removed by the owner, not found on drac-ng.org).
  helplinesOnPage: text.includes('08000-3000-100') && !/WhatsApp/.test(text),
  sliderSingleName: /slider "Text size"/.test(aria) && !/slider "Text size Text size"/.test(aria),
  mainLandmark: /main "Helplines and answers"/.test(aria), settingsRegion: /region "Settings"/.test(aria),
  skip, h1Focused, routeBefore, routeAfter, focusAfter, caption, pageErrors: errs,
}, null, 1));
await b.close();
