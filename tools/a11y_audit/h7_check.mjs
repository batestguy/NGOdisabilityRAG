// H7 browser check: the helpful control, replay/rerun behaviour, opt-in, clear.
// Reads the server's stdout log for DRLCA_SIGNAL lines between steps.
//   node h7_check.mjs <server-stdout-file> [--base=http://localhost:8501]
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const LOG = process.argv[2];
const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=http://localhost:8501').slice(7);
const signals = () => fs.readFileSync(LOG, 'utf8').split(/\r?\n/).filter(l => l.includes('DRLCA_SIGNAL '))
  .map(l => JSON.parse(l.slice(l.indexOf('DRLCA_SIGNAL ') + 13)));
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
const msgs = p.locator('[data-testid="stChatMessage"]');
async function ask(q) {
  const n = await msgs.count();
  const ta = p.getByTestId('stChatInputTextArea'); await ta.fill(q); await ta.press('Enter');
  await p.waitForFunction(k => document.querySelectorAll('[data-testid="stChatMessage"]').length >= k + 2, n, { timeout: 90000 });
  await p.waitForTimeout(3000);
}
const res = {};
await p.goto(BASE); await p.getByText('National helplines').first().waitFor({ timeout: 60000 });
const s0 = signals().length;
const Q1 = 'What are the penalties under the Act?';
await ask(Q1);
let s = signals().slice(s0);
res.turnLine = s.filter(x => x.kind === 'turn');
res.noTextWithoutOptIn = !JSON.stringify(s).includes('penalties');

const t1 = msgs.nth(1);
await t1.getByRole('radiogroup', { name: /helpful/i }).getByText('Yes', { exact: true }).click();
await p.waitForTimeout(2000);
s = signals().slice(s0);
res.helpfulLine = s.filter(x => x.kind === 'helpful');
res.idsJoin = res.helpfulLine.length === 1 && res.helpfulLine[0].id === res.turnLine[0]?.id;

const s1 = signals().length;   // unrelated rerun: toggle plain language twice
await p.getByRole('checkbox', { name: 'Explain in plain language' }).click({ force: true }); await p.waitForTimeout(1500);
await p.getByRole('checkbox', { name: 'Explain in plain language' }).click({ force: true }); await p.waitForTimeout(1500);
res.rerunEmitsNothing = signals().length === s1;
res.selectionKeptAfterRerun = await msgs.nth(1).getByRole('radio', { name: 'Yes' }).isChecked();

await p.getByRole('checkbox', { name: 'Also share the words of my questions' }).click({ force: true }); await p.waitForTimeout(1500);
const s2 = signals().length;
await ask('I need an organisation that can help me in Lagos');
const after = signals().slice(s2).filter(x => x.kind === 'turn');
res.optInLine = after;
res.optInCarriesText = after.length === 1 && (after[0].q || '').includes('Lagos');

const axe = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
res.axe = axe.violations.map(v => `${v.id}(${v.impact},${v.nodes.length})`);
const cdp = await p.context().newCDPSession(p);
const { nodes } = await cdp.send('Accessibility.getFullAXTree');
res.radioGroups = nodes.filter(n => !n.ignored && n.role?.value === 'radiogroup').map(n => n.name?.value);

await p.getByRole('button', { name: 'Clear conversation' }).click({ force: true }); await p.waitForTimeout(2500);
await ask('What does the Act say about education?');
res.afterClearNothingSelected = !(await msgs.nth(1).getByRole('radio', { name: 'Yes' }).isChecked())
  && !(await msgs.nth(1).getByRole('radio', { name: 'No' }).isChecked());
res.pageErrors = errs.length;
console.log(JSON.stringify(res, null, 1));
await b.close();
