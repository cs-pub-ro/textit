from typing import List
from ..metadata import Metadata

def mobi_handler(file_path: str, metadata: Metadata) -> List[str]:

    print(f"Extracting text from PDF: {file_path}")
    return ["Sample PDF text"]
