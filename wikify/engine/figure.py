"""Manual, user-driven figure embedding for one page: crop a precise region out of the
source PDF in place of one existing image tag — leaving the rest of the page's markdown
untouched.

Complements `reparse.embed_page_image`'s caption mode (agent-driven, requires a unique
caption on the page) by resolving the tag positionally instead — caption + which
occurrence of it — so a page with duplicate captions (e.g. two figures both called
"Button") can still be targeted precisely from the UI, where the user clicked a
specific image rather than typing a caption.
"""

from __future__ import annotations

import fitz
import frappe
from frappe.utils.file_manager import save_file

from wikify.engine import store
from wikify.engine.tags import find_tags

# Sharper than the cached page thumbnail (rendered at settings.render_dpi, ~150) so a
# crop of a small in-page figure isn't a blurry upscale.
_CROP_DPI = 400

# Points (1/72in). Below this on either axis it's not a plausible crop.
_MIN_CROP_POINTS = 10


def _pdf_path(source_document: str) -> str | None:
	pdf_url = frappe.db.get_value("Wikify Import", {"source_document": source_document}, "pdf")
	if not pdf_url:
		return None
	file_name = frappe.db.get_value("File", {"file_url": pdf_url}, "name")
	return frappe.get_doc("File", file_name).get_full_path() if file_name else None


def _page_row(source_document: str, page_no: int) -> dict:
	row = frappe.db.get_value(
		"Source Page",
		{"source_document": source_document, "page_no": page_no},
		["name", "canonical_markdown", "baseline_markdown"],
		as_dict=True,
	)
	if not row:
		raise ValueError(f"Page {page_no} of {source_document} not found.")
	return row


def _resolve_tag(markdown: str, caption: str, occurrence: int) -> str:
	tags = find_tags(markdown, caption)
	if occurrence < 0 or occurrence >= len(tags):
		raise ValueError(
			f"Couldn't find image tag '{caption}' (occurrence {occurrence}) on this page — "
			"it may have changed. Reload the page and try again."
		)
	return tags[occurrence]


def _clip_rect(page_rect: fitz.Rect, bbox: dict) -> fitz.Rect:
	x0 = max(0.0, min(1.0, bbox["x0"])) * page_rect.width
	y0 = max(0.0, min(1.0, bbox["y0"])) * page_rect.height
	x1 = max(0.0, min(1.0, bbox["x1"])) * page_rect.width
	y1 = max(0.0, min(1.0, bbox["y1"])) * page_rect.height
	return fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def crop_page_figure(source_document: str, page_no: int, caption: str, occurrence: int, bbox: dict) -> dict:
	page = _page_row(source_document, page_no)
	old_md = page.canonical_markdown or page.baseline_markdown or ""
	old_tag = _resolve_tag(old_md, caption, occurrence)

	pdf_path = _pdf_path(source_document)
	if not pdf_path:
		raise RuntimeError(f"Couldn't locate the source PDF for {source_document}.")

	with fitz.open(pdf_path) as doc:
		if page_no < 1 or page_no > doc.page_count:
			raise ValueError(
				f"Page {page_no} is out of range for {source_document} ({doc.page_count} pages)."
			)
		fpage = doc[page_no - 1]
		clip = _clip_rect(fpage.rect, bbox)
		if clip.width < _MIN_CROP_POINTS or clip.height < _MIN_CROP_POINTS:
			raise ValueError("That crop is too small to be a real figure.")
		zoom = _CROP_DPI / 72.0
		crop_png = fpage.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip).tobytes("png")

	file_doc = save_file(f"page-{page_no:04d}-crop.png", crop_png, "Source Page", page.name, is_private=1)
	new_md = old_md.replace(old_tag, f"![{caption}]({file_doc.file_url})", 1)
	store.set_canonical_markdown(page.name, new_md)
	return {"page_no": page_no, "image_url": file_doc.file_url}
