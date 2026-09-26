"""Zombie Dice in the terminal: python -m zombie [--name NAME]"""
import argparse
import getpass

from unicode3d.terminal import add_display_args, display_options, run

from .session import MAX_NAME
from .ui import App


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    try:
        default_name = getpass.getuser().capitalize()
    except Exception:
        default_name = "Player"
    parser.add_argument("--name", default=default_name, help="your player name")
    parser.add_argument("--fps", type=int, default=30)
    add_display_args(parser)
    args = parser.parse_args()
    app = App(args.name[:MAX_NAME])
    try:
        run(app.frame, args.fps, mouse=True, title="Zombie Dice", **display_options(args))
    except KeyboardInterrupt:
        pass
    finally:
        app.close()


if __name__ == "__main__":
    main()
