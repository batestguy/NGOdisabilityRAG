// H3b: deterministic check that each candidate's phone is ON its official page.
// Loads every source URL in a real browser (no summarising fetch), collects the
// rendered text plus tel:/wa.me/whatsapp links, and matches phones on their last
// 10 digits. Also reports whether disability words appear on the page.
//   node verify_ngo_sources.mjs <candidates.json> <out.json>
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [inFile, outFile] = process.argv.slice(2);
const cands = JSON.parse(fs.readFileSync(inFile, 'utf8'));
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const b = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const ctx = await b.newContext({ ignoreHTTPSErrors: false, userAgent:
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' });
const last10 = s => s.replace(/\D/g, '').slice(-10);
const DIS = /disab|deaf|blind|autis|cerebral|albin|special needs|mental health|impair|wheelchair|inclusion/i;
const out = [];
for (const c of cands) {
  const rec = { name: c.name, pages: [], phones: {} };
  for (const url of c.urls) {
    const p = await ctx.newPage();
    try {
      const resp = await p.goto(url, { timeout: 45000, waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(3500);
      const text = await p.evaluate(() => document.body.innerText);
      const links = await p.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => a.href)
        .filter(h => /^(tel:|https?:\/\/(wa\.me|api\.whatsapp\.com))/i.test(h)));
      const digitsText = text.replace(/\D/g, '');
      const digitsLinks = links.join(' ').replace(/\D/g, '');
      for (const ph of c.phones) {
        const k = last10(ph);
        const where = digitsText.includes(k) ? 'text' : digitsLinks.includes(k) ? 'link' : null;
        if (where && !rec.phones[ph]) {
          const i = text.replace(/\s+/g, ' ');
          rec.phones[ph] = { where, url };
        }
      }
      const m = text.match(DIS);
      rec.pages.push({ url, status: resp ? resp.status() : null,
        disabilityWord: m ? text.slice(Math.max(0, m.index - 60), m.index + 80).replace(/\s+/g, ' ') : null });
    } catch (e) {
      rec.pages.push({ url, error: String(e).split('\n')[0].slice(0, 120) });
    }
    await p.close();
  }
  for (const ph of c.phones) if (!rec.phones[ph]) rec.phones[ph] = null;
  out.push(rec);
  console.log(`${c.name.slice(0, 44).padEnd(44)} ` + c.phones.map(ph => `${ph}=${rec.phones[ph] ? rec.phones[ph].where : 'NOT FOUND'}`).join('  '));
}
fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
await b.close();
