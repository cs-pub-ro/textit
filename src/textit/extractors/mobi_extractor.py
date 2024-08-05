from typing import List
from textit.metadata import Metadata
from textit.helpers import Result

import tempfile
import shutil                                                                                                                  
import mobi
from trafilatura import extract

def mobi_handler(file_path: str, metadata: Metadata) -> Result[List[str]]:
    try:
        # Create a temporary folder for unpacking
        temp_folder = tempfile.mkdtemp()
                                                               
        # Unpack the .mobi file                                                                                                
        temp_folder, html_file = mobi.extract(file_path)
         
                                                               
        if html_file:                               
            with open(html_file, 'r', encoding='utf-8') as f:
                text_content = extract(f.read())
            # Clean up the temporary folder
            shutil.rmtree(temp_folder)

            return Result.ok([text_content])
        else:   
            shutil.rmtree(temp_folder)
            raise FileNotFoundError("No HTML file found in the unpacked .mobi content.")
    except Exception as e:
        return Result.err(f"Error extracting text from MOBI: {str(e)}")

