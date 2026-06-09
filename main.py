from __future__ import annotations

import argparse

from gui import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omok GUI")
    parser.add_argument(
        "--engine",
        choices=("stable", "experimental"),
        default="stable",
        help="stable=omok(12) baseline (default), experimental=latest omok/",
    )
    args = parser.parse_args()
    main(engine=args.engine)
