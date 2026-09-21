
from __future__ import annotations

import re


def find_tags(markdown: str, caption: str) -> list[str]:
	"""Every `![caption](url)` tag in `markdown` whose caption matches exactly, in order."""
	pattern = re.compile(r"!\[" + re.escape(caption) + r"\]\([^)]*\)")
	return pattern.findall(markdown or "")
