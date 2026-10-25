// README media capture: screenshots + a demo video of a LOCAL run.
//   node capture_readme_media.mjs [--base=http://localhost:8504] [--out=D:/NGORAG-hl/docs/media]
// Run it against a local `streamlit run app.py`, never the live site: the demo asks
// questions, and on the live site that would write production telemetry.
// Zero Gemini quota: the AI expander is never opened.
// Output: NN_*.jpg screenshots and demo.webm (encode to mp4/gif with ffmpeg; see README).
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const arg = (k, d) => (process.argv.find(a => a.startsWith(`--${k}=`)) || `--${k}=${d}`).split('=').slice(1).join('=');
const BASE = arg('base', 'http://localhost:8504').replace(/\/$/, '');
const OUT = arg('out', 'D:/NGORAG-hl/docs/media');
// --with-ai: the video also shows the opt-in AI answer in plain language. This SPENDS
// ONE Gemini call (free tier, 20/day/model); a re-run replays the answer cache.
// --video-only: skip the screenshots (keep the committed ones).
const WITH_AI = process.argv.includes('--with-ai');
const VIDEO_ONLY = process.argv.includes('--video-only');
fs.mkdirSync(OUT, { recursive: true });

const shot = (p, name) => p.screenshot({ path: path.join(OUT, name), type: 'jpeg', quality: 82 });
const turns = p => p.locator('[data-testid="stChatMessage"]');

async function ask(p, q, wantText) {
  const n = await turns(p).count();
  const box = p.locator('textarea').first();
  await box.click();
  await box.pressSequentially(q, { delay: 35 });
  await p.keyboard.press('Enter');
  await p.waitForFunction(k => document.querySelectorAll('[data-testid="stChatMessage"]').length >= k + 2, n, { timeout: 90000 });
  await p.waitForFunction(t => document.body.innerText.includes(t), wantText, { timeout: 90000 });
  await p.waitForTimeout(1200);  // let the read-aloud iframe settle before a frame is taken
}

// Streamlit keeps scrolling to the bottom while a turn paints (read-aloud iframe,
// helpful radio), so scroll to the newest answer's heading AFTER that settles.
async function showNewest(p, hold) {
  await p.waitForTimeout(1500);
  for (let i = 0; i < 2; i++) {
    await p.evaluate(() => {
      const t = [...document.querySelectorAll('[data-testid="stChatMessage"]')].pop();
      const h = t && (t.querySelector('h3') || t);
      h.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
    await p.waitForTimeout(700);
  }
  await p.waitForTimeout(hold);
}

const b = await chromium.launch();

// --- 1. Screenshots (1280x800 desktop + one 390 phone frame) -------------------
if (!VIDEO_ONLY) {
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto(BASE + '/'); await p.waitForSelector('.drlca-banner');
  await p.waitForFunction(() => document.body.innerText.includes('not legal advice'));
  await shot(p, '01_landing.jpg');

  await ask(p, "Can I be denied employment because of my disability?", 'Retrieved excerpts');
  await turns(p).last().scrollIntoViewIfNeeded();
  await p.evaluate(() => { const t = [...document.querySelectorAll('[data-testid="stChatMessage"]')].pop(); t.scrollIntoView({ block: 'start' }); });
  await p.waitForTimeout(400);
  await shot(p, '02_legal_answer_citations.jpg');

  await ask(p, "I'm deaf and live in Lagos. Who can help me?", 'Help near you');
  await p.evaluate(() => { const t = [...document.querySelectorAll('[data-testid="stChatMessage"]')].pop(); t.scrollIntoView({ block: 'start' }); });
  await p.waitForTimeout(400);
  await shot(p, '03_help_organisations.jpg');

  await p.getByRole('radio', { name: 'Hausa' }).click({ force: true });
  await p.waitForFunction(() => document.body.innerText.includes('Layin taimako na ƙasa:'));
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.locator('[data-testid="stAppScrollToBottomContainer"]').evaluate(e => e.scrollTo(0, 0)).catch(() => {});
  await p.waitForTimeout(800);
  await shot(p, '04_hausa_interface.jpg');
  await p.getByRole('radio', { name: 'English' }).click({ force: true });
  await p.waitForFunction(() => document.body.innerText.includes('National helpline:'));
  await p.getByRole('checkbox', { name: 'High contrast mode' }).click({ force: true });
  await p.waitForSelector('.drlca-hc-on', { state: 'attached' });
  await p.waitForTimeout(1200);
  await shot(p, '05_high_contrast.jpg');
  await p.close();
}
if (!VIDEO_ONLY) {
  // Phone width: the sidebar starts collapsed, so this is what a phone user sees first.
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await p.goto(BASE + '/'); await p.waitForSelector('.drlca-banner');
  await p.waitForFunction(() => document.body.innerText.includes('not legal advice'));
  await p.locator('h1').first().scrollIntoViewIfNeeded();
  await p.evaluate(() => document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0; }));
  await p.waitForTimeout(800);
  await shot(p, '06_phone.jpg');
  await p.close();
}

// --- 2. Demo video (1280x720, one continuous session) --------------------------
{
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 },
                                   recordVideo: { dir: OUT, size: { width: 1280, height: 720 } } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/'); await p.waitForSelector('.drlca-banner');
  await p.waitForFunction(() => document.body.innerText.includes('not legal advice'));
  await p.waitForTimeout(2500);                                   // helplines + notice
  if (WITH_AI) {
    await p.getByRole('checkbox', { name: 'Explain in plain language' }).click({ force: true });
    await p.waitForTimeout(1200);
  }
  await ask(p, "Can I be denied employment because of my disability?", 'Retrieved excerpts');
  await showNewest(p, 3000);                                      // the cited excerpts
  if (WITH_AI) {
    const turn = p.locator('[data-testid="stChatMessage"]').last();
    await turn.getByText('Answer with AI').click();
    const go = turn.getByRole('button', { name: 'Generate AI answer' });
    await go.scrollIntoViewIfNeeded(); await p.waitForTimeout(800);
    await go.click();
    // The answer is stored, then the app reruns and the expander re-mounts CLOSED:
    // wait for the button to go, then reopen it to show the answer.
    await go.waitFor({ state: 'detached', timeout: 120000 }).catch(() => {});
    await p.waitForTimeout(1500);
    const det = p.locator('[data-testid="stChatMessage"]').last().locator('details').filter({ hasText: 'Answer with AI' });
    if (!(await det.evaluate(d => d.open))) await det.locator('summary').click();
    await p.waitForFunction(() => {
      const t = [...document.querySelectorAll('[data-testid="stChatMessage"]')].pop().innerText;
      return t.includes('Citations:') || t.includes('AI answer unavailable');
    }, null, { timeout: 60000 });
    await p.waitForTimeout(1500);
    const exp = p.locator('[data-testid="stChatMessage"]').last().locator('[data-testid="stExpander"]').last();
    await exp.evaluate(e => e.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    await p.waitForTimeout(1200);
    await p.screenshot({ path: path.join(OUT, '07_ai_plain_answer.jpg'), type: 'jpeg', quality: 82 });
    await p.waitForTimeout(6000);                                 // read the plain answer
  } else {
    await ask(p, 'Do public buildings have to be accessible for wheelchair users?', 'Retrieved excerpts');
    await showNewest(p, 3000);
  }
  await ask(p, "I'm deaf and live in Lagos. Who can help me?", 'Help near you');
  await showNewest(p, 3500);                                      // helpline first, then orgs
  await p.getByRole('radio', { name: 'Hausa' }).click({ force: true });
  await p.waitForFunction(() => document.body.innerText.includes('Layin taimako na ƙasa:'));
  await p.waitForTimeout(2500);
  await p.getByRole('radio', { name: 'Yorùbá' }).click({ force: true });
  await p.waitForTimeout(2500);
  await p.getByRole('radio', { name: 'English' }).click({ force: true });
  await p.waitForTimeout(1200);
  await p.getByRole('checkbox', { name: 'High contrast mode' }).click({ force: true });
  await p.waitForSelector('.drlca-hc-on', { state: 'attached' });
  await p.waitForTimeout(3000);
  const v = p.video();
  await ctx.close();
  fs.renameSync(await v.path(), path.join(OUT, 'demo.webm'));
}
await b.close();
console.log('wrote', fs.readdirSync(OUT).join(', '));
