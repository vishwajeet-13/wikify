# Import Detail Tab Cleanup (PR1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `ImportDetail.vue` to `PDF · Pages · Wiki · Logs`, where the
new "Wiki" tab (the old "Tree") both arranges the section tree and publishes
it — folding in the space picker + Generate/Regenerate action that used to
live on its own "Wiki" tab (`WikiGenerate.vue`).

**Architecture:** Extract the target-space picker + generate/regenerate
control out of `WikiGenerate.vue` into a new, smaller component
`WikiPublish.vue` (no preview pane — `SectionTree.vue` already has one).
Mount `WikiPublish.vue` inside `SectionTree.vue`'s toolbar. Update
`ImportDetail.vue`'s tab list and drop its now-unused `explore`/`wiki`
template panels and imports (the source files `Explore.vue` /
`WikiGenerate.vue` stay on disk, untouched, just unreferenced).

**Tech Stack:** Vue 3 `<script setup>`, frappe-ui v1 (`useCall`, `useList`,
`Dialog`, `TabButtons`, `FormControl`, `Badge`, `Button`, `toast`), the
wikify realtime socket (`useSocket`).

**Note on testing:** this frontend has no unit/component test runner
configured (`frontend/package.json` only has `dev`/`build`/`serve` scripts,
no vitest/jest). Verification here is a live check against the running
`wikify.localhost:8013` site (bench root `/Users/chiku/company_projects/sep_bench`,
`bench start` already running) instead of automated tests — drive it with a
browser and confirm the rendered behavior, not just the diff.

---

### Task 1: Extract `WikiPublish.vue`

**Files:**
- Create: `frontend/src/components/WikiPublish.vue`
- Reference (read-only, do not modify): `frontend/src/components/WikiGenerate.vue`

- [ ] **Step 1: Create the component**

Port the *left panel* logic/markup from `WikiGenerate.vue` (target picker +
generate button + generated-link + stop button), drop the *right panel*
preview list entirely (rows/preview/WikiPreview dialog — `SectionTree.vue`
already renders `WikiPreview` for the selected node). Collapse the picker
into a `Dialog` triggered by a compact button, so it fits in a toolbar row.

```vue
<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from "vue";
import {
	Badge,
	Button,
	Dialog,
	FormControl,
	TabButtons,
	dialog,
	useCall,
	useList,
	toast,
} from "frappe-ui";
import { useSocket } from "@/socket";

const props = defineProps({
	importName: { type: String, required: true },
	status: { type: String, default: null },
	wikiSpace: { type: String, default: null },
});
const emit = defineEmits(["generated"]);

// Generation is gated on an approved tree (Graphed) — or a prior run
// (Completed → it regenerates in place).
const canPublish = computed(() =>
	["Graphed", "Completed", "Generating Wiki", "Stopped"].includes(props.status)
);
const generating = computed(() => props.status === "Generating Wiki");
const alreadyGenerated = computed(() => props.status === "Completed" || !!props.wikiSpace);

// Existing spaces (also resolves the current space's route for the "View wiki" link).
const spaces = useList({
	doctype: "Wiki Space",
	fields: ["name", "space_name", "route"],
	orderBy: "modified desc",
	limit: 100,
	auto: true,
});
const currentSpace = computed(() => (spaces.data || []).find((s) => s.name === props.wikiSpace));

// Target choice: reuse an existing space, or create a new one.
const mode = ref("existing");
const targetSpace = ref(null);
const newName = ref("");
const newRoute = ref("");
watch(
	() => spaces.data,
	(list) => {
		if (!list?.length) mode.value = "new";
		else if (!targetSpace.value) targetSpace.value = props.wikiSpace || list[0]?.name;
	},
	{ immediate: true }
);
watch(newName, (n) => {
	newRoute.value = (n || "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "");
});

const spaceOptions = computed(() =>
	(spaces.data || []).map((s) => ({ label: `${s.space_name} (/${s.route})`, value: s.name }))
);

const open = ref(false);

const generate = useCall({
	url: "/api/v2/method/wikify.api.imports.generate_wiki",
	method: "POST",
	immediate: false,
});
const canGenerate = computed(() =>
	mode.value === "existing" ? !!targetSpace.value : !!(newName.value && newRoute.value)
);
async function runGenerate() {
	const params = { import_name: props.importName };
	if (mode.value === "existing") params.wiki_space = targetSpace.value;
	else params.new_space = { space_name: newName.value, route: newRoute.value };
	await generate.submit(params);
	if (generate.error) {
		toast.error(generate.error?.messages?.[0] || "Could not start wiki generation");
		return;
	}
	open.value = false;
	emit("generated");
}

const stop = useCall({
	url: "/api/v2/method/wikify.api.imports.stop_wiki_generation",
	method: "POST",
	immediate: false,
});
function stopGenerate() {
	dialog.danger({
		title: "Stop wiki generation",
		message:
			"Pages written so far stay in the wiki. Generating again starts over from the first page.",
		confirmLabel: "Stop",
		async onConfirm() {
			await stop.submit({ import_name: props.importName });
			if (stop.error) {
				throw new Error(stop.error?.messages?.[0] || "Could not stop wiki generation");
			}
			emit("generated");
		},
	});
}

const lastRoute = ref(null);
const socket = useSocket();
function onWikiDone(payload) {
	if (payload.import !== props.importName) return;
	lastRoute.value = payload.space_route;
	spaces.reload();
	emit("generated");
	toast.success("Wiki generated");
}
onMounted(() => socket?.on("wikify_wiki_done", onWikiDone));
onUnmounted(() => socket?.off("wikify_wiki_done", onWikiDone));

const wikiUrl = computed(() => {
	const route = lastRoute.value || currentSpace.value?.route;
	return route ? `/${route}` : null;
});
</script>

<template>
	<div class="flex shrink-0 items-center gap-2">
		<a
			v-if="alreadyGenerated && wikiUrl"
			:href="wikiUrl"
			target="_blank"
			class="inline-flex items-center gap-1 text-sm font-medium text-ink-blue-6 hover:underline"
		>
			{{ currentSpace?.space_name || "View wiki" }}
			<span aria-hidden>↗</span>
		</a>
		<Button
			size="sm"
			:variant="alreadyGenerated ? 'subtle' : 'solid'"
			:label="alreadyGenerated ? 'Regenerate' : 'Publish'"
			:disabled="!canPublish"
			:title="!canPublish ? 'Approve the section tree first' : undefined"
			@click="open = true"
		/>

		<Dialog v-model="open" :options="{ title: alreadyGenerated ? 'Regenerate wiki' : 'Publish wiki', size: 'lg' }">
			<template #body-content>
				<p class="mb-4 text-sm text-ink-gray-5">
					Mirror the approved tree into a Wiki Space as linked pages.
				</p>
				<TabButtons
					v-model="mode"
					class="mb-4"
					:options="[
						{ label: 'Existing space', value: 'existing' },
						{ label: 'New space', value: 'new' },
					]"
				/>
				<template v-if="mode === 'existing'">
					<FormControl
						v-if="spaceOptions.length"
						type="select"
						label="Wiki Space"
						:options="spaceOptions"
						v-model="targetSpace"
					/>
					<p v-else class="text-sm text-ink-gray-5">No spaces yet — create one.</p>
				</template>
				<template v-else>
					<FormControl
						type="text"
						label="Space name"
						placeholder="My Manual"
						class="mb-3"
						v-model="newName"
					/>
					<FormControl type="text" label="Route" placeholder="my-manual" v-model="newRoute" />
				</template>

				<div class="mt-5 flex items-center gap-2">
					<Button
						variant="solid"
						:label="alreadyGenerated ? 'Regenerate wiki' : 'Generate wiki'"
						:loading="generate.loading || generating"
						:disabled="!canGenerate || generating"
						@click="runGenerate"
					/>
					<Button
						v-if="generating"
						variant="ghost"
						label="Stop generating"
						icon-left="lucide-circle-stop"
						@click="stopGenerate"
					/>
				</div>
				<p v-if="generating" class="mt-2 text-xs text-ink-gray-5">
					Generating… watch progress in the header.
				</p>
			</template>
		</Dialog>
	</div>
</template>
```

- [ ] **Step 2: Confirm the file has no leftover references to the dropped
  preview pane**

Run: `grep -n "previewRows\|previewSection\|WikiPreview" frontend/src/components/WikiPublish.vue`
Expected: no output (those symbols only existed in `WikiGenerate.vue`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WikiPublish.vue
git commit -m "Add WikiPublish: compact publish control extracted from WikiGenerate"
```

---

### Task 2: Wire `WikiPublish` into `SectionTree.vue`

**Files:**
- Modify: `frontend/src/components/SectionTree.vue`

- [ ] **Step 1: Add the `wikiSpace` prop and import `WikiPublish`**

In the `defineProps` block (around line 10-17), add `wikiSpace`:

```js
const props = defineProps({
	sourceDocument: { type: String, default: null },
	docTitle: { type: String, default: "Document" },
	importName: { type: String, default: null },
	status: { type: String, default: null },
	wikiSpace: { type: String, default: null },
	initialSection: { type: String, default: null },
});
const emit = defineEmits(["graphed", "generated"]);
```

Add the import near the top:

```js
import WikiPublish from "@/components/WikiPublish.vue";
```

- [ ] **Step 2: Render it in the toolbar**

In the toolbar `<div class="flex flex-wrap items-center gap-2 ...">` (around
line 287-308), add `WikiPublish` after the existing "Approve & Build
Graph"/"Rebuild graph" button:

```html
<Button
	class="ml-auto shrink-0"
	size="sm"
	variant="solid"
	:label="graphLabel"
	:loading="graph.loading"
	@click="buildGraph"
/>
<WikiPublish
	:import-name="importName"
	:status="status"
	:wiki-space="wikiSpace"
	@generated="emit('generated')"
/>
```

(`class="ml-auto shrink-0"` stays only on the graph button so it's the one
that pushes the rest to the right; `WikiPublish` sits immediately after it.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SectionTree.vue
git commit -m "Wire WikiPublish into SectionTree's toolbar"
```

---

### Task 3: Update `ImportDetail.vue`'s tabs

**Files:**
- Modify: `frontend/src/pages/ImportDetail.vue`

- [ ] **Step 1: Drop the Explore/WikiGenerate imports, rename the Tree tab**

Replace:

```js
import PageReview from "@/components/PageReview.vue";
import SectionTree from "@/components/SectionTree.vue";
import Explore from "@/components/Explore.vue";
import WikiGenerate from "@/components/WikiGenerate.vue";
```

with:

```js
import PageReview from "@/components/PageReview.vue";
import SectionTree from "@/components/SectionTree.vue";
```

Replace the `tabs` array:

```js
const tabs = [
	{ label: "PDF", key: "pdf" },
	{ label: "Pages", key: "pages" },
	{ label: "Tree", key: "tree" },
	{ label: "Explore", key: "explore" },
	{ label: "Wiki", key: "wiki" },
	{ label: "Logs", key: "overview" },
];
```

with:

```js
const tabs = [
	{ label: "PDF", key: "pdf" },
	{ label: "Pages", key: "pages" },
	{ label: "Wiki", key: "tree" },
	{ label: "Logs", key: "overview" },
];
```

- [ ] **Step 2: Update the Tree panel and remove the Explore/Wiki panels**

Replace the Tree panel:

```html
<!-- Tree -->
<div
	v-else-if="tab.key === 'tree'"
	class="h-[calc(100dvh-9.5rem)] sm:h-[calc(100vh-7rem)]"
>
	<SectionTree
		ref="sectionTree"
		:source-document="imp.doc?.source_document"
		:doc-title="imp.doc?.import_title || name"
		:import-name="name"
		:status="status"
		:initial-section="route.query.section"
		@graphed="imp.reload()"
	/>
</div>
```

with (adds `wiki-space` and a `@generated` handler):

```html
<!-- Wiki (tree editing + publish) -->
<div
	v-else-if="tab.key === 'tree'"
	class="h-[calc(100dvh-9.5rem)] sm:h-[calc(100vh-7rem)]"
>
	<SectionTree
		ref="sectionTree"
		:source-document="imp.doc?.source_document"
		:doc-title="imp.doc?.import_title || name"
		:import-name="name"
		:status="status"
		:wiki-space="imp.doc?.wiki_space"
		:initial-section="route.query.section"
		@graphed="imp.reload()"
		@generated="imp.reload()"
	/>
</div>
```

Delete the two panels that followed it:

```html
<!-- Explore -->
<div
	v-else-if="tab.key === 'explore'"
	class="h-[calc(100dvh-9.5rem)] sm:h-[calc(100vh-7rem)]"
>
	<Explore :source-document="imp.doc?.source_document" :import-name="name" />
</div>

<!-- Wiki -->
<div
	v-else-if="tab.key === 'wiki'"
	class="h-[calc(100dvh-9.5rem)] sm:h-[calc(100vh-7rem)]"
>
	<WikiGenerate
		:source-document="imp.doc?.source_document"
		:import-name="name"
		:status="status"
		:wiki-space="imp.doc?.wiki_space"
		@generated="imp.reload()"
	/>
</div>
```

- [ ] **Step 3: Confirm no dangling references**

Run: `grep -n "Explore\|WikiGenerate" frontend/src/pages/ImportDetail.vue`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ImportDetail.vue
git commit -m "Collapse ImportDetail tabs to PDF/Pages/Wiki/Logs"
```

---

### Task 4: Live verification + screen recording

**Files:** none (verification only)

- [ ] **Step 1: Build the frontend**

Run (from bench root `/Users/chiku/company_projects/sep_bench`):
`bench build --app wikify`
Expected: build succeeds (or run `yarn dev` inside `apps/wikify/frontend`
for a live-reload session instead, if `bench start` is already running).

- [ ] **Step 2: Drive it with a browser**

Reuse the existing Administrator session (same technique as other benches in
this environment): pull the latest session id for `wikify.localhost` from
that site's `tabSessions` table, inject it as a cookie, and navigate to an
existing `/import/IMP-.../tree` (now the "Wiki" tab) with Playwright +
headless Chromium.

Confirm:
- Tabs read exactly PDF, Pages, Wiki, Logs (no Explore, no second Wiki tab).
- The Wiki tab shows the section tree with "Publish"/"Regenerate" +
  "Approve & Build Graph"/"Rebuild graph" together in its toolbar.
- On an import whose tree isn't graphed yet: Publish is disabled.
- On a graphed import: Publish opens the dialog, generating still works
  end-to-end (existing-space and new-space paths), and after it completes
  the "View wiki ↗" link appears and opens the right space.

- [ ] **Step 3: Capture evidence**

Take a screenshot of the new tab bar + Wiki tab (and a short screen
recording of Publish → dialog → generate → "View wiki" link appearing, since
that's an interaction/flow, not just a static layout) for the PR
description, per the `gh-upload` guidance in the global CLAUDE.md.

- [ ] **Step 4: Open the PR**

Push the branch and open a PR with a short description (what changed) and
the screenshot/recording embedded — see the global CLAUDE.md's `gh upload`
usage for attaching media from the CLI.
