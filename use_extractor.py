import sys
import os
import argparse
import json
import gzip
from tqdm import tqdm
from typing import Dict, Any
import multiprocessing as mp
import hashlib


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result, logger
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
        logger.error(f"Error: {e}")
        return None
    except FileNotFoundError:
        logger.error("Error: 'file' command not found")
        return None


def get_output_name(input_path: str) -> str:
    try:
        pathhash = hashlib.md5(input_path.encode("utf-8")).hexdigest()
    except UnicodeEncodeError as e:
        logger.warning(f"UnicodeEncodeError for '{repr(input_path)}':\n\t{e}")
        pathhash = hashlib.md5(repr(input_path).encode("utf-8")).hexdigest()

    bname = os.path.basename(input_path)
    output_filename = os.path.splitext(bname)[0] + f".{pathhash}" + '.json'
    return output_filename


def json_default_serializer(obj):
    return obj.name

import hashlib

def compute_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as file:
        while chunk := file.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def process_file(file_path: str, output_dir: str) -> None:
    extractor = TextExtractor()
    extractor.add_processor(text_repair)
    extractor.add_processor(quality_filter)
    extractor.add_processor(language_identification)

    file_type = get_file_type(file_path)
    metadata = Metadata(file_type=file_type, document_class=DocumentClass.BOOK)
    result, metadata = extractor.extract_text(file_path, metadata)

    assert(metadata is not None)

    pdir, basename = os.path.split(file_path)
    # We will append stuff to the filename, so we must be sure not to cross
    # over the maximum limit (which is system dependent, but 255 to be real).
    # We'll add a base16 md5 and a "json.tmp" extension.
    if len(basename) > 210:
        basename = basename[:210]

    file_path = os.path.join(pdir, basename)
    title = os.path.splitext(basename)[0]

    if result.is_ok():
        text = result.unwrap()

        result = {
            "title": title,
            "url": file_path,
            "extract_version": textit.version.__version__
        }

        result['digest'] = 'sha1:' + compute_sha1(file_path) 

        res_metadata = {}

        if metadata.digest is not None:
            res_metadata['content_digest'] = metadata.digest

        if metadata.nlines is not None:
            result['nlines'] = metadata.nlines

        if metadata.original_nlines is not None:
            result['original_nlines'] = metadata.original_nlines

        result['raw_content'] = '\n'.join(text)

        result = {**result, 'metadata': {**metadata.__dict__}}

        # Write the result to a temporary file and then rename it
        basename = os.path.splitext(get_output_name(file_path))[0]
        output_file_tmp = os.path.join(output_dir, f"{basename}.json.tmp")
        output_file_final = os.path.join(output_dir, f"{basename}.json")
        with open(output_file_tmp, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=json_default_serializer)
        os.rename(output_file_tmp, output_file_final)
    else:
        return None


def process_file_wrapper(arg):
    # For some reason we can't make this anonymous or local because someone
    # wants to pickle it.
    file_path, output_dir = arg
    return process_file(file_path, output_dir)


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
            output_filename = get_output_name(input_file_path)
            output_file_path = os.path.join(args.output_dir, output_filename)
            if not os.path.exists(output_file_path):
                file_list.append(input_file_path)
            else:
                logger.info(f'File {input_file_path} already processed')

    with mp.Pool(processes=args.num_processes) as pool:
        with tqdm(total=len(file_list), desc="Extracting text", unit="file") as pbar:
            for _ in pool.imap_unordered(process_file_wrapper, [(file, args.output_dir) for file in file_list]):
                pbar.update()

if __name__ == "__main__":
    main()
