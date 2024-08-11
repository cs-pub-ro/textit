from typing import List
from textit.metadata import Metadata
from textit.helpers import Result

import subprocess
import os
from multiprocessing import Lock

doc_lock = Lock()

def doc_handler(file_path: str, metadata: Metadata) -> Result[List[str]]:
    try:
        # Sadly we can only process one doc at a time
        with doc_lock:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            output_file = f"{file_name}.txt"

            # Run the LibreOffice command
            try:
                result = subprocess.run(["soffice", "--headless", "--convert-to", "txt:Text", file_path], 
                                        check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Error converting file - {file_path}: {e.stderr}")
            
            # Read the content of the output file
            try:
                with open(output_file, 'r') as f:
                    text_content = f.read()
            except IOError as e:
                raise RuntimeError(f"Error reading output file: {str(e)}")
            
            # Remove the temporary output file
            os.remove(output_file)
            return Result.ok([text_content])
    except Exception as e:
        print(e)
        return Result.err(f"Error extracting text from DOC/X at {file_path}: {str(e)}")
