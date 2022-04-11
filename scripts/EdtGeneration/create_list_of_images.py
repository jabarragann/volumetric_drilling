from pathlib import Path
import argparse
import re


if __name__ == "__main__":

    # Arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Root directory where data is located")
    args = parser.parse_args()

    files = []
    for f in Path(args.root).glob("*.png"):
        step = re.findall("[0-9]+", f.name)
        if len(step) > 0:
            files.append([int(step[0]), str(f.resolve())])

    # Sort files
    files = sorted(files, key=lambda x: x[0])

    # Create txt
    f = Path(args.root)
    f = f / f.with_suffix(".txt").name

    with open(f, "w") as f_h:
        for s, name in files:
            f_h.write(name + "\n")

    print(f"saving to {f}")
    print(files[:4])
