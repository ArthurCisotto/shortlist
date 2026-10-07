# Install Shortlist

[← README](README.md)

## Requirements

| Component | Needed for |
| --- | --- |
| Local Codex or Claude Code with skill support and file access | Running the skill and keeping sessions. |
| **visualize** in Codex, or a modern local browser | Reviewing the interactive Evidence Desk. |
| Web search and source-reading tools | Discovering and verifying real candidates. |
| Python 3.10+ on macOS or Linux | Validating, ranking, saving, and rendering sessions. |
| Node.js 18+, npm, and installed Google Chrome | Optional Instagram browser research and browser checks. |

The core helper uses `fcntl` for file locking, so native Windows execution is not supported. A Linux environment can run the helper; the interactive view still depends on host capabilities.

With visualize, Codex displays the interface inline. Without inline display, Claude Code and terminal hosts render a complete HTML page with `render --standalone` for a local browser. Save/Refine messages are then copied into the same agent chat. Headless users can review a sourced text shortlist or save the HTML for later. This repository includes the Evidence Desk template, but does not install the host's visualize capability.

## Codex: ask the skill installer

Send this as a prompt in Codex:

```text
$skill-installer install https://github.com/ArthurCisotto/shortlist/tree/main/skills/shortlist
```

The installer copies the complete skill directory, including its scripts, assets, and references. If the destination already exists, it refuses to overwrite it; use the manual update procedure below.

Codex detects newly installed skills automatically. If Shortlist does not appear, restart Codex. You can then invoke it by name:

```text
$shortlist Find a quiet vegetarian-friendly restaurant for Friday dinner.
Ask me about the neighborhood, time, and budget before researching.
```

These discovery and invocation conventions follow [OpenAI's skill documentation](https://learn.chatgpt.com/docs/build-skills). The installer currently uses `$CODEX_HOME/skills`, defaulting to `~/.codex/skills`; recent Codex hosts also discover `~/.agents/skills`.

## Codex: install manually

Clone the repository and copy the skill into your personal skills directory:

```sh
git clone https://github.com/ArthurCisotto/shortlist.git
cd shortlist
mkdir -p "$HOME/.agents/skills"
# Refuse to overwrite an existing installation.
test ! -e "$HOME/.agents/skills/shortlist" && \
  cp -R skills/shortlist "$HOME/.agents/skills/shortlist"
```

Keep the entire `shortlist` folder together. Copying `SKILL.md` alone leaves the UI and helper scripts unavailable.

For a single project, copy that same folder into the project's `.agents/skills/` instead. Choose one active installation to avoid duplicate discovery.

### Confirm it works

Ask Codex to use Shortlist. It should propose and confirm your criteria before searching, then present sourced options. With visualize available, those options appear in Evidence Desk.

To check the local helper independently, run this from the cloned repository:

```sh
python3 skills/shortlist/scripts/session.py --help
python3 -m unittest discover -s tests -p 'test_*.py'
```

The second command uses synthetic data and does not search the web.

## Claude Code

Clone the repository and copy the entire shared skill into Claude's personal skills directory:

```sh
git clone https://github.com/ArthurCisotto/shortlist.git
cd shortlist
mkdir -p "$HOME/.claude/skills"
test ! -e "$HOME/.claude/skills/shortlist" && \
  cp -R skills/shortlist "$HOME/.claude/skills/shortlist"
```

If you already cloned the repository, start at `mkdir` from its root. For a project-only installation, use the project's `.claude/skills/shortlist/` instead. Claude Code loads the same `SKILL.md` and bundled files; no separate prompt, MCP server, or plugin manifest is needed. These paths and the `/shortlist` command follow [Claude Code's skill documentation](https://code.claude.com/docs/en/skills).

Start a new Claude Code session and invoke:

```text
/shortlist Find a quiet vegetarian-friendly restaurant for Friday dinner.
Ask me about the neighborhood, time, and budget before researching.
```

Claude should confirm your criteria, research with its available tools, and save a local session. It can then render a browser-ready Evidence Desk page inside `.shortlist/` and give you its absolute path.

### Review in your browser

Open that HTML file locally. Use Save/Pass, add optional reasons, and click **Save session** or **Refine**. Copy the complete generated message into the same Claude Code conversation. Claude applies the snapshot, checks the saved file, and re-renders the page. Reload after acknowledgement.

The page has no automatic Claude connection. Keep it open until the save is acknowledged; closing or refreshing before that loses pending choices. You can also request Save/Pass and refinement directly in chat by candidate name or ID.

The export command, using an installed skill and a previously saved session, is:

```sh
python3 "$HOME/.claude/skills/shortlist/scripts/session.py" render \
  .shortlist/SESSION_ID.json .shortlist/SESSION_ID.html --standalone
```

Replace `SESSION_ID` with the known session's ID. Both hosts use the same session schema; resume a search from either agent by providing its ID and known location. Existing revision checks still apply.

## Update an existing installation

Pull the repository, then replace only the installed skill directory. Back up the existing installation first if you have customized it. Personal session files live separately in the working project's `.shortlist/` directory.

From the repository root, for a manual installation:

```sh
git pull --ff-only
cp -R skills/shortlist/. "$HOME/.agents/skills/shortlist/"
```

For an installer-managed Codex copy, use `${CODEX_HOME:-$HOME/.codex}/skills/shortlist/` as the destination instead. For Claude Code, use `$HOME/.claude/skills/shortlist/`. Copying updates current files; review and remove obsolete files separately when a release removes them. Start a new agent session if updated metadata is not detected.

## Optional: public Instagram research

Shortlist can inspect public profile text and attributed post captions when they are accessible. Use another authorized browser or connector when the host already provides one. To use the included clean-browser helper, install Google Chrome and Node.js, then add Playwright separately:

```sh
npm install --prefix "$HOME/.local/share/shortlist/instagram-browser" \
  playwright@1.62.1 --no-audit --no-fund
```

From the repository root:

```sh
node skills/shortlist/scripts/instagram-browser.cjs profile HANDLE
node skills/shortlist/scripts/instagram-browser.cjs post SHORTCODE
```

Replace `HANDLE` or `SHORTCODE` with a public profile handle or post shortcode. The helper also supports `--visible`, and `SHORTLIST_PLAYWRIGHT` can point to an existing Playwright module directory.

Public access can fail because of login gates, rate limits, or page changes. The helper reports the access gap. It does not read personal browser cookies or inspect private posts, stories, highlights, image text, or reel audio. A separate mobile-client helper exists for an already-working authenticated session; it is optional and its login is not established as working. See the [Instagram reference](skills/shortlist/references/instagram.md) for details.

## Troubleshooting

| What you see | What to check |
| --- | --- |
| Shortlist is missing | Confirm `shortlist/SKILL.md` is in the host's skills directory. Start a new session; use `$shortlist` in Codex or `/shortlist` in Claude Code. |
| Results arrive as text | Ask for a local browser export, or use Codex with visualize for an inline view. Text review is supported. |
| Save/Refine opens no request | Paste the interface's fallback message into the same chat. Wait for the agent's saved-file confirmation. |
| A revision conflict | Reload the latest session and reconcile the pending review; do not overwrite the newer file. |
| `BROWSER_TOOL_MISSING` | Install Playwright as above or point `SHORTLIST_PLAYWRIGHT` to an existing module. |
| Chrome cannot start | Install Google Chrome and check that the environment permits browser execution. |
| Instagram is unavailable | Keep the criterion unknown and continue with accessible sources. Stop on rate limits. |

## Uninstall

Remove the installed `shortlist` skill folder from the directory you used. Leave project `.shortlist/` folders in place if you want to retain searches; deleting an installation does not require deleting sessions.
