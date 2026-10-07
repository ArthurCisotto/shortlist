# Contributing to Shortlist

[← README](README.md)

Shortlist is one installable skill with a small session helper and an HTML interface. Reuse those pieces before adding another layer.

## What lives where

- `skills/shortlist/SKILL.md` defines the research and review workflow.
- `skills/shortlist/scripts/session.py` owns validation, ranking, saving, and rendering.
- `skills/shortlist/assets/evidence-desk.html` is the current interface.
- `skills/shortlist/assets/pt-BR.json` translates the interface before candidate data is inserted.
- `skills/shortlist/references/` holds scenario verification, session format, and Instagram guidance.
- `examples/` contains synthetic documentation fixtures; personal searches belong in an ignored `.shortlist/` directory.

## Run the core checks

From the repository root, on macOS or Linux with Python 3.10+:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q skills/shortlist/scripts tests
git diff --check
```

The tests cover evidence requirements, ranking, URL identity, translation, revision conflicts, atomic saves, and untrusted markup. The core helper has no third-party Python dependencies. This repository does not currently define a shared lint or typecheck configuration.

## Run the browser checks

Use Node.js 18+, Google Chrome, and an existing Playwright runtime. To set up a separate runtime without adding project dependencies:

```sh
npm install --prefix "$HOME/.local/share/shortlist/instagram-browser" \
  playwright@1.62.1 --no-audit --no-fund
export SHORTLIST_PLAYWRIGHT="$HOME/.local/share/shortlist/instagram-browser/node_modules/playwright"
node tests/check_ui.cjs
node tests/check_standalone.cjs
node tests/check_instagram_browser.cjs
```

The checks exercise real browser interactions. Instagram browser tests intercept requests with synthetic pages and do not perform live Instagram research. The UI check covers ranking, keyboard review, save/refine snapshots, translation, narrow layouts, and persistence acknowledgement through the local helper.

The standalone check opens the CLI's complete HTML export directly without the Codex bridge, then applies copied Save/Refine payloads and verifies the acknowledged revision, choices, reasons, and feedback. It also checks the Portuguese view and a narrow layout.

The optional mobile-client compatibility check also expects the documented client installation:

```sh
node tests/check_instagram.cjs
```

See the [Instagram reference](skills/shortlist/references/instagram.md) before setting that client up. Its compatibility check does not prove successful live authentication.

## Regenerate documentation screenshots

With the browser runtime configured above:

```sh
node scripts/capture-docs.cjs
```

The script renders the actual Evidence Desk template from the committed English and Portuguese demo sessions, checks the expected content and layout, and captures PNGs into `docs/images/`. It uses temporary files for preview documents and session saves. It never reads a personal session or visits the fixtures' placeholder source URLs.

Review the images after updating the template. A screenshot is useful only if the text is legible, the layout is complete, and the fixture still matches what the docs claim.

## Changes worth checking carefully

- Keep must-have failures excluded and uncertainty visible. A verification lead is not a confirmed match.
- Keep session IDs stable across refinement. Preserve prior favorites and rejects.
- Treat candidate names, excerpts, reasons, and feedback as data; verify escaping and translation boundaries.
- Keep complete review snapshots and revision checks intact. A stale action must not overwrite a newer session.
- Keep Save/Pass usable with buttons and keyboard. Check both desktop and narrow layouts.
- Update the session-format reference when the schema changes, and the docs when installation or user behavior changes.

## Verify the host boundary

Browser stubs can check the request format and failure handling. They cannot prove that a real Codex click delivers feedback to the agent.

For changes to the bridge, verify a live interaction in an authorized local Codex session: submit Save/Refine, observe the incoming action, apply it with the helper, check the saved file, and re-render the acknowledged revision. Record which parts were tested and which remain unverified.

For Claude Code, install the shared folder under `.claude/skills/shortlist/` and test `/shortlist` with a confirmed synthetic session. Verify that it saves the session and renders with `--standalone`, then paste a browser-generated `SHORTLIST_ACTION` into the same conversation and inspect the resulting file/revision. Keep all smoke-test sessions outside committed content. Browser tests establish the payload format and local persistence, not the agent's decision to follow the instructions.

## Before opening a pull request

Explain the concrete change and how you checked it. Include a small regression test for changed logic and screenshots for visible UI changes. Keep real search data, generated personal payloads, credentials, and local authentication state out of the diff.
