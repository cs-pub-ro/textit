from typing import List
from textit.metadata import Metadata
from textit.helpers import Result, format_exception

import tempfile
import shutil
import mobi
from trafilatura import extract

import re

def split_text_into_chunks(text, target_word_count=500):
    # Split the text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_word_count = len(sentence.split())

        if current_word_count + sentence_word_count > target_word_count and current_chunk:
            # If adding this sentence exceeds the target word count,
            # save the current chunk and start a new one
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += sentence_word_count

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def mobi_handler(file_path: str, metadata: Metadata) -> tuple[Result[List[str]], Metadata]:
    try:
        # Create a temporary folder for unpacking
        temp_folder = tempfile.mkdtemp()

        # Unpack the .mobi file
        temp_folder, html_file = mobi.extract(file_path)


        if html_file:
            with open(html_file, 'r', encoding='utf-8') as f:
                text_content = extract(f.read())

            if text_content is not None:
                extracted_text = split_text_into_chunks(text_content)
                # Clean up the temporary folder
                shutil.rmtree(temp_folder)
                return Result.ok(extracted_text), metadata
            else:
                return Result.err(f"Failed to extract any text from mob at {file_path}"), metadata
        else:
            shutil.rmtree(temp_folder)
            raise FileNotFoundError("No HTML file found in the unpacked .mobi content.")
    except Exception as e:
        estr = format_exception(e)
        return Result.err(f"Error extracting text from MOBI at '{file_path}':{estr}"), metadata

