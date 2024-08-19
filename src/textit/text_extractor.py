from typing import List, Optional, Dict, Callable, Union
from dataclasses import dataclass
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ProcessPoolExecutor
import os
import hashlib

from textit.extractors import pdf_extractor, doc_extractor, epub_extractor
from textit.extractors import html_extractor, mobi_extractor

from textit.metadata import Metadata, FileType, DocumentClass
from textit.helpers import Result, getLogger

# Type aliases
HandlerFunction = Callable[[str, Metadata], tuple[Result[List[str]], Metadata]]
ProcessingFunction = Callable[[str], Optional[str]]

def compute_sha1(text):
    text_bytes = text.encode('utf-8')
    sha1_hash = hashlib.sha1()
    sha1_hash.update(text_bytes)
    return sha1_hash.hexdigest()


class TextExtractor:
    def __init__(self):
        self.handlers: Dict[FileType, HandlerFunction] = {
            FileType.PDF: pdf_extractor.pdf_handler,
            FileType.DOC: doc_extractor.doc_handler,
            FileType.DOCX: doc_extractor.doc_handler,
            FileType.HTML: html_extractor.html_handler,
            #FileType.RTF: rtf_extractor.rtf_handler,
            #FileType.DVI: dvi_extractor.dvi_handler,
            FileType.MOBI: mobi_extractor.mobi_handler,
            FileType.EPUB: epub_extractor.epub_handler,
        }
        self.processing_pipeline: List[ProcessingFunction] = []

    def register_handler(self, file_type: FileType, handler: HandlerFunction) -> None:
        self.handlers[file_type] = handler

    def add_processor(self, processor: ProcessingFunction) -> None:
        self.processing_pipeline.append(processor)

    def extract_text(self, file_path: str, metadata: Optional[Metadata] = None) -> tuple[Result[List[str]], Metadata]:
        if metadata is None:
            metadata = Metadata()

        # Identify the file type and the handler. and_then simply applies the
        # function received as an argument if the value is Result[T] and not
        # Error
        file_type_handler = (self._determine_file_type(file_path, metadata)
            .and_then(self._get_handler)
            )

        # Extract the text using the right handler
        text, newmetadata = file_type_handler.and_then(lambda handler: handler(file_path, metadata))
        if text.is_err():
            logger = getLogger()
            logger.error(text._error)
            if newmetadata.drop_reason is None:
                newmetadata.drop_reason = "text-extraction-failure"

            return Result.ok([""]), newmetadata

        newmetadata.original_nlines = len(text.unwrap())

        # Call the pipeline functions for text processing
        processed_text = text.map(self._process_text)

        if processed_text.is_ok():
            newmetadata.nlines = len(processed_text.unwrap())

        return (processed_text, newmetadata)

    def _determine_file_type(self, file_path: str, metadata: Metadata) -> Result[FileType]:
        if metadata.file_type:
            return Result.ok(metadata.file_type)

        _, extension = os.path.splitext(file_path)
        extension = extension.lower()[1:]  # Remove the leading dot

        extension_to_type = {
            'pdf': FileType.PDF,
            'doc': FileType.DOC,
            'docx': FileType.DOC,
            'html': FileType.HTML,
            #'rtf': FileType.RTF,
            #'dvi': FileType.DVI,
            'mobi': FileType.MOBI,
            'epub': FileType.EPUB
        }

        file_type = extension_to_type.get(extension)
        if file_type is None:
            return Result.err(f"Unsupported file extension for {file_path}: {extension}")

        return Result.ok(file_type)

    def _get_handler(self, file_type: FileType) -> Result[HandlerFunction]:
        handler = self.handlers.get(file_type)
        if handler is None:
            return Result.err(f"Invalid File Type: {file_type}. No registered handler.")
        return Result.ok(handler)

    def _process_text(self, raw_text: List[str]) -> List[str]:
        with ThreadPoolExecutor() as executor:
            processed_text = [e for e in list(executor.map(self._apply_pipeline, raw_text)) if e is not None]
        return processed_text

    def _apply_pipeline(self, text: Optional[str]) -> Optional[str]:
        for processor in self.processing_pipeline:
            text = None if text is None else processor(text)

        return text
