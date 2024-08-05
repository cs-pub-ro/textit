import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result

# Create an instance of TextExtractor
extractor = TextExtractor()

# Add processing functions to the pipeline
extractor.add_processor(text_repair)
extractor.add_processor(quality_filter)
extractor.add_processor(language_identification)

# Example usage for a PDF file
mobi_file_path = "tests/fixtures/J.R.R. Tolkien - Stapinul inelelor 1 - Fratia inelului.mobi"
mobi_metadata = Metadata(file_type=FileType.MOBI, document_class=DocumentClass.BOOK)

result = extractor.extract_text(mobi_file_path, mobi_metadata)
handle_result(result, "Extracted text from MOBI:")

# Example usage for an unsupported file type
unsupported_file_path = "path/to/your/document.unsupported"

result = extractor.extract_text(unsupported_file_path)
handle_result(result, "Extracted text from unsupported file:")
