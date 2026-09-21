<script setup>
// Manual figure fix for one page: crop a precise region out of the page's photo in
// place of the one `target` tag (matched by caption + occurrence, since captions can
// repeat on a page) — the rest of the page's markdown is untouched. Companion to the
// deterministic whole-page-photo fallback (auto-repair + use_page_image) this closes
// the loop on.
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { Dialog, Button, ErrorMessage, useCall } from "frappe-ui";
import Cropper from "cropperjs";
import "cropperjs/dist/cropper.css";

const props = defineProps({
	// { sourceDocument, pageName, pageNo, pageImage, caption, occurrence }
	target: { type: Object, required: true },
});
const emit = defineEmits(["close", "saved"]);

const open = ref(true);
watch(open, (v) => {
	if (!v) emit("close");
});

const imageEl = ref(null);
let cropper = null;
const cropperReady = ref(false);

function initCropper() {
	destroyCropper();
	cropperReady.value = false;
	if (!imageEl.value) return;
	cropper = new Cropper(imageEl.value, {
		viewMode: 1,
		dragMode: "move",
		autoCropArea: 0.5,
		background: false,
		zoomable: false,
		ready: () => {
			cropperReady.value = true;
		},
	});
}
function destroyCropper() {
	cropper?.destroy();
	cropper = null;
}
onBeforeUnmount(destroyCropper);

watch(
	() => props.target.pageImage,
	async () => {
		destroyCropper();
		await nextTick();
		initCropper();
	},
	{ immediate: true }
);

const cropFigure = useCall({
	url: "/api/v2/method/wikify.api.pages.crop_page_figure",
	method: "POST",
	immediate: false,
});
const cropError = ref("");
async function submitCrop() {
	if (!cropper || !imageEl.value) return;
	const img = imageEl.value;
	const data = cropper.getData(true);
	cropError.value = "";
	await cropFigure.submit({
		source_document: props.target.sourceDocument,
		page_no: props.target.pageNo,
		caption: props.target.caption,
		occurrence: props.target.occurrence,
		x0: data.x / img.naturalWidth,
		y0: data.y / img.naturalHeight,
		x1: (data.x + data.width) / img.naturalWidth,
		y1: (data.y + data.height) / img.naturalHeight,
	});
	if (cropFigure.error) {
		cropError.value =
			cropFigure.error?.messages?.[0] ||
			cropFigure.error?.message ||
			"Couldn't crop that figure.";
		return;
	}
	emit("saved");
	open.value = false;
}
</script>

<template>
	<Dialog v-model:open="open" :title="`Fix '${target.caption}'`" size="xl">
		<template #body-content>
			<div class="max-h-[60vh] overflow-hidden rounded border border-outline-gray-1">
				<img
					v-if="target.pageImage"
					ref="imageEl"
					:src="target.pageImage"
					alt=""
					class="block max-w-full"
				/>
				<p v-else class="p-6 text-center text-sm text-ink-gray-5">
					No page photo available to crop.
				</p>
			</div>
			<ErrorMessage v-if="cropError" :message="cropError" class="mt-2" />
			<div class="mt-3 flex justify-end gap-2">
				<Button label="Cancel" variant="ghost" @click="open = false" />
				<Button
					label="Crop &amp; embed"
					variant="solid"
					:loading="cropFigure.loading"
					:disabled="!cropperReady"
					@click="submitCrop"
				/>
			</div>
		</template>
	</Dialog>
</template>
