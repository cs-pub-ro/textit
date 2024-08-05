import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result

import subprocess


def get_file_type(file_path):
    try:
        result = subprocess.run(['file', '-b', file_path], capture_output=True, text=True, check=True)
        file_info = result.stdout.strip().upper()
        
        if "MOBIPOCKET" in file_info:
            return FileType.MOBI
        elif "PDF" in file_info:
            return FileType.PDF
        elif "MICROSOFT WORD" in file_info or "MICROSOFT OFFICE WORD" in file_info:
            return FileType.DOC
        else:
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return None
    except FileNotFoundError:
        print("Error: 'file' command not found")
        return None

# Create an instance of TextExtractor
extractor = TextExtractor()

# Add processing functions to the pipeline
extractor.add_processor(text_repair)
extractor.add_processor(quality_filter)
extractor.add_processor(language_identification)

# Example usage for a PDF file
file_path = "tests/fixtures/J.R.R. Tolkien - Stapinul inelelor 1 - Fratia inelului.mobi"
file_type = get_file_type(file_path)

metadata = Metadata(file_type=file_type, document_class=DocumentClass.BOOK)

result = extractor.extract_text(file_path, metadata)
if result.is_ok():
    text = result.unwrap()
    print('\n'.join(text))
