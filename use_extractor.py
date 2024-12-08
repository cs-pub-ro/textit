from re import L
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
import bisect


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from textit.text_extractor import TextExtractor, Metadata, FileType, DocumentClass
from textit.processors import text_repair, quality_filter, language_identification
from textit.helpers import handle_result, setup_logging, format_exception
from textit.helpers import getLogger, get_path_hash, get_all_files
import textit.version

import subprocess


# For sha1 calculation
CHUNK_SIZE = 2 ** 16


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
        logger.error(f"Couldn't get file type for '{file_path}':\n```\n{e}```\n\n")
        return None
    # XXX Dubious
    # except FileNotFoundError:
        # logger.error("Error: 'file' command not found")
        # return None


def json_default_serializer(obj):
    return obj.name


def compute_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as file:
        while chunk := file.read(CHUNK_SIZE):
            sha1.update(chunk)

    return sha1.hexdigest()


def process_file(input_path: str, output_path: str) -> None:
    extractor = TextExtractor()
    extractor.add_processor(text_repair)
    extractor.add_processor(quality_filter)
    extractor.add_processor(language_identification)

    file_type = get_file_type(input_path)
    file_digest = compute_sha1(input_path)
    logger.info(f"Processing '{input_path}' (type: {file_type}, digest: "
                f"{file_digest})")
    metadata = Metadata(file_type=file_type, document_class=DocumentClass.CRAWLED)
    _, basename = os.path.split(input_path)
    title = os.path.splitext(basename)[0]

    # While we can deal with non-UTF-8 filenames, other tools down the line,
    # may not be able to, so here we do first copy a file to temporary, UTF-8
    # path.
    url = input_path
    try:
        input_path.encode("utf-8")
        logger.debug(f"UTF-8 filename: '{input_path}'")
        result, metadata = extractor.extract_text(input_path, metadata)
    except UnicodeEncodeError:
        url = input_path.encode("utf-8", "surrogateescape")
        logger.debug(f"Non-UTF-8 filename: '{input_path}'")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_output:
            shutil.copy2(input_path, temp_output.name)
            result, metadata = extractor.extract_text(temp_output.name, metadata)

    assert(metadata is not None)

    if result.is_ok():
        logger.debug(f"Text extraction successful for '{input_path}'")
        text = result.unwrap()
    else:
        logger.debug(f"Text extraction failed for '{input_path}': {result}")
        text = ""

    metadata.version = textit.version.__version__
    result = {k: v for k, v in metadata.__dict__.items() if v is not None}
    result["url"] = url
    result["digest"] = "sha1:" + file_digest
    result["raw_content"] = "\n".join(text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output_file_tmp = output_path + ".tmp"
    with open(output_file_tmp, "w", encoding="utf-8", errors="surrogateescape") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=json_default_serializer)

    os.rename(output_file_tmp, output_path)


def process_file_wrapper(arg):
    # For some reason we can't make this anonymous or local because someone
    # wants to pickle it.
    input_path, output_path = arg
    try:
        result = process_file(input_path, output_path)
    except Exception as e:
        estr = format_exception(e)
        logger.error(f"Exception raised when processing '{input_path}':{estr}")


def get_basename_noext(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def create_task(path: str, output_dir: str, prefix: str) -> tuple[str, str]:
    hashed_input_path = path
    if prefix is not None:
        relpath = os.path.relpath(path, prefix)
        hashed_input_path = relpath

    # Determine the output directory
    input_path_hash = get_path_hash(hashed_input_path)
    output_dir = os.path.join(output_dir, os.path.dirname(hashed_input_path))
    output_filename = input_path_hash + ".json"
    output_file_path = os.path.join(output_dir, output_filename)
    return path, output_file_path


def main():
    parser = argparse.ArgumentParser(description="Extract text from files in a directory")
    parser.add_argument("input_dir", help="Path to the input directory")
    parser.add_argument("output_dir", help="Path to the output .json.gz file")
    parser.add_argument("--num_processes", type=int, default=mp.cpu_count(),
                        help="Number of processes to use (default: number of CPU cores)")
    parser.add_argument("--prefix", type=str, default=None, help="Directory prefix to ignore.")
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

    existing_files = get_all_files(args.output_dir)
    existing_hashes = {get_basename_noext(file) for file in existing_files}

    input_files = get_all_files(args.input_dir)
    tasks = (create_task(file, args.output_dir, args.prefix) for file in input_files)
    tasks = filter(lambda e: get_basename_noext(e[1]) not in existing_hashes, tasks)
    tasks = sorted(tasks, key=lambda e: os.path.getsize(e[0]))
    tasks_str = "\n\t".join(task[0] for task in tasks)
    logger.info(f"Processing files:\n\t{tasks_str}")

    with mp.Pool(initializer=init_proc, initargs=[args], processes=args.num_processes) as pool:
        with tqdm(total=len(tasks), desc="Extracting text", unit="file") as pbar:
            for _ in pool.imap_unordered(process_file_wrapper, tasks):
                pbar.update()


if __name__ == "__main__":
    main()
