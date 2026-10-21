// Browser check for the H2/H3 leftover minor fixes (2026-10-21), local only.
//   node minor_check.mjs [--base=http://localhost:8502]
// 1 slider has a single name · 2 skip link is first, focuses H1 · 3 main + Settings landmarks
// 4 route buttons expose "(selected)" and the used-up override resets after a turn
// 5 read-aloud text follows the NGO filter · 6 axe: no serious/moderate/minor
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.argv.find(a => a.startsWith('--base=')) || '--base=http://localhost:8502').slice(7);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
const res = {};
await p.goto(BASE, { timeout: 120000 });
await p.getByText('National helplines').first().waitFor({ timeout: 120000 });
await p.waitForTimeout(3000);

res.sliderName = await p.getByRole('slider').first().evaluate(e => e.getAttribute('aria-labelledby') === null && e.getAttribute('aria-label'));
const aria = await p.locator('body').ariaSnapshot();
res.sliderAria = (aria.match(/slider "[^"]*"/) || [null])[0];
res.mainLandmark = /main "Helplines and answers"/.test(aria);
res.settingsRegion = /region "Settings"/.test(aria);

const skipOnTop = async () => p.evaluate(() => {
  const a = document.getElementById('drlca-skip'); if (!a || document.activeElement !== a) return 'not-focused';
  const r = a.getBoundingClientRect(); const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const cs = getComputedStyle(a);
  return { onTop: top === a || a.contains(top), fg: cs.color, bg: cs.backgroundColor, outline: cs.outlineStyle + ' ' + cs.outlineWidth };
});
await p.keyboard.press('Tab');
res.skipVisible1280 = await skipOnTop();
res.firstTabStop = await p.evaluate(() => document.activeElement && document.activeElement.textContent);
await p.keyboard.press('Enter');
await p.waitForTimeout(500);
res.skipFocusesH1 = await p.evaluate(() => document.activeElement && document.activeElement.tagName === 'H1');

const sb = p.getByTestId('stSidebar');
const checked = async () => (await sb.getByRole('radio', { checked: true }).first().getAttribute('aria-label'))
  || (await sb.getByRole('radio', { checked: true }).first().evaluate(e => (e.closest('label') || e).innerText.trim()));
res.routeDefault = await checked();
// Keyboard: focus the checked radio, ArrowUp moves to "Find help near me"; focus must stay on a radio.
await sb.getByRole('radio', { checked: true }).first().focus();
await p.keyboard.press('ArrowUp');
await p.waitForTimeout(2500);
res.routeAfterKey = await checked();
res.focusAfterKey = await p.evaluate(() => { const e = document.activeElement; return e ? e.tagName + ':' + (e.getAttribute('type') || '') : null; });
res.routeAfterClick = res.routeAfterKey;
res.captionAfterClick = (await sb.innerText()).match(/Next question: (\w+)/)?.[1];

const ta = p.getByTestId('stChatInputTextArea');
await ta.fill('I need help in Lagos'); await ta.press('Enter');
const t = p.locator('[data-testid="stChatMessage"]').nth(1);
await t.locator('iframe[title*="Read answer aloud"]').waitFor({ timeout: 120000 });
await p.waitForTimeout(2500);
res.routeAfterTurn = await checked();
res.captionAfterTurn = (await sb.innerText()).match(/Next question: (\w+)/)?.[1];
res.turnWasHelp = (await t.innerText()).includes('Help near you');

const speech = async () => {
  const f = t.locator('iframe[title*="Read answer aloud"]');
  const src = await f.getAttribute('srcdoc');
  const m = src && src.match(/Help contacts: ([^\\"\n]*)/);
  return m ? m[1] : null;
};
res.speechBefore = await speech();
await t.locator('summary', { hasText: 'Filter or sort' }).click();
await p.waitForTimeout(800);
let opts = [];
for (let i = 0; i < 4 && !opts.length; i++) {  // the popover sometimes misses the first click
  await t.getByRole('combobox', { name: /State/ }).click();
  await p.waitForTimeout(800);
  opts = await p.getByRole('option').allInnerTexts();
}
const pick = opts.find(o => /Kano|Oyo|Abuja|FCT|Rivers|Enugu/.test(o)) || opts[opts.length - 1];
await p.getByRole('option', { name: pick, exact: true }).click();
await p.waitForTimeout(3000);
res.filterPicked = pick;
res.speechAfter = await speech();
const shownNames = await t.locator('strong').allInnerTexts();
res.speechMatchesShown = !!res.speechAfter && res.speechAfter !== res.speechBefore;
res.shownStrong = shownNames.slice(0, 8);

const axeW = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
res.axeWcag = axeW.violations.map(v => v.id + ':' + v.impact + ':' + v.nodes.length);  // same tags as h3a/h7 baseline
const axe = await new AxeBuilder({ page: p }).analyze();  // + best-practice, for information
res.axe = axe.violations.map(v => v.id + ':' + v.impact + ':' + v.nodes.length);
res.axeNodes = axe.violations.filter(v => v.impact !== 'critical').map(v => v.id + ' -> ' + v.nodes.map(n => n.target.join(' ') + ' :: ' + n.html.slice(0, 140)).join(' | '));
// Routing trap: "Switch to legal" re-answers the last turn on LEGAL; the radio then shows Auto again.
await p.getByRole('button', { name: /Switch to legal/ }).last().click();
await p.waitForTimeout(6000);
const lastTurn = p.locator('[data-testid="stChatMessage"]').last();
res.trapReansweredLegal = (await lastTurn.innerText()).includes('Your rights');
res.trapTurnCount = await p.locator('[data-testid="stChatMessage"]').count();
res.routeAfterTrap = await checked();

// Skip link at phone width and in high-contrast mode.
await p.setViewportSize({ width: 390, height: 844 });
await p.goto(BASE); await p.getByText('National helplines').first().waitFor({ timeout: 120000 }); await p.waitForTimeout(2500);
await p.keyboard.press('Tab');
res.skipVisible390 = await skipOnTop();
await p.setViewportSize({ width: 1280, height: 900 });
await p.goto(BASE); await p.getByText('National helplines').first().waitFor({ timeout: 120000 }); await p.waitForTimeout(2500);
await p.getByTestId('stSidebar').getByText('High contrast mode').click(); await p.waitForTimeout(2500);
await p.evaluate(() => document.activeElement && document.activeElement.blur());
await p.evaluate(() => document.getElementById('drlca-skip').focus());
res.skipVisibleHC = await skipOnTop();
await p.screenshot({ path: path.join(process.env.TEMP || '.', 'drlca_skip_hc.png'), clip: { x: 0, y: 0, width: 500, height: 90 } });
res.pageErrors = errs;
console.log(JSON.stringify(res, null, 1));
await b.close();
