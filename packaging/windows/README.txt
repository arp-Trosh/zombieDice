ZOMBIE DICE {VERSION} for Windows
=================================

Eat brains, don't get shot. A 3D dice game that runs in your terminal.

STARTING
  1. Extract the whole zip first (right-click > Extract All). Don't run it from inside the zip.
  2. Open the ZombieDice folder and double-click ZombieDice.exe.

  It needs Windows 10 or 11 and a window of at least 80x24. Windows Terminal (the default on
  Windows 11, and free in the Microsoft Store for Windows 10) looks best. Nothing to install;
  to uninstall, delete the folder.

  About the exe: ZombieDice.exe is the official Python program from python.org, renamed. It is
  signed by the Python Software Foundation, so Windows should run it without a warning.

PLAYING
  R roll, S stop and bank your brains, T or Tab chat, Q leave (press twice).
  Arrow keys + Enter, or the mouse, work the buttons. Rules are in the game's README:
  https://github.com/arp-Trosh/zombieDice

MULTIPLAYER
  One player picks Multiplayer > Host Game and tells the others the address shown in the lobby.
  The others pick Join Game and enter it. Everyone must be on the same network, or the host has
  to forward the port (5555 by default).

  The first time you HOST, Windows Firewall asks whether to allow "Python" (that's this game)
  on networks: allow it on Private networks. Joining a game and single player never ask.

SHARPER GRAPHICS
  For finer detail, if your font has the characters (Cascadia, Windows Terminal's default, does),
  open a Command Prompt in the ZombieDice folder and run:
      set UNICODE3D_GLYPHS=sextant
      ZombieDice.exe
  If you see boxes or question marks instead of dice, close it and start the game normally.
  Your player name is your Windows user name; to use another one, run
      set ZOMBIEDICE_NAME=YourName
  before ZombieDice.exe the same way.
