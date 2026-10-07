# Instagram research access

Use when Instagram is relevant to a confirmed search. Prefer verified public browser access; retain [supreme-gg-gg/instagram-cli](https://github.com/supreme-gg-gg/instagram-cli) as an optional client because its login is currently rejected on this host.

## Public browser research (default)

Use `scripts/instagram-browser.cjs` first. It runs installed Google Chrome with a clean, temporary browser context, using the bundled Playwright runtime or a local Playwright installation. It does not read personal Chrome profiles, saved cookies, or Instagram CLI sessions. If neither runtime exists, install the inspected browser-tool version separately:

```sh
npm install --prefix "$HOME/.local/share/shortlist/instagram-browser" playwright@1.62.1 --no-audit --no-fund
```

Requires installed Chrome. Resolve `<skill>` relative to SKILL.md:

```sh
node <skill>/scripts/instagram-browser.cjs profile SHOP_HANDLE
node <skill>/scripts/instagram-browser.cjs post POST_SHORTCODE
```

`SHORTLIST_PLAYWRIGHT` can point to an existing Playwright module directory. `--visible` shows the same clean browser for inspection; it does not save a logged-in session. Discover handles through public web search and linked sites, inspect promising profile pages, then inspect relevant post shortcodes from the returned `post_links`. Calls are sequential and inspect one page each; avoid broad scans.

The helper returns the actual source URL, retrieval date, profile header text, attributed post caption metadata and its author/date label when available, and visible page text. Caption metadata may be truncated. Visible text includes interface labels and can include visitor comments; use only clearly attributed author text as provider evidence. Timestamps can belong to comments, so match a publication date to the post's explicit caption/date label rather than taking any timestamp. Missing or changed page structure, redirects, login gates and limits return errors instead of invented evidence. No credentials are needed for a public page that renders successfully.

A live public profile and post were retrieved on 2026-10-06. Public access is not exhaustive or guaranteed. Image text, reel speech, stories, highlights, private posts and login-gated content remain uninspected. If a public page becomes unavailable, disclose the gap and use another accessible source or an authorized browser/connector; stop on limits. Do not repeat the failed mobile-client password login.

## Optional mobile client

The suggested `instagram-cli` was inspected and installed, but its legacy `/accounts/login/` flow still returned `needs_upgrade` after its packaged app-version patch. Updating version constants did not establish working authentication. Keep it optional; the public browser helper is the verified research route on this host.

For a future compatible client/session, the existing helper supports:

```sh
node <skill>/scripts/instagram.cjs doctor
node <skill>/scripts/instagram.cjs status
node <skill>/scripts/instagram.cjs search "bicycle repair" --limit 6
node <skill>/scripts/instagram.cjs profile SHOP_HANDLE --limit 6
```

The inspected setup is `bash <skill>/scripts/setup-instagram.sh`; it applies packaged patches before checking the reported version. `doctor` verifies loading and rejects the known unpatched version, not Instagram acceptance. `status` checks for a local session, not authentication. Use account search/profile reads only after a successful authenticated read. Native account search is a bounded username/name search, not semantic search across all posts. The default returns up to six accounts/posts, maximum ten, with one response page per operation. The account owner handles any future login locally; passwords/codes/session cookies stay outside chat and output.

The helper restores CLI session state in memory without initializing inbox, timeline, or realtime. An optional `--account HANDLE` selects a saved account without changing its default; `--tool-directory PATH` selects another installation. Command failures emit `ok:false` with nonzero status. Partial profile success with unavailable posts emits `ok:true` with `post_error`; stop further reads if it reports authentication, challenge, or rate-limit errors. Private posts, DMs and actions are excluded.

## Evidence and presentation

Match a handle to its candidate using linked websites, registration, name and service details. Use the profile URL for bio claims and an individual post URL for caption claims. Map explicit text to the session evidence fields (`publisher`, `excerpt`, `checked_at`, `scope`, and `declared:true`). Convert an explicit publication date to `published_at`; retrieval dates are not publication dates. Instagram service claims do not establish registration or insurer eligibility; offering receipts is insufficient to establish insurance reimbursement.

Keep raw output inside the ignored session directory, and show only relevant excerpts in the review UI. Photo URLs remain subject to host display policy; use placeholders when blocked. Both helpers avoid DMs, follows, likes, contacting candidates, marking stories viewed, and media downloads. Report social coverage and access gaps separately from evidence quality.
