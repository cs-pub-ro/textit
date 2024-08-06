# TextIT


## Prerequisites

Get the language identification model.

```Bash
cd src/textit/processors/lang_id/ && wget https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```

## Usage

```Bash
python use_extractor.py /path/to/input/folder "" --separate_files  /path/to/output/folder
```
