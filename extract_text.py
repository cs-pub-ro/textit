import os
import re
import fitz  # PyMuPDF
import argparse
import hashlib
import json

def extract_paragraphs_from_text(text):
    # Define a regular expression to split text into paragraphs
    paragraph_pattern = re.compile(r'(\n\n|\r\n\r\n)')

    # Split text into paragraphs
    paragraphs = paragraph_pattern.split(text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Filter out paragraphs that are likely to be page numbers
    paragraphs = [p for p in paragraphs if not re.match(r'^\d+$', p)]

    return paragraphs

def extract_text_from_pdf(pdf_path):
    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    text = ""
    
    # Iterate through each page
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        page_text = page.get_text()

        # Remove standalone numbers that are likely to be page numbers
        page_text = re.sub(r'^\d+\s*$', '', page_text, flags=re.MULTILINE)
        text += page_text

    return text

def compute_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return f"sha1:{sha1.hexdigest()}"

def process_pdfs(input_folder, output_folder):
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Check if the input folder exists
    if not os.path.exists(input_folder):
        print(f"Error: The input folder '{input_folder}' does not exist.")
        return

    # Iterate through all PDF files in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(input_folder, filename)
            output_file = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.json")

            try:
                # Extract text from PDF
                text = extract_text_from_pdf(pdf_path)

                # Extract paragraphs
                paragraphs = extract_paragraphs_from_text(text)

                # Create JSON object
                json_data = {
                    "file_type": "PDF",
                    "document_class": "CRAWLED",
                    "nlines": len(paragraphs),
                    "original_nlines": len(text.splitlines()),
                    "version": "0.3.0",
                    "url": os.path.relpath(pdf_path),
                    "digest": compute_sha1(pdf_path),
                    "raw_content": "\n\n".join(paragraphs)
                }

                # Write the JSON object to a file
                with open(output_file, 'w', encoding='utf-8') as file:
                    json.dump(json_data, file, ensure_ascii=False, indent=4)

            except Exception as e:
                print(f"Failed to process {pdf_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract paragraphs from PDF files in a specified folder")
    parser.add_argument("input_folder", help="Path to the folder containing PDF files")
    parser.add_argument("output_folder", help="Path to the folder where extracted paragraphs will be saved")
    args = parser.parse_args()

    # Convert relative paths to absolute paths
    input_folder = os.path.abspath(args.input_folder)
    output_folder = os.path.abspath(args.output_folder)

    # Check if the input folder exists
    if not os.path.exists(input_folder):
        print(f"Error: The input folder '{input_folder}' does not exist.")
    else:
        # Check if the output folder exists
        if not os.path.exists(output_folder):
            print(f"Error: The output folder '{output_folder}' does not exist.")
        else:
            process_pdfs(input_folder, output_folder)