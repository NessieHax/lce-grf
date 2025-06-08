import argparse
import os
from pprint import pprint
from GRFFileParser import GRFFileParser

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("grf_file", type=str)
    args = parser.parse_args()

    if not os.path.exists(args.grf_file): raise FileNotFoundError("file not found")
    with open(args.grf_file, "rb") as grf_file:
        grf = GRFFileParser()
        grf.parse(grf_file)

if __name__ == "__main__":
    main()