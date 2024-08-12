import sys
import os
import argparse
import json
import gzip
from tqdm import tqdm
from typing import Dict, Any
import multiprocessing as mp


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result
import textit.version

import subprocess


def get_file_type(file_path):
    try:
        result = subprocess.run(['file', '-b', file_path], capture_output=True, text=True, check=True)
        file_info = result.stdout.strip().upper()
        if "HTML" in file_info:
            return FileType.HTML
        if "EPUB" in file_info:
            return FileType.EPUB
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

def process_file(file_path: str, output_dir: str) -> None:

    extractor = TextExtractor()
    extractor.add_processor(text_repair)
    extractor.add_processor(quality_filter)
    extractor.add_processor(language_identification)

    file_type = get_file_type(file_path)
    metadata = Metadata(file_type=file_type, document_class=DocumentClass.BOOK)
    result, metadata = extractor.extract_text(file_path, metadata)

    assert(metadata is not None)

    title = os.path.splitext(os.path.basename(file_path))[0]

    if result.is_ok():
        text = result.unwrap()

        result = {
            "title": title,
            "url": file_path,
            "extract_version": textit.version.__version__
        }
        if metadata.digest is not None:
            result['digest'] = metadata.digest

        if metadata.nlines is not None:
            result['nlines'] = metadata.nlines

        if metadata.original_nlines is not None:
            result['original_nlines'] = metadata.original_nlines

        result['raw_content'] = '\n'.join(text)

         # Write the result to a temporary file and then rename it
        output_file_tmp = os.path.join(output_dir, f"{title}.json.tmp")
        output_file_final = os.path.join(output_dir, f"{title}.json")
        with open(output_file_tmp, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.rename(output_file_tmp, output_file_final)
    else:
        return None

def main():
    parser = argparse.ArgumentParser(description="Extract text from files in a directory")
    parser.add_argument("input_dir", help="Path to the input directory")
    parser.add_argument("output_dir", help="Path to the output .json.gz file")
    parser.add_argument("--num_processes", type=int, default=mp.cpu_count(), 
                        help="Number of processes to use (default: number of CPU cores)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    file_list = []
    for root, _, files in os.walk(args.input_dir):
        for file in files:
            input_file_path = os.path.join(root, file)
            output_file_name = os.path.splitext(file)[0] + '.json'
            output_file_path = os.path.join(args.output_dir, output_file_name)
            
            if not os.path.exists(output_file_path):
                file_list.append(input_file_path)
            else:
                print(f'File {input_file_path} already processed')

    with mp.Pool(processes=args.num_processes) as pool:
        results = list(tqdm(pool.starmap(process_file, [(file, args.output_dir) for file in file_list]), 
                            total=len(file_list), 
                            desc="Processing files", 
                            unit="file"))

if __name__ == "__main__":
    main()
