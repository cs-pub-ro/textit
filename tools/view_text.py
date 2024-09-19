#!/usr/bin/env python3
import json
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Get quality statistics")
    parser.add_argument("src", help="File to read")
    parser.add_argument("--out", help="Path where to write human-readable text (if absent, will write to stdout).")

    args = parser.parse_args()
    with open(args.src, "r") as fin:
        js = json.load(fin)

    assert "raw_content" in js, "Malformed json, missing 'raw_content'!"

    if args.out:
        with open(args.out, "w") as fout:
            fout.write(js["raw_content"])
    else:
        print(js["raw_content"])


if __name__ == "__main__":
    main()
