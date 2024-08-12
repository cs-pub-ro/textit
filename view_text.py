#!/usr/bin/env python3
import json
import sys


def main():
    assert len(sys.argv) == 3, "Usage: ./extract <input-json> <output-txt>!"
    with open(sys.argv[1], "r") as fin:
        js = json.load(fin)

    assert "raw_content" in js, "Malformed json, missing 'raw_content'!"
    with open(sys.argv[2], "w") as fout:
        fout.write(js["raw_content"])


if __name__ == "__main__":
    main()
