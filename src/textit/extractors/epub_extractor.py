from typing import List
from ..metadata import Metadata

def epub_handler(file_path: str, metadata: Metadata) -> List[str]:

    print(f"Extracting text from EPUB: {file_path}")
    return ["Sample EPUB text"]
