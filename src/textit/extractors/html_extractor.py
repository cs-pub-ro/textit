from typing import List
from textit.metadata import Metadata
from textit.helpers import Result, format_exception

from trafilatura import extract

def html_handler(file_path: str, metadata: Metadata) -> tuple[Result[List[str]], Metadata]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            extracted_text = extract(f.read())

        #print(extracted_text)
        return (Result.ok([extracted_text]), metadata)
    except Exception as e:
        estr = format_exception(e)
        return (Result.err(f"Error extracting text from HTML at '{file_path}':{estr}"), metadata)

