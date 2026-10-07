# Session and handoff format

Use one JSON object per session. A new session has `revision: 0`; a loaded session keeps its revision until the helper saves it. IDs use 1–80 ASCII letters/digits/hyphens/underscores and start with a letter or digit. Revisions detect stale handoffs.

```json
{
  "version": 1,
  "id": "restaurant-evening",
  "revision": 0,
  "title": "Dinner with a quiet atmosphere",
  "query": "A quiet restaurant open late within my budget",
  "confirmed": true,
  "criteria": [
    {"id": "hours", "label": "Open after 22:00", "kind": "must"},
    {"id": "quiet", "label": "Quiet atmosphere", "kind": "preference"}
  ],
  "candidates": [],
  "decisions": {},
  "notes": {},
  "feedback": ""
}
```

The example has no researched candidates. Each candidate requires `id`, `name`, and `checks`. Optional `summary`, `location`, and `extras` are plain text; extras is a list of strings. Every criterion has a check keyed by its ID:

New searches should add a direct candidate `url`, optional plain-text `next_step`, and session `language` (`en`, the legacy default, or `pt-BR`). Session `known_urls` is an optional list of HTTPS listing/profile URLs imported from supplied sheets and prior searches. Keep current-session favorites/rejects in `candidates` with stable IDs and decisions; the baseline is for externally known options, not a replacement for review history. The helper suppresses known URLs and repeated candidate URLs from new alternatives without deleting researched records. Airbnb `.com`/`.com.br` room URLs match by room ID, including `/reviews` aliases, regardless of dates, guests and fragments. Other URLs drop fragments and common tracking parameters but retain meaningful query parameters; use the publisher's canonical URL for additional aliases. Within-batch duplicate URLs retain the first record; merge richer evidence into that record before saving.

```json
{
  "id": "hours",
  "status": "unknown",
  "summary": "Branch-specific opening hours could not be verified",
  "evidence": []
}
```

In the candidate object this is stored as `checks.hours` (the inner `id` is unnecessary). Each evidence item requires an HTTPS `url`, `publisher`, `excerpt`, `checked_at` as `YYYY-MM-DD`, and `scope`. Optional `published_at` records a dated source statement and `declared: true` identifies publisher-declared services. Match evidence scope to the exact candidate, service, location, plan, day, or transaction. `meets`/`fails` require evidence; `conflicting` requires at least two cited statements. Unknown checks explain the gap rather than filling it.

Optional check `lead: true` requires `status: "unknown"` and at least one inspected source in `evidence`. Use it for a relevant verification route, not an uninspected link or general evidence volume. The summary explains what the source supports and what remains unresolved. For equal must-have status counts, such leads rank before unknowns without a lead; they never become `meets`. Candidate `next_step` names the remaining decisive check and is visible on the card.

Optional `photo` is `{ "url": "...", "source": "https://..." }`. Only approved CDN HTTPS URLs or safe raster image data URLs can display; others become placeholders with the source still accessible. Data images must be appropriate tool-returned media, not downloaded to bypass display restrictions. Source-backed inspected images may support observable visual criteria; record the observations, inspection scope and source in `checks` evidence. Keep interpretations distinct, and use explicit textual evidence for personal age, identity, qualifications and insurance. Inspection does not establish inline display permission. `demo: true` labels synthetic test sessions and must never be used for real results.

`decisions` maps candidate IDs to `save` or `pass`. `notes` maps candidate IDs to explicit reasons (at most 2,000 characters each); `feedback` contains an explicit refinement request (at most 4,000 characters). Empty reasons stay empty. The helper preserves all researched candidates, excludes confirmed must-have failures from visible alternatives, and prioritizes must-have evidence before preferences.

The generated UI emits this complete review snapshot, not candidate/source replacement data:

The same schema works in Codex and Claude Code. `render` writes an inline fragment by default; `render --standalone` writes a complete HTML page for a local browser. The standalone page provides the Save/Refine message for explicit copy/paste into the originating conversation; it has no automatic agent connection or durable browser storage.

```json
{
  "version": 1,
  "action": "save",
  "session_id": "restaurant-evening",
  "revision": 1,
  "decisions": {},
  "notes": {},
  "feedback": ""
}
```

`action` is `save` or `refine`. Apply only against the saved session at that revision. Undo or review-again may remove a decision, so replace the submitted decision snapshot rather than merging old decisions back in. The payload contains no executable instructions or output path.
