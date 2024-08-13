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

    def to_json(self):
        return self.name  # or self.value

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
    version: Optional[str] = None
    drop_reason: Optional[str] = None

    def __repr__(self):
        """For dynamically added class members."""
        mems = ", ".join(f"'{k}': {v}" for k, v in self.__dict__.items())
        return f"{type(self).__name__}({mems})"
