// Post-deploy smoke of the live site (read-only; never opens the AI expander).
//   node live_smoke.mjs [--base=https://ngodisabilityrag.onrender.com]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=https://ngodisabilityrag.onrender.com').slice(7);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(BASE, { timeout: 180000 });
await p.getByText('National helplines').first().waitFor({ timeout: 180000 });
await p.waitForTimeout(3000);
const det = p.locator('details', { has: p.locator('summary', { hasText: 'Voice input' }) });
await det.locator('summary').click(); await p.waitForTimeout(2000);
const disclosure = await p.getByText("Google's speech service").count() > 0;
const ta = p.getByTestId('stChatInputTextArea');
await ta.fill('What are the penalties under the Act?'); await ta.press('Enter');
await p.locator('[data-testid="stChatMessage"]').nth(1).waitFor({ timeout: 120000 });
// a cold instance builds the legal index first; the turn is done when its read-aloud renders
await p.locator('[data-testid="stChatMessage"]').nth(1).locator('iframe[title*="Read answer aloud"]').waitFor({ timeout: 180000 });
await p.waitForTimeout(3000);
const turn = await p.locator('[data-testid="stChatMessage"]').nth(1).innerText();
const cdp = await p.context().newCDPSession(p);
const { nodes } = await cdp.send('Accessibility.getFullAXTree');
const leaks = nodes.filter(n => !n.ignored && n.name && /\b(keyboard_[a-z_]+|smart_toy)\b/.test(n.name.value)).length;
console.log(JSON.stringify({
  disclosure,
  helplinesLeadTurn: turn.indexOf('08000-3000-100') > -1 && turn.indexOf('08000-3000-100') < turn.indexOf('Your rights'),
  liveRegion: await p.locator('#drlca-live').textContent().catch(() => null),
  ligatureLeaks: leaks,
  tagsShown: (await p.locator('[data-testid="stChatMessage"]').nth(1).evaluate(e => e.textContent.match(/\[(?:Act cl\.|Constitution s\.|Factsheet Section) [^\]]+\]/g) || [])).length,
  pageErrors: errs.length,
}, null, 1));
await b.close();
