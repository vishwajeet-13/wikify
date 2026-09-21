from __future__ import annotations

import re


def find_tags(markdown: str, caption: str) -> list[str]:
	"""Every `![caption](url)` tag in `markdown` whose caption matches exactly, in order."""
	pattern = re.compile(r"!\[" + re.escape(caption) + r"\]\([^)]*\)")
	return pattern.findall(markdown or "")


def find_tag_spans(markdown: str, caption: str) -> list[tuple[int, int]]:
	"""Start/end offsets of every `![caption](url)` tag in `markdown`, in order.

	Unlike `find_tags`, this disambiguates occurrences that are textually identical —
	needed by callers that must edit one specific occurrence, not "the first match".
	"""
	pattern = re.compile(r"!\[" + re.escape(caption) + r"\]\([^)]*\)")
	return [m.span() for m in pattern.finditer(markdown or "")]
