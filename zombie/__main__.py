"""Zombie Dice in the terminal: python -m zombie [--name NAME]"""
import argparse
import curses
import getpass

from unicode3d.terminal import init_locale, run_loop

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
    parser.add_argument("--ascii", action="store_true", help="draw with ASCII characters instead of Unicode blocks")
    args = parser.parse_args()
    init_locale()
    app = App(args.name[:MAX_NAME])

    def run(stdscr):
        curses.mousemask(curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)
        curses.mouseinterval(0)
        run_loop(stdscr, app.frame, args.fps, "ascii" if args.ascii else None)

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()


if __name__ == "__main__":
    main()
