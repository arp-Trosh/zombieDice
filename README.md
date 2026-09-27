# zombieDice

Terminal dice game rendered in 3D with Unicode block characters in 24-bit colour, using only numpy.
Runs in Windows Terminal and in Linux/macOS terminals. The `unicode3d` renderer started as a Python
port, in spirit, of [ShakedAp/ASCII-renderer](https://github.com/ShakedAp/ASCII-renderer), and still
falls back to 256 or 16 colours and to ASCII on terminals that need it.

## Play

```sh
pip install -r requirements.txt   # just numpy
python3 -m zombie [--name NAME]   # the game (needs an 80x24 terminal; bigger looks better)
```

**Windows, no Python needed:** download `ZombieDice-<version>-windows-x64.zip` from the
[Releases page](https://github.com/arp-Trosh/zombieDice/releases), extract it, and double-click
`ZombieDice.exe`. With Python installed you can also run it from source (`py -m zombie`). The display
is detected automatically; these flags (on the game and both demos) override it:

- `--glyphs sextant|quad|half|ascii`: how finely cells are divided. `sextant` shows the most detail
  but needs the Unicode 13 "legacy computing" block symbols, so it is the default only in terminals
  known to show them: Windows Terminal (its font, Cascadia, has them), kitty, WezTerm, foot and
  Ghostty. Everywhere else the default is `quad`, which works with any font. If you see boxes or
  question marks, use `--glyphs quad`.
- `--color truecolor|256|16|mono`: colour depth.
- `--ascii`: plain characters, for terminals without Unicode.

The environment variables `UNICODE3D_GLYPHS` and `UNICODE3D_COLOR` set the same things. While
playing, on any screen, `F2` cycles the glyphs (half, quad, sextant, ascii), `F3` the colours
(truecolor, 256, 16, mono) and `F4` the frame rate (30, 60, 120, 144). The bottom row is a status
line that always shows the current settings, each field at a fixed width so nothing moves, and the
frame rate as achieved/target (e.g. `41/60fps`); click a setting to change it.

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

All three take the display flags above. A small font and a large terminal give the best detail.

### How it draws

- **Sub-cell pixels:** each terminal cell covers a small grid of pixels: 2x2 with quadrant blocks
  (`▘▝▖▗▚▞▙▟…`), 2x3 with sextants, or 1x2 with half blocks (`▀▄`). A cell shows only two colours,
  so for each cell the renderer tries every way of splitting its pixels in two and picks the glyph
  and colour pair with the least error (the approach [chafa](https://hpjansson.org/chafa/) uses).
  Edges land on the right sub-pixel while flat areas stay solid.
- **Colour:** everything is computed in linear light and converted to sRGB at the end. Truecolor
  terminals get exact 24-bit colour. On 256- or 16-colour terminals, colours are matched in the OKLab
  colour space (so a shaded green stays green) with ordered dithering instead of banding.
- **Shading:** per-pixel Blinn-Phong lighting with interpolated vertex normals (smooth where a mesh
  shares vertices, flat where it doesn't, like cube faces), plus a white specular highlight. Light
  levels are perceived brightness, so a level of 0.5 looks half as bright.
- **Antialiasing:** 4 samples per pixel in a rotated-grid pattern, so near-vertical and
  near-horizontal edges get four coverage steps instead of two. Pixels whose samples disagree
  (silhouettes, creases, overlaps) get 8 more. Each pixel is shaded once per triangle, as GPUs do with
  multisampling, and partly covered pixels blend by coverage in linear light.
- **Textures:** mipmapped with trilinear filtering, so a 48x48 face texture a dozen pixels across
  stays steady instead of shimmering as a die turns.
- **Depth cues:** surfaces dim with distance across the scene (fog), and where one surface passes in
  front of another the far side gets a dark outline.
- **Output:** the screen is a grid of cells, and each refresh sends only the cells that changed, as
  VT escape sequences, wrapped in synchronized-output markers where the terminal supports them. There
  is no curses: on Windows the console is put in VT mode, and keys and mouse clicks are read as
  console input records.
- **Speed:** each object's triangles are rasterized together, for all sample positions at once,
  with numpy rather than one at a time. Triangles crossing the camera's near plane are clipped
  rather than dropped.

## unicode3d layout

`unicode3d` is self-contained, with nothing specific to this game, and is meant to become its own
project that other terminal games use.

| module          | role |
|-----------------|------|
| `transforms.py` | projection/view matrices, quaternions |
| `mesh.py`       | `Mesh` with vertex normals and cached mipmaps, OBJ loader, textured `make_box` |
| `texture.py`    | mipmap chains and trilinear sampling |
| `raster.py`     | `FrameBuffer` (linear RGB premultiplied by coverage, alpha, depth, object ids), vectorized multi-sample z-buffered rasterizer, perspective-correct interpolation, near-plane clipping |
| `scene.py`      | `Camera`, `Light`, `Object3D`, `Renderer` (transform, cull, lighting, multisampling with extra edge samples, fog, outlines) |
| `color.py`      | sRGB/linear conversion, named `Color`s, OKLab palette matching, dithering, SGR colour codes |
| `glyphs.py`     | glyph sets (half, quad, sextant, ascii) and matching pixels to cells |
| `keys.py`       | `Key` codes, `MouseEvent`, the VT input decoder |
| `console.py`    | raw terminal I/O for POSIX (termios) and Windows (console API), colour and glyph detection |
| `terminal.py`   | `Screen` (cell grid, text, frames, diffed output), `run`, command-line display flags |
| `dice.py`       | pip-textured die, `orientation_showing`, `top_face`, `RollAnimation` (result chosen first, then animated to land on it) |

### Using it in a game

```python
from unicode3d import Camera, Color, Key, Light, Object3D, Renderer, make_box, run

cube = Object3D(make_box(), color=Color.CYAN)   # or color=(r, g, b)
renderer, camera, light = Renderer(1, 1), Camera(), Light()

def frame(screen, dt, keys):
    if ord("q") in keys or Key.ESC in keys:
        return False
    rows, cols = screen.size()
    renderer.resize(cols, rows - 1, screen.cell_pixels)  # cell_pixels depends on the glyph set
    screen.erase()
    screen.draw_frame(renderer.render([cube], camera, light))
    screen.text(rows - 1, 0, "q quits", Color.YELLOW)
    screen.refresh()

run(frame, fps=30)
```

Textures (for `make_box`, or any mesh with `uvs` and `materials`) are 2D arrays of brightness
multipliers or `(H, W, 3)` colour arrays, both 0..1 in sRGB, where 1.0 leaves the object's colour
unchanged and 0.0 is black.

### Engine reference

**Display detection.** `Screen` picks a glyph set and colour depth unless told otherwise (arguments,
the `--glyphs`/`--color` flags from `add_display_args`, or `UNICODE3D_GLYPHS`/`UNICODE3D_COLOR`):

| setting | chosen when |
|---------|-------------|
| `truecolor` | `COLORTERM=truecolor` or `24bit`, Windows Terminal (`WT_SESSION`), any Windows console, or a known truecolor terminal (kitty, WezTerm, Alacritty, foot, Ghostty, iTerm2, VS Code, ...) |
| `256` | `TERM` contains `256` |
| `mono` | `NO_COLOR` is set or `TERM=dumb` (glyphs then default to `ascii`, which still shows shading) |
| `16` | anything else |
| `sextant` glyphs | a terminal known to show sextants whatever the font: Windows Terminal (`WT_SESSION`), kitty, WezTerm, foot or Ghostty (by `TERM`, `TERM_PROGRAM` or their own variables) |
| `quad` glyphs | any other terminal with a UTF-8 locale (always on Windows) |
| `half` glyphs | the Linux text console (`TERM=linux`), whose fonts lack quadrants |
| `ascii` glyphs | no UTF-8 |

A program can't ask a terminal which characters its font has (a missing one still takes a cell,
drawn as a box), so sextants are picked by terminal, never by guessing at fonts.
`console.shows_sextants()` holds the list.

**`Renderer(width, height, cell_pixels=(1, 2), ...)` options:**

| option | default | effect |
|--------|---------|--------|
| `cell_pixels` | `(1, 2)` | pixels per cell; pass `screen.cell_pixels` to `resize()` every frame, since it follows the glyph set |
| `cell_aspect` | `0.5` | a cell's width divided by its height |
| `samples` | `4` | samples per pixel: 1, 4, 8 or 16 |
| `edge_samples` | `8` | extra samples in pixels whose samples disagree: 0, 4, 8 or 16 |
| `fog` | `0.3` | how much the farthest surfaces are dimmed |
| `outline` | `0.55` | how much the far side of a depth edge is darkened |
| `lod_bias` | `-0.5` | added to texture mip levels: lower is sharper, higher is softer |

`render()` returns the renderer's own `FrameBuffer`, which the next render reuses; `copy()` it to
cache a frame (as the Dice Kept tokens do). `fb.ids` tells you which object (its index in the render
list plus one) covers each pixel, which is handy for mouse picking. `renderer.project(point)` gives
the cell a world point landed on, for placing text labels.

**Colours and light.** `Object3D.color` takes a named `Color` or an `(r, g, b)` triple (0..255 ints
or 0..1 floats). `Light` levels (`ambient`, `diffuse`, `specular`) are perceived brightness from 0
to 1; the highlight is always white, so lower `specular` for large flat faces that would otherwise
wash out.

**`Screen` and `run()`.** `run(frame_fn, fps=30, glyphs=None, color=None, mouse=False,
background=None, title=None)` takes over the terminal (naming its window `title`, if given) and restores it however the loop ends (Ctrl-C raises
`KeyboardInterrupt`). `frame_fn(screen, dt, keys)` returns `False` to stop. `keys` holds ints (a
character's code, or a `Key` such as `Key.UP`, `Key.ENTER`, `Key.ESC`) and, with `mouse=True`,
`MouseEvent(x, y, button, pressed)` values. `screen.text()` draws in the terminal's own ANSI colours,
so text follows the user's theme. Characters that aren't exactly one cell wide are shown as `?`.
`background=(r, g, b)` fills the screen with a known colour so anti-aliased edges blend into it
exactly; by default, edges blend toward black over the terminal's own background.
`Screen(size=(rows, cols))` with no console gives an off-screen grid for tests;
`render_updates()` returns the escape sequences a refresh would send. `screen.set_glyphs(name)` and
`screen.set_color(mode)` switch modes while running (`screen.glyph_modes` lists the glyph sets the
terminal can take), and `screen.fps` is the target frame rate, which `run()` re-reads every frame;
`screen.measured_fps` is the rate it achieved over the last second.

**Performance.** At 30 fps, a 60x15-cell view of three dice takes about 5-7 ms per frame and an
80x16 title logo 12-16 ms, from half blocks to sextants. Cost grows with the pixel count, so large
views in `sextant` mode are the most expensive (about 21 ms for a 150x45 view of three rolling
dice, against 15 ms in `quad`). A scene that hasn't changed since the last `render()` (same objects,
poses, camera, light and size) isn't drawn again, so still frames cost a few milliseconds; after
editing a mesh's arrays in place, call `renderer.invalidate()`. Use `quad` if frames drop.

**Windows release.** `.github/workflows/windows-release.yml` builds the zip on a Windows runner
whenever a `v*` tag is pushed, and publishes it as a GitHub release. The exe is `python.exe` from
python.org's embeddable package, renamed, so the only executable is the one signed by the Python
Software Foundation. SmartScreen and Defender have no unknown or packed program to flag, as they often
do with PyInstaller bundles. `ZombieDice._pth` enables the site module, and a `.pth` file starts
`zombiedice_launch.py`, which runs the game and exits. The workflow runs the unit tests on Windows,
checks the exe's signature, runs a packaged self-test (`ZOMBIEDICE_SELFTEST=1`), and plays a game
through ConPTY (the console layer Windows Terminal uses) before publishing. The files are in
`packaging/windows/`.

**Windows.** Needs Windows 10 or later (for VT sequences in the console) and only numpy. Windows
Terminal is recommended, and gets sextants by default; the classic console works too, with quadrants
(its default fonts may lack sextants).
