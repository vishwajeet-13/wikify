# Import Detail: tab cleanup + publish → Wiki app edit handoff

## Summary

Two changes to `ImportDetail.vue` and its related components, shipped as two
PRs:

1. **Tab cleanup** — hide the Explore tab and the standalone Wiki (generate)
   tab; rename Tree → Wiki and fold the publish action into it.
2. **Publish handoff** — once a wiki has been generated once, stop offering
   Regenerate from Wikify and send the user to the real Wiki app editor for
   further edits, instead of round-tripping through Wikify.

## Background

`ImportDetail.vue` currently shows six tabs: PDF, Pages, Tree, Explore, Wiki,
Logs.

- **Tree** (`SectionTree.vue`) is where the section hierarchy is reviewed and
  approved ("Approve & Build Graph").
- **Wiki** (`WikiGenerate.vue`) is where a target Wiki Space is chosen and
  `wikify.api.imports.generate_wiki` is called to write/overwrite `Wiki
  Document` records under it.

`generate_wiki` → `wikify.engine.generate.generate_wiki` does a full
sweep-and-rebuild of the target space's `Wiki Document` records from the
current `Source Section` rows on every call, including "Regenerate." There is
no reverse sync: an edit made directly in the Wiki app's own editor
(`/wiki-app/spaces/:spaceId/page/:pageId`, in-place `WikiEditor`) would be
silently overwritten by a later Regenerate from Wikify.

## Goals

- Reduce ImportDetail to the tabs actually in use today: PDF, Pages, Wiki,
  Logs. Explore and the separate generate-only Wiki tab are hidden, not
  deleted — they can come back later.
- Consolidate arranging the tree and publishing it into one "Wiki" tab.
- Once a space has been published from an import, make the Wiki app the one
  place further edits happen — Wikify stops being a second, conflicting
  editing surface for that content.

## Non-goals

- No reverse sync (Wiki app edits flowing back into `Source Section`).
- No "unpublish" / re-enable-regenerate flow.
- No changes to `generate_wiki`'s actual generation logic (the sweep-and-
  rebuild algorithm, page-ref rewriting, etc.) — only when it's callable.
- No removal of `Explore.vue` / `WikiGenerate.vue` — they stay in the
  codebase, just unmounted from `ImportDetail.vue`'s tab list.

## PR1 — Tab cleanup

- `ImportDetail.vue`: `tabs` array drops `{ label: "Explore", key: "explore" }`
  and `{ label: "Wiki", key: "wiki" }` (the generate-only one), and relabels
  `{ label: "Tree", key: "tree" }` to `{ label: "Wiki", key: "tree" }` (the
  route `key` stays `tree` so existing deep links / the `tab` route param
  don't need a migration).
- `SectionTree.vue` gains the target-space picker + Generate/Regenerate button
  currently in `WikiGenerate.vue` (existing space vs. new space, same
  `generate_wiki` call), rendered alongside the tree — e.g. in the tree's
  toolbar/header area. The preview-list pane from `WikiGenerate.vue` is not
  ported over; `WikiPreview.vue` (page preview dialog) stays as-is for
  in-progress (pre-publish) browsing.
- Resulting tabs: **PDF · Pages · Wiki · Logs**.

## PR2 — Publish → edit-in-Wiki-app handoff

### Locking regenerate after first publish

- Client: once `imp.doc.status === "Completed"` (or `wiki_space` is set),
  the Wiki tab renders a **Published** state — the Generate/Regenerate button
  is replaced by the state described below, not just disabled-but-visible.
- Server: `wikify.api.imports.generate_wiki` gets the same check enforced —
  reject (`frappe.throw`) a call for an import whose status is already
  `Completed` unless some future flow explicitly allows it. This isn't just a
  UI nicety: it stops a stale tab or a direct API call from clobbering
  Wiki-app edits after publish.

### Per-page links to the real editor

- In the Published state, the tree is still shown (for orientation), but each
  row's click target changes: instead of opening `WikiPreview.vue`, it opens
  `/wiki-app/spaces/{wiki_space}/page/{wiki_document}` in a new tab —
  `wiki_space` from `imp.doc.wiki_space`, `wiki_document` from the
  corresponding `Source Section.wiki_document`.
- A banner above the tree explains the handoff, e.g. *"This wiki has been
  published — edit pages directly in the Wiki app,"* with a link to the space
  root (`/{space_route}`).

## Open questions for later (explicitly deferred)

- Whether remediation/re-parse after publish should ever be able to push
  changes back into an already-published space (would need to detect and
  reconcile Wiki-app-side edits — the reverse-sync problem called out as a
  non-goal above).
- Whether Explore and the richer WikiGenerate preview list come back later,
  and in what form.
