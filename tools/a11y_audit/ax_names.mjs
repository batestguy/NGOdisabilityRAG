// Computed accessible names (Chrome's own AX tree via CDP): no OS keystrokes, no
// screen reader. Flags any Material icon ligature that still reaches the tree.
//   node ax_names.mjs [--width=1280]
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const width = +((process.argv.find(a => a.startsWith('--width=')) || '--width=1280').split('=')[1]);
const exe = path.join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const browser = await chromium.launch({ executablePath: fs.existsSync(exe) ? exe : undefined });
const page = await (await browser.newContext({ viewport: { width, height: 800 } })).newPage();
await page.goto('http://localhost:8501'); await page.getByText('National helplines').first().waitFor({ timeout: 60000 });
const ta = page.getByTestId('stChatInputTextArea');
await ta.fill('I need an organisation that can help me in Lagos'); await ta.press('Enter');
await page.locator('[data-testid="stChatMessage"]').nth(1).waitFor({ timeout: 60000 });
await page.waitForTimeout(3000);
const cdp = await page.context().newCDPSession(page);
const { nodes } = await cdp.send('Accessibility.getFullAXTree');
const LIG = /\b(keyboard_[a-z_]+|smart_toy|face|expand_more|chevron_[a-z]+)\b/;
const named = nodes.filter(n => !n.ignored && n.name && n.name.value);
const leaks = named.filter(n => LIG.test(n.name.value)).map(n => `${n.role.value}: ${n.name.value.slice(0, 70)}`);
const pick = re => named.filter(n => re.test(n.name.value)).map(n => `${n.role.value}: ${n.name.value.slice(0, 70)}`);
console.log(JSON.stringify({
  width,
  ligatureLeaks: [...new Set(leaks)],
  avatars: pick(/^(You asked|Assistant answered)$/),
  sidebarButtons: pick(/^(Close sidebar|Open sidebar)$/),
  expanders: pick(/excerpt\(s\)|Voice input|Answer with AI/),
  liveRegion: nodes.filter(n => n.role && n.role.value === 'status').length,
}, null, 1));
await browser.close();
