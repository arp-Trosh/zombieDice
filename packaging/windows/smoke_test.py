"""Plays the built ZombieDice.exe in a real Windows console (ConPTY, as Windows Terminal uses).

Starts a single-player game, rolls, leaves, and quits from the menu, checking the
screen at each step: this exercises the Windows console setup, VT input decoding
and output that unit tests cannot. Usage: python smoke_test.py dist/ZombieDice/ZombieDice.exe
"""
import os
import re
import sys
import time

from winpty import PtyProcess

ANSI = re.compile(r"\x1b(\[[0-9;?<>]*[ -/]*[@-~]|\][^\x07]*\x07|[@-Z\\-_])")


class Game:
    def __init__(self, exe):
        self.proc = PtyProcess.spawn(exe, dimensions=(34, 110))
        self.seen = ""

    def wait_for(self, text, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                chunk = self.proc.read(65536)
            except EOFError:
                break
            self.seen += ANSI.sub("", chunk)
            if text in self.seen:
                self.seen = ""
                print(f"  saw {text!r}")
                return
        tail = self.seen[-1500:]
        raise AssertionError(f"never saw {text!r}; last output:\n{tail}")

    def send(self, keys):
        self.proc.write(keys)
        time.sleep(0.5)


def main(exe):
    game = Game(os.path.abspath(exe))
    game.wait_for("Single Player")
    game.send("\r")                      # Single Player
    game.wait_for("SINGLE PLAYER")
    game.send("\r")                      # start with the default number of players
    game.wait_for("YOUR TURN")
    game.send("r")
    game.wait_for("rolled")
    game.send("q")
    game.send("q")                       # leave (confirmed), back to the menu
    game.wait_for("Multiplayer")
    game.send("\x1b[B")
    game.send("\x1b[B")                  # arrow keys down to Quit
    game.send("\r")
    end = time.time() + 15
    while game.proc.isalive() and time.time() < end:
        time.sleep(0.2)
    if game.proc.isalive():
        game.proc.terminate(force=True)
        raise AssertionError("the game did not exit after Quit")
    print(f"  exited with status {game.proc.exitstatus}")
    assert game.proc.exitstatus == 0
    print("SMOKE TEST OK")


if __name__ == "__main__":
    main(sys.argv[1])
