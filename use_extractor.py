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

def process_file(file_path: str) -> Dict[str, Any] | None:

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
        }
        if metadata.digest is not None:
            result['digest'] = metadata.digest
    
        if metadata.nlines is not None:
            result['nlines'] = metadata.nlines

        if metadata.original_nlines is not None:
            result['original_nlines'] = metadata.original_nlines

        result['raw_content'] = '\n'.join(text)

        return result
    else:
        return None

def write_to_separate_files(results: list, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    for result in results:
        if result is not None:
            output_file = os.path.join(output_dir, f"{result['title']}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Extract text from files in a directory")
    parser.add_argument("input_dir", help="Path to the input directory")
    parser.add_argument("output_file", help="Path to the output .json.gz file")
    parser.add_argument("--num_processes", type=int, default=mp.cpu_count(), 
                        help="Number of processes to use (default: number of CPU cores)")
    parser.add_argument("--separate_files", help="Directory to write separate JSON files for each input file")
    args = parser.parse_args()

    file_list = []

    # TODO: We can remove from the file list the already processed files
    for root, _, files in os.walk(args.input_dir):
        for file in files:
            file_list.append(os.path.join(root, file))

    with mp.Pool(processes=args.num_processes) as pool:
        results = list(tqdm(pool.imap(process_file, file_list), 
                            total=len(file_list), 
                            desc="Processing files", 
                            unit="file"))
    if args.separate_files:
        write_to_separate_files(results, args.separate_files)
    else:
        with gzip.open(args.output_file, 'wt', encoding='utf-8') as out_file:
            for (text, metadata) in results:
                if text is not None:
                    out_file.write(json.dumps(result) + '\n')

if __name__ == "__main__":
    main()
