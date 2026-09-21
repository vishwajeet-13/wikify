# Copyright (c) 2026, BWH and contributors
# For license information, please see license.txt
import fitz
import frappe
from frappe.tests.utils import FrappeTestCase

from wikify.api import pages as pages_api
from wikify.engine import store
from wikify.tests import _cleanup

_PNG = (
	b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
	b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00"
	b"\x00\x00IEND\xaeB`\x82"
)


def _make_pdf_file() -> str:
	document = fitz.open()
	page = document.new_page(width=612, height=792)
	page.insert_text((72, 90), "Pages API test page", fontsize=12)
	uploaded = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.generate_hash(length=6)}-pages-api-test.pdf",
			"content": document.tobytes(),
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	return uploaded.file_url


class TestPagesApi(FrappeTestCase):
	def setUp(self):
		self.sd = frappe.get_doc({"doctype": "Source Document", "title": "Pages API Test"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(_cleanup.delete_document, self.sd.name)
		project = frappe.db.get_value("Wikify Project", {"is_default": 1}, "name")
		frappe.get_doc(
			{
				"doctype": "Wikify Import",
				"import_title": "Pages API Test Import",
				"project": project,
				"pdf": _make_pdf_file(),
				"source_document": self.sd.name,
			}
		).insert(ignore_permissions=True)
		self.page_name = store.add_page(self.sd.name, 1, "visual", _PNG, "![Diagram](image1.png)")

	def test_crop_page_figure_coerces_args_and_replaces_the_tag(self):
		result = pages_api.crop_page_figure(
			source_document=self.sd.name,
			page_no="1",
			caption="Diagram",
			occurrence="0",
			x0="0.1",
			y0="0.1",
			x1="0.4",
			y1="0.4",
		)
		self.assertTrue(result["image_url"])
		markdown = frappe.db.get_value("Source Page", self.page_name, "canonical_markdown")
		self.assertIn(f"![Diagram]({result['image_url']})", markdown)

	def test_crop_page_figure_throws_a_user_facing_error_on_bad_caption(self):
		with self.assertRaises(frappe.ValidationError):
			pages_api.crop_page_figure(
				source_document=self.sd.name,
				page_no="1",
				caption="Nope",
				occurrence="0",
				x0="0.1",
				y0="0.1",
				x1="0.4",
				y1="0.4",
			)
