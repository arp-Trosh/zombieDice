# zombieDice

Terminal dice game rendered in 3D with Unicode block characters in 24-bit colour, in Python with numpy and Numba.
Runs in Windows Terminal and in Linux/macOS terminals. The 3D graphics come from
[unicode3d](https://github.com/arp-Trosh/unicode3d), a separate terminal renderer that falls back to
256 or 16 colours and to ASCII on terminals that need it.

## Play

```sh
python3 -m venv .venv && . .venv/bin/activate   # Windows: py -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt                  # numpy, Numba and unicode3d (Python 3.10 or later)
python3 -m zombie [--name NAME]                  # the game (needs an 80x24 terminal; bigger looks better)
```

Your player name defaults to your login name; `--name` (or the Multiplayer screen) changes it. The
first start compiles the 3D renderer, which takes 10-20 seconds ("First run compile, please
wait..."); later starts are quick.

**Windows, no Python needed:** download `ZombieDice-<version>-windows-x64.zip` from the
[Releases page](https://github.com/arp-Trosh/zombieDice/releases), extract it, and double-click
`ZombieDice.exe`. With Python installed you can also run it from source (`py -m zombie`). The display
is detected automatically; these flags override it:

- `--glyphs sextant|quad|half|ascii`: how finely cells are divided. `sextant` shows the most detail
  but needs the Unicode 13 "legacy computing" block symbols, so it is the default only in terminals
  known to show them: Windows Terminal (its font, Cascadia, has them), kitty, WezTerm, foot and
  Ghostty. Everywhere else the default is `quad`, which works with any font. If you see boxes or
  question marks, use `--glyphs quad`.
- `--color truecolor|256|16|mono`: colour depth.
- `--ascii`: plain characters, for terminals without Unicode.
- `--fps N`: the frame rate to aim for (default 30).

The environment variables `UNICODE3D_GLYPHS` and `UNICODE3D_COLOR` set the same things. While
playing, on any screen, `F2` cycles the glyphs (half, quad, sextant, ascii), `F3` the colours
(truecolor, 256, 16, mono), `F4` the frame rate (30, 60, 120, 144), `F5` switches shadows on and off
and `F6` reflections (turning those two off makes every 3D view quicker to draw on a slow PC). The
bottom row is a status line that always shows the current settings, each field at a fixed width so
nothing moves, and the frame rate as achieved/target (e.g. `41/60fps`); click a setting to change it.

**Everything the 3D shows is also written out as text**: whose turn it is, each die's colour and
face, the running tally, the cup, busts, banked brains and the winner are all in plain words on the
screen and in the chat log. If the graphics are hard to make out in your terminal (or you'd rather
not have them), `--glyphs ascii`, `F5` and `F6` keep them simple, and the game plays exactly the same.

**The main menu** stands in a graveyard at night: zombies shamble after the living, catch them and
eat their brains, and the eaten rise again as zombies, until a hunter strolls in and shotguns a few
into flying pieces. Click a zombie to shoot it yourself. The menus are plain text over the scene.

- **Single Player**: pick the number of players (2-8, default 6), then play against that many
  computer zombies minus you.
- **Multiplayer** opens one form for both hosting and joining, where you can also change your name.
- **Multiplayer > Host Game**: pick the number of players (2-8 seats, default 4) and a port (5555 by
  default). Choose whether to allow **Bots**. The lobby shows your LAN address; the host can still change the
  seat count with `-`/`+` and flip bots on/off with `B`. With bots on, open seats are filled with bots
  at Start and a player who leaves mid-game is taken over by a bot; with bots off it's humans only
  (at least two needed) and a player who leaves has their turns skipped. Joins are refused once every
  seat is taken.
- **Multiplayer > Join Game**: enter the host's address and port.

In game: `R` roll, `S` stop and eat your brains, `T`/`Tab` chat, `F` bot speed (single player),
`P` play again (host, once the game is over), `Q` leave (press twice to confirm), Left/Right arrows +
Enter or Space for the buttons, Up/Down (or Page Up/Down, or the mouse wheel over it) to scroll the
Dice Kept panel. Mouse clicks work too.

### How to play

You're a zombie. On your turn you shake the cup and roll three dice, trying to eat as many brains
as you can before the humans shoot you three times. Keep pushing your luck, or stop and bank what
you have.

1. **Roll** (`R`). Three dice are drawn at random from the cup and rolled. Each face is one of:
   - **Brain**: you ate a brain. The die is set aside and counts toward this turn's total.
   - **Shotgun**: you got shot. The die is set aside. Three shotguns in one turn and you're done.
   - **Footsteps**: your victim ran. The die stays in your hand and is rolled again if you keep going.
2. **Decide.** Roll again (`R`) or **stop** (`S`) and add this turn's brains to your score.
   You must roll at least once before you can stop.
3. **Rolling again** always rolls three dice: your footstep dice first, topped up with new dice
   from the cup.
4. **Bust.** Reach 3 shotguns and your turn ends immediately, scoring nothing for that turn.
   Brains banked on earlier turns are safe.

### The rules

- **The cup** holds 13 dice, refilled and shuffled at the start of every turn:

  | die | count | brains | footsteps | shotguns | feel |
  |-----|:-----:|:------:|:---------:|:--------:|------|
  | green  | 6 | 3 | 2 | 1 | safe |
  | yellow | 4 | 2 | 2 | 2 | even |
  | red    | 3 | 1 | 2 | 3 | dangerous |

- **Running out of dice:** if the cup can't supply enough dice to make three, your brain dice go
  back into the cup (you keep credit for those brains) and the draw continues from there.
  Shotgun dice never go back.
- **Winning:** the first player to reach **13 brains** starts the **final round**: every other player
  gets one last turn. After that, the highest score wins; equal top scores
  share the win.
- Turn order follows the scoreboard, top to bottom.

### The game screen

```
+-----------+--------------------------------------------+ +-------------------+
| Dice Kept |               ~ YOUR TURN ~                | |    Scoreboard     |
|           |                                            | | > You (you)    4  |
| Brains 2  |                                            | |   ####.........   |
| Shots 1/3 |              3D dice tray                  | |   Rotbeard     9  |
|           |        (the dice you just rolled)          | |   #########....   |
|  [brain]  |                                            | |        ...        |
|  [brain]  |                                            | |                   |
|  [  X  ]  |                                            | | First to 13 brains|
|  [feet ]  |                                            | | dice legend       |
+-----------+--------------------------------------------+ |                   |
 Brains this turn: 2 BB   Shotguns: 1/3 X                  |                   |
 Footsteps to reroll: F   Cup: 4 green  3 yellow  2 red    |                   |
 [Roll Dice (R)] [Stop & Eat Brains (S)] [Leave (Q)]       |                   |
+----------------------------------------------------------+-------------------+
| Chat                                                                         |
| game log, rolls, busts, and players' messages                                |
| Press T or Tab to talk                                                       |
+------------------------------------------------------------------------------+
      F2 sextant  F3 truecolor  F4 30/30fps    F5 shadows     F6 reflections
```

- **Dice tray** (centre, top): the 3D dice pour out of the glass cup at the left of the tray and tumble in
  when anyone rolls, landing face up on the result with the picture upright, the camera framing the
  tray to fill the area, with the result written under each die (`BRAIN`,
  `BLAM!`, `RAN`). The cup holds the dice still left in it this turn. The banner across the top says
  whose turn it is, and flags the **FINAL ROUND**. A bust flashes the tray red and shakes it (BLAM!),
  and banking brains flashes it green (BRAINS!). Click the cup on your turn to roll; click a die or
  the cup to have it described in words under the banner. When the game ends, a **GAME OVER** box
  here names the winner, over a trophy in falling confetti.
- **Dice Kept** (left): this turn's running tally, with a rocking token for every die set aside:
  brains, shotguns (X), and footsteps waiting to be rerolled. `+N brains eaten earlier` counts
  brains whose dice went back into an empty cup. It widens on terminals 120+ columns wide. When
  more dice are kept than fit, its bottom row scrolls: `^ 3-4 of 7 v` tells which are showing, and
  Up/Down, the mouse wheel over the panel, or a click on `^`/`v` scrolls it.
- **Status lines** (below the tray): the same turn at a glance in text, coloured by die:
  `B` brains, `X` shotguns, `F` footsteps to reroll, plus how many of each colour are still in
  the cup. Use this to judge the risk of the next roll.
- **Buttons** (under the status lines): Roll Dice, Stop & Eat Brains, Speed (single player: bots
  play at x1 or x3), and Leave. After the game the host gets **Play Again**. Buttons grey out when
  it's not your turn. When the full labels don't fit, they shorten to the key and a word
  (`R Roll`, `S Stop`, `F x1`, `Q Leave`).
- **Scoreboard** (right): every player in turn order with their score and a progress bar to 13.
  `>` marks whose turn it is, `*` the winner(s); `(you)`, `bot` and `left` tag players. When there's
  room, a legend at the bottom shows each die colour's faces.
- **Chat** (bottom, full width): the game log (rolls, busts, banked brains, whose turn it is) mixed
  with players' messages and the bots' trash talk. Press `T` or `Tab` to type, `Enter` to send,
  `Esc` to cancel.
- **Display settings** (bottom row, on every screen): glyphs, colours, frame rate, shadows and
  reflections; see [Play](#play).

The **lobby** (multiplayer, before the game) has the player list on the left with open seats,
your LAN address across the top, tips and keys on the right above the table in 3D (everyone seated
as a zombie in their name colour and named over their head, bots with blue eyes, open seats taken
by see-through ghosts), and the same chat box at the bottom.

### How it's built

| module | role |
|--------|------|
| `zombie/rules.py`    | the rules: 13-die cup, draws, footsteps rerolled, 3 shotguns bust, brains recycled when the cup runs dry, final round |
| `zombie/bots.py`     | NPC names, trash talk, and the AI: Monte Carlo bust odds against a per-bot risk appetite that shrinks as brains pile up; in the final round it keeps rolling until it's ahead |
| `zombie/session.py`  | `HostSession` runs the game (single player = host with no server); `ClientSession` mirrors a remote host. Both hand the UI the same state snapshots |
| `zombie/net.py`      | TCP, newline-delimited JSON, background reader threads |
| `zombie/graphics.py` | the voxel title logo (its font, slime and animation), zombie dice meshes, the dice tray (table, glass cup, flashes, trophy and confetti), the Dice Kept tokens (brain, footprint, X), and the shadows/reflections switches shared by every renderer |
| `zombie/horde.py`    | the graveyard behind the menus (people built as scene graphs, zombies, humans and hunters, flying gibs) and the 3D lobby table |
| `zombie/ui.py`       | menu, multiplayer setup, lobby and game screens |

The host is authoritative: clients send `hello`, `chat` and `act` (`roll`/`stop`) messages; the host
broadcasts `state` snapshots and `chat` lines. A player who disconnects mid-game is taken over by a bot
(or, with bots off, skipped).

## The engine: unicode3d

The renderer lives in its own repository, [arp-Trosh/unicode3d](https://github.com/arp-Trosh/unicode3d),
which documents how it draws and its API. `requirements.txt` pins the version the game uses (a git
tag, currently `v0.4.0`); the game uses `unicode3d`'s public modules and builds its dice on
`unicode3d.examples.dice`. Engine features on show:

| where | what it uses |
|-------|--------------|
| menu graveyard | a sky box of stars, a moon and flames that glow (emissive), moonlight and a campfire casting shadows (sun and point light), a green lantern, a puddle that mirrors the zombies, fog, people built as scene graphs (`Node`s for joints), picking (click a zombie), gibs fading out (transparency), per-vertex colours on the ground and the logo, textured headstones |
| logo | extruded voxel text (`text_mesh`'s bitmaps) with vertex-colour gradients, slightly reflective, parented to a `Node` that floats it in front of the camera |
| dice tray | a wood-textured table, a lacquered tray floor that mirrors the dice, shadows from a lamp and a flickering candle, a see-through glass cup with the cup's dice inside, flash lights, a lathe-turned golden trophy reflecting the sky, confetti (many small objects), picking |
| Dice Kept | small cached renders of pillow-shaped tokens |
| lobby | a mirror-topped table under a lamp casting shadows, see-through ghosts in the open seats, names placed over heads with `Renderer.project` |
| status line | `unicode3d.ui.DisplayControls` (F2-F6), switching shadows and reflections in every renderer at once |

### Working on the engine and the game together

Keep both checkouts side by side in the same folder (`unicode3d/` and `zombieDice/`)
and install the engine in editable mode, so the game runs your working copy of it:

```sh
. .venv/bin/activate
pip install -e ../unicode3d     # engine edits take effect the next time the game starts
python3 -m unittest             # the game's tests (the engine's are in its own repo)
```

`pip install -r requirements.txt` goes back to the pinned release. To move the game to a new engine
release: tag it in unicode3d (`git tag v0.2.0 && git push --tags`), change the tag in
`requirements.txt`, test, and commit.

### Windows release

`.github/workflows/windows-release.yml` builds the zip on a Windows runner
whenever a `v*` tag is pushed, and publishes it as a GitHub release; run by hand, it builds and
tests without publishing. The exe is `python.exe` from
python.org's embeddable package, renamed, so the only executable is the one signed by the Python
Software Foundation. SmartScreen and Defender have no unknown or packed program to flag, as they often
do with PyInstaller bundles. `ZombieDice._pth` enables the site module, and a `.pth` file starts
`zombiedice_launch.py`, which runs the game and exits. The workflow runs the unit tests on Windows,
checks the exe's signature, runs a packaged self-test (`ZOMBIEDICE_SELFTEST=1`), and plays a game
through ConPTY (the console layer Windows Terminal uses) before publishing. The files are in
`packaging/windows/`.

## License

Zombie Dice is not licensed for reuse: all rights reserved. The unicode3d engine it uses is free
software under the GNU LGPL 3.0 or later (see its repository); the Windows release includes its
license texts.

---

*Disclaimer: This project was created with Claude Code.*
