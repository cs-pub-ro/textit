from typing import List
from ..metadata import Metadata

def html_handler(file_path: str, metadata: Metadata) -> List[str]:

    print(f"Extracting text from HTML: {file_path}")
    return ["Sample HTML text"]
