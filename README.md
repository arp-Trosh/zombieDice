# zombieDice

Terminal dice game rendered in 3D with Unicode half blocks and 256 colours, using curses + numpy.
The `unicode3d` renderer started as a Python port, in spirit, of
[ShakedAp/ASCII-renderer](https://github.com/ShakedAp/ASCII-renderer), and still falls back to ASCII
on terminals without Unicode or 256 colours.

## Play

```sh
pip install -r requirements.txt   # just numpy
python3 -m zombie [--name NAME] [--ascii]  # the game (needs an 80x24 terminal; bigger looks better)
```

- **Single Player**: pick the number of players (2-8, default 6), then play against that many
  computer zombies minus you.
- **Multiplayer > Host Game**: pick the number of players (2-8 seats) and a port (5555 by default).
  Choose whether to allow **Bots**. The lobby shows your LAN address; the host can still change the
  seat count with `-`/`+` and flip bots on/off with `B`. With bots on, open seats are filled with bots
  at Start and a player who leaves mid-game is taken over by a bot; with bots off it's humans only
  (at least two needed) and a player who leaves has their turns skipped. Joins are refused once every
  seat is taken.
- **Multiplayer > Join Game**: enter the host's address and port.

In game: `R` roll, `S` stop and eat your brains, `T`/`Tab` chat, `F` bot speed (single player),
`P` play again (host, once the game is over), `Q` leave (press twice to confirm), arrow keys +
Enter for the buttons. Mouse clicks work too.

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
```

- **Dice tray** (centre, top): the 3D dice tumble here when anyone rolls, landing face up on the
  result. The banner across the top says whose turn it is, and flags the **FINAL ROUND**. When the
  game ends, a **GAME OVER** box here names the winner.
- **Dice Kept** (left): this turn's running tally, with a rocking token for every die set aside:
  brains, shotguns (X), and footsteps waiting to be rerolled. `+N brains eaten earlier` counts
  brains whose dice went back into an empty cup. It widens on terminals 120+ columns wide.
- **Status lines** (below the tray): the same turn at a glance in text, coloured by die:
  `B` brains, `X` shotguns, `F` footsteps to reroll, plus how many of each colour are still in
  the cup. Use this to judge the risk of the next roll.
- **Buttons** (under the status lines): Roll Dice, Stop & Eat Brains, Speed (single player: bots
  play at x1 or x3), and Leave. After the game the host gets **Play Again**. Buttons grey out when
  it's not your turn.
- **Scoreboard** (right): every player in turn order with their score and a progress bar to 13.
  `>` marks whose turn it is, `*` the winner(s); `(you)`, `bot` and `left` tag players. When there's
  room, a legend at the bottom shows each die colour's faces.
- **Chat** (bottom, full width): the game log (rolls, busts, banked brains, whose turn it is) mixed
  with players' messages and the bots' trash talk. Press `T` or `Tab` to type, `Enter` to send,
  `Esc` to cancel.

The **lobby** (multiplayer, before the game) has the player list on the left with open seats,
your LAN address across the top, tips and keys on the right, and the same chat box at the bottom.

### How it's built

| module | role |
|--------|------|
| `zombie/rules.py`    | the rules: 13-die cup, draws, footsteps rerolled, 3 shotguns bust, brains recycled when the cup runs dry, final round |
| `zombie/bots.py`     | NPC names, trash talk, and the AI: Monte Carlo bust odds against a per-bot risk appetite that shrinks as brains pile up; in the final round it keeps rolling until it's ahead |
| `zombie/session.py`  | `HostSession` runs the game (single player = host with no server); `ClientSession` mirrors a remote host. Both hand the UI the same state snapshots |
| `zombie/net.py`      | TCP, newline-delimited JSON, background reader threads |
| `zombie/graphics.py` | extruded voxel title logo, zombie dice meshes, the dice tray, and the Dice Kept tokens (brain, footprint, X) |
| `zombie/ui.py`       | menu, multiplayer setup, lobby and game screens |

The host is authoritative: clients send `hello`, `chat` and `act` (`roll`/`stop`) messages; the host
broadcasts `state` snapshots and `chat` lines. A player who disconnects mid-game is taken over by a bot
(or, with bots off, skipped).

## Renderer demos

```sh
python3 -m unicode3d                      # dice roll demo: space rolls, +/- dice count, q quits
python3 -m unicode3d.viewer [model.obj]   # spinning model viewer (WASD/arrows, q/e spin, Esc)
python3 -m unittest                       # tests
```

All three take `--ascii` to force the character fallback. A small monospace font and a large
terminal give the best detail.

### How it draws

- **Half blocks:** each terminal cell shows two pixels, `▀` with the top pixel as the foreground
  colour and the bottom one as the background, so pixels are about square and vertical detail doubles.
  Brightness comes from a palette of 24 shades per hue picked from xterm's 256 colours (shadows keep
  their hue, so a green die stays green). Needs a UTF-8 locale and a 256-colour terminal with
  extended colour pairs (ncurses 6); otherwise it falls back to ASCII automatically.
- **ASCII fallback:** one ramp character per cell, tinted by brightness where 256 colours exist,
  or dimmed/bolded on 8-colour terminals.
- **Shading:** per-pixel Blinn-Phong lighting with interpolated vertex normals (smooth where a mesh
  shares vertices, flat where it doesn't, like cube faces), plus a specular highlight.
- **Depth cues:** surfaces dim with distance across the scene (fog), and where one surface passes in
  front of another the far side gets a dark outline.
- **Antialiasing:** every pixel is supersampled 2x2.
- **Speed:** each object's triangles are rasterized together with numpy rather than one at a time,
  and triangles crossing the camera's near plane are clipped rather than dropped.

## unicode3d layout

| module          | role |
|-----------------|------|
| `transforms.py` | projection/view matrices, quaternions |
| `mesh.py`       | `Mesh` with vertex normals, OBJ loader, textured `make_box` |
| `raster.py`     | pixel `FrameBuffer` (shade, colour, depth; two pixels per cell), vectorized z-buffered rasterizer, perspective-correct interpolation, near-plane clipping |
| `scene.py`      | `Camera`, `Light`, `Object3D`, `Renderer` (transform, cull, per-pixel lighting, supersampling, fog, outlines) |
| `terminal.py`   | 256-colour shade palette, half-block and ASCII drawing, curses `Screen`, `run_loop` |
| `dice.py`       | pip-textured die, `orientation_showing`, `top_face`, `RollAnimation` (result chosen first, then animated to land on it) |

Custom dice faces (e.g. brains/shotguns) are just six textures passed to `make_box`:
2D float arrays where 1.0 is full brightness and 0.0 renders as the darkest shade.
