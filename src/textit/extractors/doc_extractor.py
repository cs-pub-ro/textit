from typing import List
from textit.metadata import Metadata
from textit.helpers import Result, format_exception

import subprocess
import os
from multiprocessing import Lock
import tempfile
import shutil
#doc_lock = Lock()

def doc_handler(file_path: str, metadata: Metadata) -> tuple[Result[List[str]], Metadata]:
    try:
        # Sadly we can only process one doc at a time
        #with doc_lock:
        tmpdir = tempfile.mkdtemp()
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        output_file = f"{file_name}.txt"
        user_install_arg = f"-env:UserInstallation=file://{os.path.abspath(tmpdir)}"
        # Run the LibreOffice command
        try:
            result = subprocess.run(["soffice",
                                     "--headless",
                                     "--invisible",
                                     "--nodefault",
                                     "--norestore", 
                                     user_install_arg,
                                     "--convert-to", "txt:Text", file_path], 
                                    check=True, capture_output=True, text=True, timeout=35)
        except subprocess.CalledProcessError as e:
            shutil.rmtree(tmpdir) 
            raise RuntimeError(f"Error converting file - {file_path}: {e.stderr}")

        shutil.rmtree(tmpdir) 
        # Read the content of the output file
        try:
            with open(output_file, 'r') as f:
                text_content = f.read()
        except IOError as e:
            os.remove(output_file)
            raise RuntimeError(f"Error reading output file: {str(e)}")
        
        # Remove the temporary output file
        os.remove(output_file)
        return Result.ok([text_content]), metadata
    except Exception as e:
        estr = format_exception(e)
        return Result.err(f"Error extracting text from DOC/X at '{file_path}':{estr}"), metadata
