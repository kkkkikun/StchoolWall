"""Delete oldest complete SchoolWall logical dumps; unrelated/partial files are ignored."""
import argparse
import re
from pathlib import Path

NAME = re.compile(r"ey_wall_\d{4}-\d{2}-\d{2}_\d{6}\.sql\.gz\Z")


def prune(directory: Path, keep: int) -> list[Path]:
    if keep < 1:
        raise ValueError("keep must be positive")
    complete = sorted(p for p in directory.iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink())
    removed = complete[:-keep]
    for path in removed:
        path.unlink()
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("keep", type=int)
    args = parser.parse_args()
    for removed in prune(args.directory, args.keep):
        print(f"pruned {removed.name}")
