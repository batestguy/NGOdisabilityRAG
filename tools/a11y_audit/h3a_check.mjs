// H3a browser check: filter/sort on a help turn, per-turn isolation, axe on the result.
//   node h3a_check.mjs [--base=http://localhost:8501]
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=http://localhost:8501').slice(7);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(BASE); await p.getByText(/National helplines?/).first().waitFor({ timeout: 60000 });
const msgs = p.locator('[data-testid="stChatMessage"]');
async function ask(q) {
  const n = await msgs.count();
  const ta = p.getByTestId('stChatInputTextArea'); await ta.fill(q); await ta.press('Enter');
  await p.waitForFunction(k => document.querySelectorAll('[data-testid="stChatMessage"]').length >= k + 2, n, { timeout: 60000 });
  await p.waitForTimeout(2500);
}
const orgNames = async turn => (await turn.locator('strong').allInnerTexts())
  .filter(t => !/^(Showing|Filtered|National helplines?)/.test(t));
async function pick(turn, label, option) {
  await turn.getByLabel(label).click();                       // opens the combobox
  await p.getByRole('option', { name: option, exact: true }).click();
  await p.waitForTimeout(2000);
}

await ask('I need an organisation that can help me in Lagos');
let t1 = msgs.nth(1);
const before = await orgNames(t1);
await t1.locator('summary', { hasText: 'Filter or sort' }).click(); await p.waitForTimeout(800);
await pick(t1, 'Disability type', 'Hearing');
t1 = msgs.nth(1);
const hearing = await orgNames(t1);
const t1text = await t1.innerText();
const hlFirst = t1text.indexOf('08000-3000-100') > -1 && t1text.indexOf('08000-3000-100') < t1text.indexOf('Filtered');

await ask('Find blind support in Lagos');
const t2before = await orgNames(msgs.nth(3));
t1 = msgs.nth(1);
const summary1 = t1.locator('summary', { hasText: 'Filter or sort' });
if (!(await summary1.evaluate(s => s.parentElement.open))) await summary1.click();
await t1.getByText('Name (A to Z)').click(); await p.waitForTimeout(2000);
const t1sorted = await orgNames(msgs.nth(1));
const t2after = await orgNames(msgs.nth(3));

const axe = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
console.log(JSON.stringify({
  before, hearing, helplinesBeforeFilteredList: hlFirst,
  turn1SortedByName: t1sorted, turn2Untouched: JSON.stringify(t2before) === JSON.stringify(t2after), turn2: t2after,
  axe: axe.violations.map(v => `${v.id}(${v.impact},${v.nodes.length})`),
  pageErrors: errs.length,
}, null, 1));
await b.close();
