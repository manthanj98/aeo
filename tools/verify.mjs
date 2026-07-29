/**
 * Verification harness for the Acme dashboard artifact.
 *
 * Renders dist/pepper-project.standalone.html in headless Chromium over file://
 * (no network required) and runs three groups of checks:
 *
 *   1. Baseline gates   — every tab and drawer renders with no page errors, no
 *                         unresolved {{ }} bindings and no undefined/NaN text.
 *   2. Regressions      — one targeted assertion per fixed bug.
 *   3. Responsive       — no horizontal page scroll at 1440 / 900 / 480px.
 *
 *   node tools/verify.mjs [--shots]     --shots also writes screenshots
 */
import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const TARGET = 'file://' + path.join(ROOT, 'dist', 'pepper-project.standalone.html');
const SHOTS = path.join(ROOT, 'dist', 'shots');
const WANT_SHOTS = process.argv.includes('--shots');
const CHROME = process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const TABS = ['Performance', 'Insights', 'Pages', 'Prompts', 'Keywords',
              'Competitors', 'Sitemaps', 'Backlinks', 'Brand Guidelines'];

const results = [];
const pass = (n, d = '') => results.push({ ok: true, n, d });
const fail = (n, d = '') => results.push({ ok: false, n, d });
const check = (ok, n, d = '') => (ok ? pass(n, d) : fail(n, d));

if (WANT_SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });

/** Fresh page with a page-error sink attached. */
async function newPage(width = 1440, height = 950) {
  const page = await browser.newPage({ viewport: { width, height } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e.message)));
  await page.goto(TARGET, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.nav-item', { timeout: 20000 });
  await page.waitForTimeout(600);
  return { page, errors };
}

/** Unresolved bindings / placeholder leakage in the *rendered* DOM. */
async function domHealth(page) {
  return page.evaluate(() => {
    // Ignore the inlined runtime's own source text.
    const scoped = document.querySelector('.app');
    const html = scoped ? scoped.outerHTML : '';
    const braces = [...new Set([...html.matchAll(/\{\{[^}]{0,60}\}\}/g)].map(m => m[0]))];
    const text = scoped ? scoped.innerText : '';
    const junk = [...new Set(text.match(/undefined|NaN|\[object Object\]/g) || [])];
    return { braces, junk };
  });
}

// ───────────────────────────────────────────────── 1. baseline gates
{
  const { page, errors } = await newPage();
  for (const tab of TABS) {
    await page.click(`.nav-item:has-text("${tab}")`);
    await page.waitForTimeout(450);
    const { braces, junk } = await domHealth(page);
    check(braces.length === 0, `tab renders without unresolved bindings: ${tab}`, braces.join(' '));
    check(junk.length === 0, `tab renders without undefined/NaN: ${tab}`, junk.join(' '));
    if (WANT_SHOTS) await page.screenshot({ path: path.join(SHOTS, `tab-${tab.replace(/ /g, '-')}.png`), fullPage: true });
  }

  // Drawers: insight detail, insight draft, page inspect.
  await page.click('.nav-item:has-text("Insights")');
  await page.waitForTimeout(400);
  for (const [label, sel] of [['insight detail', 'text=/View detailed breakdown/'],
                              ['insight draft', 'text=/Draft article|Update article/']]) {
    const el = page.locator(sel).first();
    if (await el.count()) {
      await el.click();
      await page.waitForTimeout(600);
      const { braces, junk } = await domHealth(page);
      check(braces.length === 0 && junk.length === 0, `drawer renders cleanly: ${label}`, [...braces, ...junk].join(' '));
      if (WANT_SHOTS) await page.screenshot({ path: path.join(SHOTS, `drawer-${label.replace(/ /g, '-')}.png`) });
      await page.keyboard.press('Escape').catch(() => {});
      const scrim = page.locator('.scrim').first();
      if (await scrim.count()) await scrim.click({ position: { x: 6, y: 6 } }).catch(() => {});
      await page.waitForTimeout(400);
    } else {
      fail(`drawer renders cleanly: ${label}`, 'trigger not found');
    }
  }

  check(errors.length === 0, 'no uncaught page errors during full tour', errors.join(' | '));
  await page.close();
}

// ───────────────────────────────────────────── 2. per-bug regressions
{
  const { page, errors } = await newPage();

  // Bug 1 — Search Performance and Marketing KPI rows must not overlap.
  await page.click('.nav-item:has-text("Performance")');
  await page.waitForTimeout(500);
  const overlap = await page.evaluate(() => {
    const grids = [...document.querySelectorAll('.kpi-grid')].map(g => g.getBoundingClientRect());
    for (let i = 0; i < grids.length; i++)
      for (let j = i + 1; j < grids.length; j++) {
        const a = grids[i], b = grids[j];
        const vOverlap = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        const hOverlap = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        if (vOverlap > 2 && hOverlap > 2) return { i, j, vOverlap };
      }
    return null;
  });
  check(overlap === null, 'overview KPI grids do not overlap', overlap ? JSON.stringify(overlap) : '');

  // Bug 1b — no element may exceed the content column width.
  const overflow = await page.evaluate(() => {
    const c = document.querySelector('.content');
    return c ? c.scrollWidth - c.clientWidth : 0;
  });
  check(overflow <= 1, 'overview content does not overflow horizontally', `overflow=${overflow}px`);

  // Bug 4 — recommended-competitors panel must disappear once emptied.
  await page.click('.nav-item:has-text("Competitors")');
  await page.waitForTimeout(500);
  for (let i = 0; i < 8; i++) {
    const add = page.locator('.reco-panel .btn:has-text("Add")').first();
    if (!(await add.count())) break;
    await add.click();
    await page.waitForTimeout(300);
  }
  const ghost = await page.evaluate(() => document.querySelector('.app').innerText.includes('Recommended competitors'));
  check(!ghost, 'recommended-competitors panel hides when empty');

  // Bug 5 — mention drawer must keep showing the same mention across filters.
  await page.click('.nav-item:has-text("Prompts")');
  await page.waitForTimeout(400);
  await page.click('text="Prompt Mentions"');
  await page.waitForTimeout(400);
  await page.click('text=/how does Claude decide which brands to cite/');
  await page.waitForTimeout(600);
  const beforeSel = await page.evaluate(() => document.querySelector('.app').innerText.includes('how does Claude decide'));
  const engineSelect = page.locator('select').last();
  await engineSelect.selectOption('Claude').catch(() => {});
  await page.waitForTimeout(600);
  const afterSel = await page.evaluate(() => document.querySelector('.app').innerText.includes('how does Claude decide'));
  check(beforeSel && afterSel, 'mention drawer survives an engine-filter change', `before=${beforeSel} after=${afterSel}`);

  // Bug 6 — a newly added prompt renders a complete row.
  await page.click('text="Your prompts"');
  await page.waitForTimeout(400);
  const addReco = page.locator('.reco-panel .btn:has-text("Add")').first();
  if (await addReco.count()) {
    await addReco.click();
    await page.waitForTimeout(600);
  }
  const newRow = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.trow')];
    const row = rows.find(r => r.innerText.includes('which AI data tool is most secure'));
    return row ? row.innerText.replace(/\n+/g, ' | ') : null;
  });
  check(newRow !== null && !/\|\s*\|/.test(newRow) && newRow.includes('0.0%'),
        'newly added prompt renders a complete row', newRow ?? 'row not found');
  check(newRow !== null && !newRow.includes('Very Low'),
        'newly added prompt shows a dash, not "Very Low", for unknown volume', newRow ?? '');

  // Bug 8 — every "pts" trend value carries one decimal.
  const badPts = await page.evaluate(() =>
    [...new Set((document.querySelector('.app').innerText.match(/[+-]\d+(\.\d+)? pts/g) || [])
      .filter(s => !/\.\d/.test(s)))]);
  check(badPts.length === 0, 'all trend values formatted to one decimal', badPts.join(' '));

  // Bug 9 — reversed dates never produce a negative range label.
  const negRange = await page.evaluate(() => /Last -\d/.test(document.querySelector('.app').innerText));
  check(!negRange, 'no negative date-range label');

  // Bug 10/11 — canonical engine and domain naming.
  await page.click('.nav-item:has-text("Pages")');
  await page.waitForTimeout(500);
  const naming = await page.evaluate(() => {
    const t = document.querySelector('.app').innerText;
    return { bareCopilot: /(^|[^-])\bCopilot\b/.test(t.replace(/Microsoft Co-Pilot/g, '')), legacyDomain: t.includes('acme-seo-geo') };
  });
  check(!naming.bareCopilot, 'engine names are canonical (no bare "Copilot")');
  check(!naming.legacyDomain, 'no legacy acme-seo-geo.com domain');

  // Rebrand — the long product name must be gone everywhere.
  let longName = false;
  for (const tab of TABS) {
    await page.click(`.nav-item:has-text("${tab}")`);
    await page.waitForTimeout(280);
    if (await page.evaluate(() => /Acme SEO\s*&\s*GEO/.test(document.querySelector('.app').innerText))) longName = true;
  }
  check(!longName, 'product is named "Acme" everywhere (no "Acme SEO & GEO")');

  check(errors.length === 0, 'no uncaught page errors during regression pass', errors.join(' | '));
  await page.close();
}

// ─────────────────────────────────────────────────── 3. responsive
for (const width of [1440, 900, 480]) {
  const { page, errors } = await newPage(width, 900);
  await page.click('.nav-item:has-text("Performance")');
  await page.waitForTimeout(500);
  const scrolls = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(!scrolls, `no horizontal page scroll at ${width}px`);
  check(errors.length === 0, `no page errors at ${width}px`, errors.join(' | '));
  if (WANT_SHOTS) await page.screenshot({ path: path.join(SHOTS, `responsive-${width}.png`), fullPage: true });
  await page.close();
}

await browser.close();

// ─────────────────────────────────────────────────────── report
const failed = results.filter(r => !r.ok);
for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.n}${r.d ? `  — ${r.d}` : ''}`);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
