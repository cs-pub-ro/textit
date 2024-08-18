import sys
import os
import argparse
import json
import gzip
from tqdm import tqdm
from typing import Dict, Any
import multiprocessing as mp
import hashlib
import traceback
import tempfile
import shutil


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result, setup_logging, format_exception, getLogger
import textit.version

import subprocess


def init_proc(args):
    setup_logging(args.logdir, stderr=args.logstderr, level=args.loglevel)


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
        estr = "".join(traceback.format_exception(e))
        logger.error(f"Couldn't get file type for '{file_path}':\n```\n{e}\n```\n\n")
        return None
    # XXX Dubious
    # except FileNotFoundError:
        # logger.error("Error: 'file' command not found")
        # return None


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

def process_file(file_path: str, output_dir: str, use_hash_directories: bool) -> None:
    extractor = TextExtractor()
    extractor.add_processor(text_repair)
    extractor.add_processor(quality_filter)
    extractor.add_processor(language_identification)

    file_type = get_file_type(file_path)
    file_digest = compute_sha1(file_path)

    metadata = Metadata(file_type=file_type, document_class=DocumentClass.BOOK)

    # While we can deal with non-UTF-8 filenames, other tools down the line,
    # may not be able to, so here we do first copy a file to temporary, UTF-8
    # path.
    try:
        file_path.encode("utf-8")
        result, metadata = extractor.extract_text(file_path, metadata)
    except UnicodeEncodeError:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_output:
            shutil.copy2(file_path, temp_output.name)
            result, metadata = extractor.extract_text(temp_output.name, metadata)

    assert(metadata is not None)

    pdir, basename = os.path.split(file_path)

    # We will append stuff to the filename, so we must be sure not to cross
    # over the maximum limit (which is system dependent, but 255 to be real).
    # We'll add a base16 md5 and a "json.tmp" extension.
    basename = basename[:210]

    file_path = os.path.join(pdir, basename)
    title = os.path.splitext(basename)[0]

    if result.is_ok():
        text = result.unwrap()
    else:
        text = ""

    result = {
        "title": title,
        "url": file_path,
        "extract_version": textit.version.__version__
    }

    result['digest'] = 'sha1:' + file_digest

    res_metadata = {}

    if metadata.digest is not None:
        res_metadata['content_digest'] = metadata.digest

    if metadata.nlines is not None:
        result['nlines'] = metadata.nlines

    if metadata.original_nlines is not None:
        result['original_nlines'] = metadata.original_nlines

    result = {**result, **metadata.__dict__}
    result['raw_content'] = '\n'.join(text)

    # Determine the output directory
    if use_hash_directories:
        dir1 = file_digest[:2]
        dir2 = file_digest[2:4]
        output_dir = os.path.join(output_dir, dir1, dir2)

    os.makedirs(output_dir, exist_ok=True)

    # Write the result to a temporary file and then rename it
    basename = os.path.splitext(get_output_name(file_path))[0]
    output_file_tmp = os.path.join(output_dir, f"{basename}.json.tmp")
    output_file_final = os.path.join(output_dir, f"{basename}.json")
    with open(output_file_tmp, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=json_default_serializer)
    os.rename(output_file_tmp, output_file_final)


def process_file_wrapper(arg):
    # For some reason we can't make this anonymous or local because someone
    # wants to pickle it.
    file_path, output_dir, use_hash_directories = arg
    try:
        result = process_file(file_path, output_dir, use_hash_directories)
    except Exception as e:
        estr = format_exception(e)
        logger.error(f"Exception raised when processing '{file_path}':{estr}")


def main():
    parser = argparse.ArgumentParser(description="Extract text from files in a directory")
    parser.add_argument("input_dir", help="Path to the input directory")
    parser.add_argument("output_dir", help="Path to the output .json.gz file")
    parser.add_argument("--hash_based_partition", help="Partition the output dir based on the ", type=bool, default=False)
    parser.add_argument("--use_hash_directories", action="store_true",
                        help="Use hash-based directory structure for output (default: False)")
    parser.add_argument("--num_processes", type=int, default=mp.cpu_count(),
                        help="Number of processes to use (default: number of CPU cores)")
    parser.add_argument("--logdir", type=str, default="logs",
                        help="Name of the log directory (default: %(default)s)")
    parser.add_argument("--loglevel", type=str, default="INFO",
                        help="Lowest log level for which to record messages (default: %(default)s)")
    parser.add_argument("--logstderr", action="store_true",
                        help="Also print the logs to stderr")

    args = parser.parse_args()

    setup_logging(args.logdir, stderr=args.logstderr, level=args.loglevel)
    global logger
    logger = getLogger()

    os.makedirs(args.output_dir, exist_ok=True)

    file_list = []
    for root, _, files in os.walk(args.input_dir):
        for file in files:
            input_file_path = os.path.join(root, file)
            output_filename = get_output_name(input_file_path)
            output_dir = args.output_dir
            # Determine the output directory
            if args.use_hash_directories:
                file_digest = compute_sha1(input_file_path)
                dir1 = file_digest[:2]
                dir2 = file_digest[2:4]
                output_dir = os.path.join(output_dir, dir1, dir2)

            output_file_path = os.path.join(output_dir, output_filename)
            if not os.path.exists(output_file_path):
                file_list.append(input_file_path)
            else:
                logger.info(f"File '{input_file_path}' already processed")

    with mp.Pool(initializer=init_proc, initargs=[args], processes=args.num_processes) as pool:
        with tqdm(total=len(file_list), desc="Extracting text", unit="file") as pbar:
            for _ in pool.imap_unordered(process_file_wrapper, [(file, args.output_dir, args.use_hash_directories) for file in file_list]):
                pbar.update()


if __name__ == "__main__":
    main()
