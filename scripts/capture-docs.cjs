// Render the real UI with committed synthetic fixtures; never read personal sessions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const {playwright} = require('../skills/shortlist/scripts/instagram-browser.cjs');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'docs/images');

(async () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'shortlist-docs-'));
  let browser;
  try {
    fs.mkdirSync(output, {recursive: true});
    for (const name of ['dinner', 'dinner-pt-BR']) {
      const fixture = path.join(root, 'examples', name + '.json');
      const data = JSON.parse(fs.readFileSync(fixture, 'utf8'));
      assert.equal(data.demo, true);
      for (const candidate of data.candidates) {
        assert(new URL(candidate.url).hostname.endsWith('.invalid'));
        for (const check of Object.values(candidate.checks)) {
          assert(check.evidence.every(e => new URL(e.url).hostname.endsWith('.invalid')));
        }
      }
      const saved = JSON.parse(execFileSync('python3', [
        path.join(root, 'skills/shortlist/scripts/session.py'), 'save', fixture,
        '--directory', path.join(work, 'sessions')
      ], {encoding: 'utf8'}));
      const fragment = path.join(work, name + '.fragment.html');
      execFileSync('python3', [path.join(root, 'skills/shortlist/scripts/session.py'),
        'render', path.join(work, 'sessions', saved.id + '.json'), fragment]);
      fs.writeFileSync(path.join(work, name + '.html'), `<!doctype html>
        <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Shortlist · fictional demo</title><style>
        :root {color-scheme:light dark}
        body {margin:0;padding:32px;background:light-dark(#eee9f5,#110e17)}
        main {max-width:1080px;margin:auto}
        @media(max-width:650px){body{padding:12px}}
        </style></head><body><main>${fs.readFileSync(fragment, 'utf8')}</main></body></html>`);
    }
    browser = await playwright().chromium.launch({headless: true, channel: 'chrome'});
    const page = await browser.newPage({viewport: {width: 1144, height: 1000}, deviceScaleFactor: 2, colorScheme: 'light'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(work, 'dinner.html')).href);
    assert.equal(await page.locator('[data-detail] h3').innerText(), 'Jardim da Mesa');
    assert.match(await page.locator('[data-saved]').innerText(), /Casa Aurora/);
    assert.match(await page.locator('[data-progress]').innerText(), /1 excluded/);
    await page.screenshot({path: path.join(output, 'evidence-desk.png'), fullPage: true});
    await page.emulateMedia({colorScheme: 'dark'});
    await page.locator('[data-list] [data-id="mesa-27"]').click();
    assert.match(await page.locator('[data-detail]').innerText(), /Verification lead · still unknown/);
    await page.locator('[data-detail] summary').click();
    assert.match(await page.locator('[data-detail]').innerText(), /Friday reservation calendar/);
    await page.screenshot({path: path.join(output, 'evidence-detail.png'), fullPage: true});
    await page.emulateMedia({colorScheme: 'light'});
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(pathToFileURL(path.join(work, 'dinner-pt-BR.html')).href);
    assert.equal(await page.getByRole('button', {name: 'Salvar →', exact: true}).count(), 1);
    assert.match(await page.locator('[data-mode]').innerText(), /opções fictícias/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path: path.join(output, 'portuguese-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS: actual UI, synthetic-only fixtures, English/Portuguese, light/dark, evidence lead, and narrow layout. Screenshots: docs/images/');
  } finally {
    if (browser) await browser.close();
    fs.rmSync(work, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
