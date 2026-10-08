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
python3 -m compileall -q skills/shortlist/scripts scripts tests
git diff --check
```

The tests cover evidence requirements, ranking, URL identity, translation, revision conflicts, atomic saves, untrusted markup, and evaluation grading. The core helper has no third-party Python dependencies. This repository does not currently define a shared lint or typecheck configuration.

## What each check establishes

| Check | What it tests | What it does not establish |
| --- | --- | --- |
| Offline unit tests | Helper behavior, fixture serving, and graders rejecting incorrect or unobserved evidence. | An agent's research ability. |
| Browser checks | Rendering, review interactions, and local persistence handoffs. | Real host delivery or source accuracy. |
| Agent reasoning evaluation | Verdicts from supplied, frozen source excerpts. | Discovery or retrieval of those sources. |
| Evidence acquisition evaluation | Retrieval and interpretation of controlled linked HTML, including collapsed content and access failures. | Browser clicks or live-web accuracy. |
| Independent live audit | Whether fresh research claims are supported by independently inspected sources. | Universal accuracy or improvement across different samples. |

## Test agent reasoning

The ten frozen synthetic cases in `tests/behavior/cases.json` test source interpretation across domains: partial descriptions, exact versus ambiguous scope, compound requirements, arithmetic, qualitative claims, and conflicting sources. `answer_key.json` holds independently specified statuses and rationales. These evaluations test reasoning from supplied evidence, not live discovery or source extraction.

With an authenticated Claude Code CLI installed:

```sh
python3 scripts/eval_behavior.py run
```

The runner uses a fresh temporary directory, disables tools and MCP, preserves the CLI's default model, and passes the current skill's Evaluate instructions with the cases. It sends no answer key or historical results. Live evaluations use model quota and run separately from the normal offline tests. No new dependencies or API keys are required.

Each run saves its exact prompt, prompt/skill hashes, model metadata, raw response, explanations and verdict report under ignored `.shortlist/evals/`. Exit 0 means every expected status matched and the response was well formed; exit 1 means a verdict/schema failure; exit 2 means the run could not complete. Outputs cannot overwrite an existing run directory. Review explanations against the answer-key rationales; a correct status alone does not establish correct reasoning.

To evaluate another agent, including Codex, provide only the exported prompt in a fresh conversation without tools or repository access, save its JSON response, then grade it:

```sh
python3 scripts/eval_behavior.py prompt > /tmp/shortlist-behavior-prompt.txt
python3 scripts/eval_behavior.py grade /path/to/agent-response.json
```

Keep expected answers and historical responses out of the evaluating agent's context. Add new cases with a source excerpt, confirmed criterion, expected status, and rationale; include clear matches as well as uncertainty and failure. Compare repeated runs after changing instructions, using the same fixtures and model. This small suite is a regression check, not a claim of accuracy in every domain.

## Test evidence acquisition

The seven controlled cases in `tests/research/` require the agent to retrieve starting pages and follow links to decisive evidence. They cover detailed specifications, contradictory conditions, total cost, exclusions, missing information, a blocked document, and recovery through an official documentation index after an initial page fails. The recovery case requires the failed request to precede the successful guide requests; a failed page need not be cited as support for a positive verdict.

```sh
python3 scripts/eval_research.py run
python3 scripts/eval_research.py grade /path/to/saved-run
```

This uses the authenticated Claude Code CLI with the full current skill, a fresh directory, and access only to exact read-only requests on a local fixture server. It preserves the CLI's default model, uses model quota, and requires no additional API key or project dependency. The answer key is never served to the agent. A pass requires the expected verdict, relevant cited URLs, and server logs proving those URLs were fetched. Runs save prompts, fixtures, responses, retrieval logs, and reports under ignored `.shortlist/evals/research/`; regrading uses that run's archived cases and answer key. Exit codes follow the reasoning runner: 0 for a pass, 1 for grading failures, 2 for an execution failure. Review explanations separately.

Collapsed content is present in the retrieved HTML; this tests inspection of that content, not browser clicks. These controlled tests do not measure live-web accuracy. For live audits, freeze the original research and criteria before an independent source review; report incorrect claims, missed evidence, unresolved requirements, and access failures separately. Different search samples cannot establish a before/after improvement.

### Compare instruction changes

Save the old skill before editing, then use `--policy` and the same full model ID for both versions:

```sh
python3 scripts/eval_research.py run --policy /path/to/before-SKILL.md --model FULL_MODEL_ID
python3 scripts/eval_research.py run --policy /path/to/after-SKILL.md --model FULL_MODEL_ID
```

Keep cases, pages, answer key, CLI version, permissions, and time budget fixed. The shared prompt describes tools and output only; research guidance comes from the supplied skill. Run multiple fresh pairs, alternate which version runs first, and confirm the requested model appears in each report's actual model usage. Commands are archived with each run. Review reasons and the retrieval logs, then report paired gains and regressions separately from overall scores. A small controlled suite can reveal a regression or a ceiling tie; it cannot establish a general improvement in live research.

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
