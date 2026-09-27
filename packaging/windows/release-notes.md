## Zombie Dice {VERSION}

Eat brains, don't get shot: the Zombie Dice push-your-luck game in 3D, in your terminal. Play alone
against up to 7 computer zombies, or with friends over your network.

### Windows

1. Download **ZombieDice-{VERSION}-windows-x64.zip** below.
2. Extract the whole zip (right-click > Extract All).
3. Open the `ZombieDice` folder and double-click **ZombieDice.exe**.

Needs Windows 10 or 11; nothing to install. Windows Terminal (the default on Windows 11) looks best.
The first start takes about 10 seconds while the 3D graphics are compiled for your PC; later starts
are quick.

`ZombieDice.exe` is the official `python.exe` from python.org's embeddable package, renamed and
still signed by the Python Software Foundation. The release contains no unsigned or packed
executable, so Windows has nothing to warn you about. The first time you **host** a multiplayer
game, Windows Firewall asks to allow "Python": allow it on private networks.

The included README.txt covers controls, multiplayer and sharper graphics.

### Linux / macOS

From the source code (Python 3.10 or later):

```sh
git clone https://github.com/arp-Trosh/zombieDice
cd zombieDice
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m zombie
```
