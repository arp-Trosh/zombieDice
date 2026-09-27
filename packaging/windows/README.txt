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
  F switches the bots' speed in single player; P plays again once a game is over (host).
  Left/Right arrows + Enter, or the mouse, work the buttons. Rules are in the game's README:
  https://github.com/arp-Trosh/zombieDice

MULTIPLAYER
  One player picks Multiplayer > Host Game and tells the others the address shown in the lobby.
  The others pick Join Game and enter it. Everyone must be on the same network, or the host has
  to forward the port (5555 by default).

  The first time you HOST, Windows Firewall asks whether to allow "Python" (that's this game)
  on networks: allow it on Private networks. Joining a game and single player never ask.

SHARPER GRAPHICS
  F2, F3 and F4 cycle the graphics, colours and frame rate while you play; the bottom line
  always shows the current settings and the frame rate achieved.
  In Windows Terminal the game uses its finest graphics automatically. In the classic console it
  uses a coarser set that works with any font; if your console font is Cascadia, you can ask for
  the finer one: open a Command Prompt in the ZombieDice folder and run
      set UNICODE3D_GLYPHS=sextant
      ZombieDice.exe
  If you ever see boxes or question marks instead of dice (for instance after changing Windows
  Terminal's font), close it and run the same way with UNICODE3D_GLYPHS=quad.
  Your player name is your Windows user name. You can change it on the Multiplayer screen, or
  set it for every game by running
      set ZOMBIEDICE_NAME=YourName
  before ZombieDice.exe the same way.
