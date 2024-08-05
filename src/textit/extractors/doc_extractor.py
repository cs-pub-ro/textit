from typing import List
from ..metadata import Metadata

def doc_handler(file_path: str, metadata: Metadata) -> List[str]:

    print(f"Extracting text from PDF: {file_path}")
    return ["Sample doc text"]
