"""Create a clip-desk workspace (ICM stage folders + config) in a new folder.

usage: python init_desk.py <folder>
Then edit <folder>/config/desk.json (copy of desk.example.json) and set CLIP_DESK_HOME=<folder>.
"""
import shutil, sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "desk-template"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dst = Path(sys.argv[1]).resolve()
    if dst.exists() and any(dst.iterdir()):
        sys.exit(f"{dst} is not empty; pick a new folder")
    shutil.copytree(TEMPLATE, dst, dirs_exist_ok=True)
    shutil.copy2(dst / "config" / "desk.example.json", dst / "config" / "desk.json")
    (dst / "jobs").mkdir(exist_ok=True)
    print(f"workspace created: {dst}\nnext: edit {dst / 'config' / 'desk.json'} (allowlist!), then\n"
          f"  set CLIP_DESK_HOME={dst}\n  python {TEMPLATE.parent / 'scripts' / 'pipeline.py'} status")


if __name__ == "__main__":
    main()
