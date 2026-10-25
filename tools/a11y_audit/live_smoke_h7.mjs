// Post-deploy smoke for H7 on the live site (read-only; never clicks "helpful", never opens the AI expander).
// One legal question = one counts-only turn line in Render's logs; no helpful line is produced.
//   node live_smoke_h7.mjs [--base=https://ngodisabilityrag.onrender.com]
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
await p.waitForTimeout(3000);
const sidebar = p.getByTestId('stSidebar');
const optIn = sidebar.getByRole('checkbox', { name: 'Also share the words of my questions' });
const ta = p.getByTestId('stChatInputTextArea');
await ta.fill('What are the penalties under the Act?'); await ta.press('Enter');
const t = p.locator('[data-testid="stChatMessage"]').nth(1);
await t.locator('iframe[title*="Read answer aloud"]').waitFor({ timeout: 180000 });
await p.waitForTimeout(2000);
const noteSeen = await t.getByText('Not your question and not your conversation').first().waitFor({ timeout: 30000 }).then(() => true, () => false);
const txt = await t.innerText();
const radios = t.getByRole('radiogroup', { name: 'Was this answer helpful?' }).getByRole('radio');
console.log(JSON.stringify({
  helplinesFirst: txt.indexOf('08000-3000-100') > -1 && txt.indexOf('08000-3000-100') < txt.indexOf('[Act cl.'),
  actTags: (txt.match(/\[Act cl\. \d+\]/g) || []).length,
  helpfulRadios: await radios.count(),
  noneSelected: (await Promise.all((await radios.all()).map(r => r.isChecked()))).every(c => !c),
  privacyNote: txt.includes('Not your question and not your conversation'), noteSeen,
  optInPresent: await optIn.count(), optInOff: (await optIn.count()) ? !(await optIn.isChecked()) : null,
  pageErrors: errs,
}, null, 1));
await b.close();
