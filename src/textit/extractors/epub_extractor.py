from typing import List
from textit.metadata import Metadata
from textit.helpers import Result

import ebooklib
from ebooklib import epub

from trafilatura import extract

def epub_handler(file_path: str, metadata: Metadata) -> Result[List[str]]:
	try:
		book = epub.read_epub(file_path)
		content = ""

		for item in book.get_items():
			if item is not None and item.get_type() == ebooklib.ITEM_DOCUMENT:
				body_content = item.get_body_content().decode()
				text = extract(body_content)
				if text is not None:
					content += text
		return Result.ok([content])
	except Exception as e:
		return Result.err(f"Error extracting text from EPUB: {str(e)}")
