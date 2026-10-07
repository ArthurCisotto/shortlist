// Exercise Claude/browser handoff with no desktop bridge or server.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {playwright} = require('../skills/shortlist/scripts/instagram-browser.cjs');
const root = path.resolve(__dirname, '..');
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'shortlist-standalone-'));
const html = path.join(work, 'view.html');
const source = path.join(work, 'test-restaurant.json');
const helper = path.join(root, 'skills/shortlist/scripts/session.py');
const python = (...args) => execFileSync('python3', args, {cwd: root, encoding: 'utf8', stdio: 'pipe'});
const render = () => python(helper, 'render', source, html, '--standalone');
const prepare = `import runpy,pathlib,sys
m=runpy.run_path('tests/test_session.py'); d=m['example']()
d['title']='Dinner </title><script>window.bad=true</script> & friends'
m['session'].save(d,pathlib.Path(sys.argv[1]))`;

(async () => {
  let browser;
  try {
    python('-c', prepare, work);
    render();
    assert.match(fs.readFileSync(html, 'utf8'), /^<!doctype html>/i);
    browser = await playwright().chromium.launch({headless: true, channel: 'chrome'});
    const page = await browser.newPage({viewport: {width: 1024, height: 1400}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(html).href);
    assert.equal(await page.evaluate(() => typeof window.openai), 'undefined');
    const detail = page.locator('[data-detail]');
    assert.equal(await detail.locator('h3').innerText(), 'Synthetic full');
    await detail.locator('summary').click();
    const link = detail.locator('a[data-source]').first();
    assert.equal(await link.getAttribute('href'), 'https://example.invalid/source');
    assert.equal(await link.getAttribute('target'), '_blank');
    assert.match(await link.getAttribute('rel'), /noopener/);
    const note = 'Keep <script>window.bad=true</script> & compare fees';
    await detail.locator('textarea').fill(note);
    await detail.getByRole('button', {name: 'Save →', exact: true}).click();
    assert.equal(await detail.locator('h3').innerText(), 'Synthetic unknown-pref');
    await detail.getByRole('button', {name: '← Pass', exact: true}).click();
    await page.getByRole('button', {name: 'Refine', exact: true}).click();
    await page.locator('[data-feedback]').fill('More options, same must-haves');
    await page.getByRole('button', {name: 'Save session', exact: true}).click();
    const snapshot = async () => {
      const message = await page.locator('[data-payload]').inputValue();
      assert.match(message, /Shortlist/);
      assert.doesNotMatch(message, /\$shortlist|Codex/);
      assert.equal(await page.locator('[data-fallback]').isVisible(), true);
      return JSON.parse(message.split('\n\nSHORTLIST_ACTION\n')[1]);
    };
    const saved = await snapshot();
    assert.equal(saved.action, 'save');
    assert.deepEqual(saved.decisions, {full: 'save', 'unknown-pref': 'pass'});
    assert.equal(saved.notes.full, note);
    assert.equal(saved.feedback, 'More options, same must-haves');
    assert.match(await page.locator('[data-save-state]').innerText(), /Unsaved/);
    await page.getByRole('button', {name: 'Save & request refinement', exact: true}).click();
    const refined = await snapshot();
    assert.equal(refined.action, 'refine');
    assert.deepEqual(refined.decisions, saved.decisions);
    fs.writeFileSync(path.join(work, 'action.json'), JSON.stringify(refined));
    python(helper, 'apply', path.join(work, 'action.json'), '--directory', work);
    const stored = JSON.parse(fs.readFileSync(source, 'utf8'));
    assert.equal(stored.revision, 2);
    assert.deepEqual(stored.decisions, saved.decisions);
    assert.equal(stored.notes.full, note);
    assert.equal(stored.feedback, saved.feedback);
    // A stale handoff must fail instead of overwriting the acknowledged revision.
    assert.throws(() => python(helper, 'apply', path.join(work, 'action.json'), '--directory', work), /revision/i);
    render();
    await page.reload();
    assert.equal(await page.locator('[data-save-state]').innerText(), 'Saved session');
    assert.match(await page.locator('[data-saved]').innerText(), /Keep <script>/);
    assert.equal(await page.locator('[data-feedback]').inputValue(), saved.feedback);
    assert.equal(await detail.locator('h3').innerText(), 'Synthetic no-pref');
    stored.language = 'pt-BR';
    fs.writeFileSync(source, JSON.stringify(stored));
    render();
    await page.setViewportSize({width: 320, height: 1400});
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('lang'), 'pt-BR');
    await page.getByRole('button', {name: 'Salvar sessão', exact: true}).click();
    assert.equal((await snapshot()).feedback, saved.feedback);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    assert.equal(await page.evaluate(() => window.bad), undefined);
    assert.deepEqual(errors, []);
    console.log('PASS: standalone initialization, safe HTTPS links, save/pass/notes, generic handoff, persistence/refinement, stale revision rejection, pt-BR at 320px and escaping; zero browser errors.');
  } finally {
    if (browser) await browser.close();
    fs.rmSync(work, {recursive: true, force: true});
  }
})().catch(e => {console.error(e); process.exitCode = 1;});
