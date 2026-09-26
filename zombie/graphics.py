"""3D pieces of the game: the title logo, zombie dice and the dice tray."""
import numpy as np

from unicode3d.dice import RollAnimation, face_texture
from unicode3d.mesh import Mesh, make_box
from unicode3d.scene import Camera, Light, Object3D, Renderer
from unicode3d.terminal import Color
from unicode3d.transforms import UP, normalize, quat_axis_angle, quat_mul, quat_to_matrix

from .rules import BRAIN, FACES, FEET, GREEN, RED, SHOTGUN, YELLOW

DIE_COLOR = {GREEN: Color.GREEN, YELLOW: Color.YELLOW, RED: Color.RED}
FACE_LABEL = {BRAIN: "BRAIN", SHOTGUN: "BLAM!", FEET: "RAN"}

# ----- 3D title --------------------------------------------------------------------

FONT = {
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    " ": ["..", "..", "..", "..", "..", "..", ".."],
}


def text_bitmap(text):
    rows = ["" for _ in range(7)]
    for i, ch in enumerate(text.upper()):
        glyph = FONT[ch]
        for r in range(7):
            rows[r] += ("." if i else "") + glyph[r]
    return np.array([[c == "#" for c in row] for row in rows])


def text_mesh(text, depth=1.6):
    """Extruded voxel text, one unit per font pixel, centred on the origin.

    Faces are merged into runs to keep the triangle count (and render time) down.
    """
    cells = text_bitmap(text)
    h, w = cells.shape
    padded = np.pad(cells, 1)
    verts, faces = [], []
    zf, zb = depth / 2, -depth / 2

    def quad(corners, normal):
        corners = [np.array(c, dtype=float) for c in corners]
        if np.dot(np.cross(corners[1] - corners[0], corners[2] - corners[0]), normal) < 0:
            corners.reverse()
        base = len(verts)
        verts.extend(corners)
        faces.extend([(base, base + 1, base + 2), (base, base + 2, base + 3)])

    def runs(mask):
        """(start, end) index pairs of consecutive True values."""
        edges = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
        return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))

    for r in range(h):
        y0, y1 = -(r + 1), -r
        for c0, c1 in runs(cells[r]):
            quad([(c0, y0, zf), (c1, y0, zf), (c1, y1, zf), (c0, y1, zf)], (0, 0, 1))
            quad([(c0, y0, zb), (c1, y0, zb), (c1, y1, zb), (c0, y1, zb)], (0, 0, -1))
        for c0, c1 in runs(cells[r] & ~padded[r, 1:-1]):      # nothing above
            quad([(c0, y1, zb), (c1, y1, zb), (c1, y1, zf), (c0, y1, zf)], (0, 1, 0))
        for c0, c1 in runs(cells[r] & ~padded[r + 2, 1:-1]):  # nothing below
            quad([(c0, y0, zb), (c1, y0, zb), (c1, y0, zf), (c0, y0, zf)], (0, -1, 0))
    for c in range(w):
        for r0, r1 in runs(cells[:, c] & ~padded[1:-1, c]):        # nothing to the left
            quad([(c, -r0, zb), (c, -r1, zb), (c, -r1, zf), (c, -r0, zf)], (-1, 0, 0))
        for r0, r1 in runs(cells[:, c] & ~padded[1:-1, c + 2]):    # nothing to the right
            quad([(c + 1, -r0, zb), (c + 1, -r1, zb), (c + 1, -r1, zf), (c + 1, -r0, zf)], (1, 0, 0))

    verts = np.array(verts) - [w / 2, -h / 2, 0]
    return Mesh(verts, np.array(faces, dtype=int)), w


class TitleLogo:
    """ "ZOMBIE / DICE" in chunky 3D, flying in with a spin and then wobbling gently."""

    LINES = (("ZOMBIE", Color.GREEN, 4.5), ("DICE", Color.RED, -4.5))

    def __init__(self):
        self.renderer = Renderer(1, 1)
        self.camera = Camera(target=np.zeros(3), fov=26.0, far=500.0)
        self.light = Light(direction=np.array([0.3, -0.6, -1.0]), ambient=0.15, diffuse=0.85)
        self.parts = []
        self.width = 0
        for text, color, y in self.LINES:
            mesh, w = text_mesh(text)
            self.width = max(self.width, w)
            self.parts.append((Object3D(mesh, color=color), np.array([0.0, y, 0.0])))
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        t = self.t
        intro = min(t / 1.6, 1.0)
        ease = 1 - (1 - intro) ** 3
        scale = ease * (1 + 0.15 * np.sin(np.pi * intro))  # overshoot a little
        yaw = 0.34 * np.sin(0.8 * t) + 2 * np.pi * (1 - ease)
        pitch = 0.13 * np.sin(1.1 * t + 0.5)
        roll = 0.05 * np.sin(0.7 * t + 1.0)
        rot = quat_mul(quat_axis_angle(UP, yaw), quat_mul(quat_axis_angle((1, 0, 0), pitch), quat_axis_angle((0, 0, 1), roll)))
        m = quat_to_matrix(rot)
        for obj, offset in self.parts:
            obj.rotation = rot
            obj.scale = max(scale, 1e-3)
            obj.position = m @ offset * scale

    def render(self, screen, top, left, width, height):
        if width < 10 or height < 4:
            return
        self.renderer.resize(width, height)
        tan_half = np.tan(np.radians(self.camera.fov) / 2)
        aspect = width * self.renderer.cell_aspect / height
        dist = max(11.0 / tan_half, (self.width / 2 + 4.0) / (tan_half * aspect))
        self.camera.position = np.array([0.0, 0.0, dist])
        fb = self.renderer.render([obj for obj, _ in self.parts], self.camera, self.light)
        screen.draw_frame(fb, top, left)


# ----- zombie dice -----------------------------------------------------------------

def symbol_texture(face, res=40, ink=0.05):
    tex, u, v = face_texture(res)
    if face == BRAIN:
        blob = ((u - 0.5) / 0.36) ** 2 + ((v - 0.5) / 0.3) ** 2 < 1
        folds = np.sin(u * 28 + 2.5 * np.sin(v * 18)) > 0.75
        tex[blob] = ink
        tex[blob & folds] = 0.45
    elif face == SHOTGUN:
        inside = (np.minimum(u, v) > 0.18) & (np.maximum(u, v) < 0.82)
        tex[inside & ((np.abs(u - v) < 0.1) | (np.abs(u + v - 1) < 0.1))] = ink
    elif face == FEET:
        for cu, cv in ((0.34, 0.38), (0.66, 0.62)):
            tex[((u - cu) / 0.11) ** 2 + ((v - cv) / 0.2) ** 2 < 1] = ink
    return tex


_TEXTURES = {}
_MESHES = {}


def zombie_die_mesh(color):
    """Die whose box face i shows FACES[color][i]."""
    if color not in _MESHES:
        for face in (BRAIN, SHOTGUN, FEET):
            _TEXTURES.setdefault(face, symbol_texture(face))
        _MESHES[color] = make_box(1.0, [_TEXTURES[f] for f in FACES[color]])
    return _MESHES[color]


class DiceTray:
    """The 3D area where the current roll tumbles in and lands."""

    SPACING = 2.0
    CAMERA_DIR = normalize([0.0, 0.85, 0.55])

    def __init__(self, rng=None):
        self.rng = rng or np.random.default_rng()
        self.renderer = Renderer(1, 1)
        self.camera = Camera(target=np.array([0.0, 0.3, 0.0]), fov=35.0)
        self.light = Light()
        self.clear()

    def clear(self):
        self.dice, self.anims, self.faces, self.t = [], [], [], 0.0

    def roll(self, dice):
        """Animate a roll; dice is a list of (color, face)."""
        self.clear()
        n = len(dice)
        for i, (color, face) in enumerate(dice):
            rest = np.array([(i - (n - 1) / 2) * self.SPACING, 0.5, 0.0])
            options = [k for k, f in enumerate(FACES[color]) if f == face]
            anim = RollAnimation(int(self.rng.choice(options)), rest, self.rng, drop_height=4.0, scatter=0.8)
            obj = Object3D(zombie_die_mesh(color), color=DIE_COLOR[color])
            obj.position, obj.rotation = anim.pose(0.0)
            self.dice.append(obj)
            self.anims.append(anim)
            self.faces.append(face)

    @property
    def animating(self):
        return any(not a.done(self.t) for a in self.anims)

    def update(self, dt):
        self.t += dt
        for obj, anim in zip(self.dice, self.anims):
            obj.position, obj.rotation = anim.pose(self.t)

    def render(self, screen, top, left, width, height):
        if width < 4 or height < 3:
            return
        self.renderer.resize(width, height)
        tan_half = np.tan(np.radians(self.camera.fov) / 2)
        aspect = width * self.renderer.cell_aspect / height
        dist = max(1.6 / tan_half, 3.5 / (tan_half * aspect))
        self.camera.position = self.camera.target + self.CAMERA_DIR * dist
        fb = self.renderer.render(self.dice, self.camera, self.light)
        screen.draw_frame(fb, top, left)
        if self.animating:
            return
        for obj, anim, face in zip(self.dice, self.anims, self.faces):
            p = self.renderer.project(anim.rest + [0.0, -0.5, 0.75])
            if p is None:
                continue
            label = FACE_LABEL[face]
            y = min(int(p[1]) + 1, height - 1)
            screen.text(top + y, left + int(p[0]) - len(label) // 2, label, obj.color, bold=True)


# ----- kept-dice tokens: a brain, a pair of shoes, a big X ---------------------------

def merge_meshes(meshes):
    verts, faces, base = [], [], 0
    for m in meshes:
        verts.append(m.vertices)
        faces.append(m.faces + base)
        base += len(m.vertices)
    return Mesh(np.concatenate(verts), np.concatenate(faces))


def block_mesh(center, size, rotation=None):
    """Box with per-axis `size`, optionally rotated (3x3 matrix) about its centre."""
    verts = make_box(1.0).vertices * size
    if rotation is not None:
        verts = verts @ np.asarray(rotation).T
    return Mesh(verts + center, make_box(1.0).faces)


def blob_mesh(radii, center=(0.0, 0.0, 0.0), rings=8, segments=12, bump=None):
    """UV ellipsoid; bump(unit_directions) -> per-vertex radius multipliers."""
    lat = np.linspace(0, np.pi, rings + 1)[1:-1]
    lon = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    la, lo = np.meshgrid(lat, lon, indexing="ij")
    dirs = np.c_[(np.sin(la) * np.cos(lo)).ravel(), np.cos(la).ravel(), (np.sin(la) * np.sin(lo)).ravel()]
    dirs = np.r_[[(0.0, 1.0, 0.0)], dirs, [(0.0, -1.0, 0.0)]]
    r = bump(dirs)[:, None] if bump else 1.0
    verts = dirs * r * radii + center
    ring = lambda i: 1 + i * segments  # first vertex of ring i
    faces = []
    for j in range(segments):
        k = (j + 1) % segments
        faces.append((0, ring(0) + k, ring(0) + j))
        last = ring(rings - 2)
        faces.append((len(verts) - 1, last + j, last + k))
        for i in range(rings - 2):
            a, b, c, d = ring(i) + j, ring(i) + k, ring(i + 1) + j, ring(i + 1) + k
            faces += [(a, b, d), (a, d, c)]
    return Mesh(verts, np.array(faces, dtype=int))


def brain_mesh():
    """Two wrinkled hemispheres with a cerebellum tucked under the back."""
    def folds(d):
        x, y, z = d.T
        wrinkles = 0.07 * np.sin(9 * z + 4 * np.sin(6 * y)) * np.sin(8 * y + 3 * np.cos(7 * z))
        return 1 + wrinkles - 0.1 * (y < -0.4) * (y + 0.4) ** 2  # flatter underneath
    halves = [blob_mesh((0.36, 0.5, 0.72), (side * 0.2, 0.08, 0.0), rings=10, segments=16, bump=folds)
              for side in (-1, 1)]
    cerebellum = blob_mesh((0.4, 0.18, 0.22), (0.0, -0.33, -0.42), rings=6, segments=10)
    stem = blob_mesh((0.1, 0.22, 0.1), (0.0, -0.45, -0.18), rings=4, segments=6)
    return merge_meshes(halves + [cerebellum, stem])


def shoes_mesh():
    """A pair of high-top sneakers side by side, toes pointing forward (+Z)."""
    parts = []
    for side, stagger in ((-1, 0.18), (1, -0.18)):
        x = side * 0.2
        parts += [
            block_mesh((x, -0.42, stagger), (0.3, 0.1, 1.0)),                # sole
            blob_mesh((0.14, 0.14, 0.32), (x, -0.33, stagger + 0.16)),       # rounded toe box
            block_mesh((x, -0.08, stagger - 0.26), (0.28, 0.62, 0.42)),      # ankle
            block_mesh((x, 0.25, stagger - 0.26), (0.32, 0.08, 0.46)),       # padded collar
        ]
    return merge_meshes(parts)


def cross_mesh():
    """A thick X, lying in the XY plane."""
    return merge_meshes([block_mesh((0.0, 0.0, 0.0), (0.26, 1.3, 0.26), quat_to_matrix(quat_axis_angle((0, 0, 1), a)))
                         for a in (np.pi / 4, -np.pi / 4)])


TOKEN_MESHES = {BRAIN: brain_mesh, FEET: shoes_mesh, SHOTGUN: cross_mesh}
_TOKENS = {}


def token_mesh(face):
    """The token for a face, centred and scaled to fit a unit sphere so it fills its cell at any angle."""
    if face not in _TOKENS:
        mesh = TOKEN_MESHES[face]()
        lo, hi = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
        verts = mesh.vertices - (lo + hi) / 2
        mesh.vertices = verts / np.linalg.norm(verts, axis=1).max()
        _TOKENS[face] = mesh
    return _TOKENS[face]


class KeptDice:
    """This turn's dice, each shown as a spinning token for what it rolled: brain, shoes or X."""

    CELL_W, CELL_H = 12, 7
    LABEL = {BRAIN: "Brain", SHOTGUN: "Shotgun", FEET: "Ran"}
    SPIN = 0.9    # radians per second
    STEPS = 72    # cached frames per turn of the spin
    TILT = {BRAIN: 0.3, FEET: 0.45, SHOTGUN: 0.0}  # lean the top toward the camera

    def __init__(self):
        self.renderer = Renderer(1, 1)
        self.camera = Camera(position=np.array([0.0, 0.0, 6.0]), fov=24.0)
        self.light = Light(direction=np.array([0.3, -0.5, -1.0]), ambient=0.25, diffuse=0.75)
        self.token = Object3D(None)
        self.t = 0.0
        self._frames = {}  # (face, color, width, height, step) -> FrameBuffer

    def update(self, dt):
        self.t += dt

    def capacity(self, width, height):
        return max(width // self.CELL_W, 1) * max(height // self.CELL_H, 0)

    def angle(self, face, t):
        """Yaw at time t. The X rocks so it never turns edge-on; the shoes rock around a side view."""
        if face == SHOTGUN:
            return 0.6 * np.sin(t * self.SPIN * 1.5)
        if face == FEET:
            return np.pi / 2 - 0.6 + 0.5 * np.sin(t * self.SPIN * 1.5)
        return t * self.SPIN

    def frame(self, face, color, width, height, t):
        """Rendered token at time t, cached by spin step since the models are costly to rasterize."""
        step = int(round(self.angle(face, t) / (2 * np.pi) * self.STEPS)) % self.STEPS
        key = (face, color, width, height, step)
        if key not in self._frames:
            yaw = 2 * np.pi * step / self.STEPS
            self.token.mesh = token_mesh(face)
            self.token.color = DIE_COLOR[color]
            self.token.rotation = quat_mul(quat_axis_angle((1.0, 0.0, 0.0), self.TILT[face]), quat_axis_angle(UP, yaw))
            self._frames[key] = self.renderer.render([self.token], self.camera, self.light).copy()
        return self._frames[key]

    def render(self, screen, top, left, width, height, dice):
        """Draw (color, face) dice into the area; returns how many fit."""
        cols = max(width // self.CELL_W, 1)
        cell_w = width // cols
        shown = dice[:self.capacity(width, height)]
        token_h = self.CELL_H - 1  # the last row of each cell is the label
        if (cell_w, token_h) != (self.renderer.width, self.renderer.height):
            self.renderer.resize(cell_w, token_h)
            self._frames.clear()
            # Fit a spinning token (about 1.9 units across) into the cell.
            tan_half = np.tan(np.radians(self.camera.fov) / 2)
            aspect = cell_w * self.renderer.cell_aspect / token_h
            self.camera.position = np.array([0.0, 0.0, max(0.95 / tan_half, 0.95 / (tan_half * aspect))])
        for i, (color, face) in enumerate(shown):
            row, col = divmod(i, cols)
            y, x = top + row * self.CELL_H, left + col * cell_w
            screen.draw_frame(self.frame(face, color, cell_w, token_h, self.t + i * 1.3 / self.SPIN), y, x)
            label = self.LABEL[face]
            screen.text(y + token_h, x + (cell_w - len(label)) // 2, label, DIE_COLOR[color], bold=True)
        return len(shown)
