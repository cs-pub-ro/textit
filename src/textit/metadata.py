from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

class FileType(Enum):
    PDF = auto()
    DOC = auto()
    DOCX = auto()
    HTML = auto()
    RTF = auto()
    DVI = auto()
    MOBI = auto()
    EPUB = auto()

class DocumentClass(Enum):
    BOOK = auto()
    THESIS = auto()
    WEBPAGE = auto()

@dataclass
class Metadata:
    file_type: Optional[FileType] = None
    document_class: Optional[DocumentClass] = None
    digest: Optional[str] = None
    nlines: Optional[int] = 0
    original_nlines: Optional[int] = 0
