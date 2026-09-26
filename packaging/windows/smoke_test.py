"""Plays the built ZombieDice.exe in a real Windows console (ConPTY, as Windows Terminal uses).

Starts a two-player single-player game, rolls, leaves, and quits from the menu, checking the
screen at each step: this exercises the Windows console setup, VT input decoding
and output that unit tests cannot. Usage: python smoke_test.py dist/ZombieDice/ZombieDice.exe
"""
import os
import re
import sys
import time

from winpty import PtyProcess

TOKEN = re.compile(r"\x1b\[([0-9;?<>]*)([ -/]*[@-~])|\x1b\][^\x07]*\x07|\x1b[@-Z\\-_]|[\r\n]|[^\x1b\r\n]+")
ROWS, COLS = 34, 110


class VirtualScreen:
    """Just enough of a terminal to follow the game's output: the game only rewrites cells that
    change, so text on screen is often never sent in one piece."""

    def __init__(self):
        self.cells = [[" "] * COLS for _ in range(ROWS)]
        self.y = self.x = 0

    def feed(self, data):
        for m in TOKEN.finditer(data):
            tok = m.group(0)
            if m.group(2):
                self._csi(m.group(1), m.group(2)[-1])
            elif tok == "\r":
                self.x = 0
            elif tok == "\n":
                self.y = min(self.y + 1, ROWS - 1)
            elif not tok.startswith("\x1b"):
                for ch in tok:
                    if self.x < COLS:
                        self.cells[self.y][self.x] = ch
                    self.x += 1

    def _csi(self, params, final):
        nums = [int(p) if p.isdigit() else 0 for p in params.lstrip("?<>").split(";")]
        if final in "Hf":
            y, x = (nums + [1, 1])[:2]
            self.y, self.x = min(max(y, 1), ROWS) - 1, min(max(x, 1), COLS) - 1
        elif final == "J" and not params.startswith("?"):
            self.cells = [[" "] * COLS for _ in range(ROWS)]
        elif final == "K":
            self.cells[self.y][self.x:] = [" "] * (COLS - self.x)
        elif final == "C":
            self.x += max(nums[0], 1)
        elif final == "G":
            self.x = max(nums[0], 1) - 1

    def text(self):
        return "\n".join("".join(row) for row in self.cells)


class Game:
    def __init__(self, exe):
        env = dict(os.environ, ZOMBIEDICE_NAME="Smoke")  # also checks the launcher passes the name on
        self.proc = PtyProcess.spawn(exe, env=env, dimensions=(ROWS, COLS))
        self.screen = VirtualScreen()

    def wait_for(self, text, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                chunk = self.proc.read(65536)
            except EOFError:
                break
            self.screen.feed(chunk)
            if text in self.screen.text():
                print(f"  saw {text!r}")
                return
            if not chunk:
                time.sleep(0.05)
        alive = self.proc.isalive()
        status = None if alive else self.proc.exitstatus
        raise AssertionError(f"never saw {text!r} (process alive: {alive}, exit status: {status}); screen:\n"
                             + self.screen.text())

    def send(self, keys):
        self.proc.write(keys)
        time.sleep(0.5)


def main(exe):
    game = Game(os.path.abspath(exe))
    game.wait_for("Single Player")
    game.send("\r")                      # Single Player
    game.wait_for("SINGLE PLAYER")
    game.send("----")                    # down to 2 players, so the one bot's turns are quick
    game.wait_for("you + 1 bot")
    game.send("\r")                      # Start Game
    game.wait_for("YOUR TURN", timeout=120)  # turn order is random: the bot may go first
    game.send("r")
    game.wait_for("Smoke rolled")
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
