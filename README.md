# TextIT


## Prerequisites

Get the language identification model.

```Bash
sudo apt install libreoffice
pip3 install -r requirements.txt
cd src/textit/processors && mkdir -p lang_id && cd lang_id && touch __init__.py && wget https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```

## Usage

The following code turns all the files from `tests/fixtures` int json files in `extracted_text`.

```Bash
python use_extractor.py tests/fixtures  extracted_text/
```

To write the files in a two level directory structure based on the hash of the file:

```
--use_hash_directories
```
