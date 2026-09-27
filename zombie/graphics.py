"""3D pieces of the game: the title logo, zombie dice and the dice tray."""
import numpy as np

from unicode3d.examples.dice import RollAnimation, face_texture
from unicode3d.mesh import make_box
from unicode3d.shapes import blob_mesh, block_mesh, merge_meshes, pillow_mesh, text_mesh
from unicode3d.scene import Camera, Light, Object3D, Renderer
from unicode3d.color import Color
from unicode3d.transforms import UP, normalize, quat_axis_angle, quat_mul, quat_to_matrix

from .rules import BRAIN, FACES, FEET, GREEN, RED, SHOTGUN, YELLOW

DIE_COLOR = {GREEN: Color.GREEN, YELLOW: Color.YELLOW, RED: Color.RED}
FACE_LABEL = {BRAIN: "BRAIN", SHOTGUN: "BLAM!", FEET: "RAN"}

# ----- 3D title --------------------------------------------------------------------

# The letters the title needs, for text_mesh: 7 rows each, "#" is ink.
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


class TitleLogo:
    """ "ZOMBIE / DICE" in chunky 3D, flying in with a spin and then wobbling gently."""

    LINES = (("ZOMBIE", Color.GREEN, 4.5), ("DICE", Color.RED, -4.5))

    def __init__(self):
        self.renderer = Renderer(1, 1)
        self.camera = Camera(target=np.zeros(3), fov=26.0, far=500.0)
        # A faint highlight: the big flat letter fronts would otherwise wash out to white.
        self.light = Light(direction=np.array([0.3, -0.6, -1.0]), ambient=0.15, diffuse=0.85, specular=0.08)
        self.parts = []
        self.width = 0
        for text, color, y in self.LINES:
            mesh, w = text_mesh(text, FONT)
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
        self.renderer.resize(width, height, screen.cell_pixels)
        tan_half = np.tan(np.radians(self.camera.fov) / 2)
        aspect = width * self.renderer.cell_aspect / height
        dist = max(11.0 / tan_half, (self.width / 2 + 4.0) / (tan_half * aspect))
        self.camera.position = np.array([0.0, 0.0, dist])
        fb = self.renderer.render([obj for obj, _ in self.parts], self.camera, self.light)
        screen.draw_frame(fb, top, left)


# ----- 2D symbol shapes, shared by the die faces and the Dice Kept tokens -------------

# Footprint in the GNOME-logo style, x right and y up in about -1..1: heel, ball, then the four
# toes from big to little. The whole print leans by FOOT_LEAN radians (negative: toes to the right).
FOOT_PARTS = ((-0.06, -0.55, 0.3, 0.28), (0.04, -0.08, 0.42, 0.38),
              (-0.3, 0.62, 0.18, 0.2), (0.14, 0.72, 0.14, 0.15), (0.5, 0.58, 0.12, 0.12), (0.76, 0.3, 0.1, 0.1))
FOOT_LEAN = -0.3

# Brain seen from its left side, front to the right: (cx, cy, rx, ry) ellipses.
CEREBRUM = (0.05, 0.12, 0.85, 0.6)
TEMPORAL_LOBE = (0.22, -0.22, 0.5, 0.3)
CEREBELLUM = (-0.52, -0.43, 0.3, 0.2)
# The folds, drawn the way a cartoon brain is: polylines for the lateral fissure, the central
# sulcus running down to it, and a curl in each lobe.
BRAIN_FOLDS = (
    ((0.74, -0.04), (0.4, 0.02), (0.05, -0.02), (-0.28, 0.1)),               # lateral fissure
    ((0.02, 0.72), (0.14, 0.52), (0.0, 0.34), (0.12, 0.16), (0.04, 0.0)),     # central sulcus
    ((0.8, 0.42), (0.58, 0.54), (0.42, 0.34), (0.62, 0.2)),                 # frontal lobe
    ((-0.3, 0.66), (-0.2, 0.44), (-0.44, 0.3), (-0.64, 0.4)),               # parietal lobe
    ((0.6, -0.26), (0.34, -0.2), (0.12, -0.3)),                             # temporal lobe
    ((-0.6, 0.12), (-0.42, -0.06)),                                         # occipital lobe
)


def _ellipse(x, y, part):
    cx, cy, rx, ry = part
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1


def _rotate(x, y, angle):
    c, s = np.cos(angle), np.sin(angle)
    return c * x - s * y, s * x + c * y


def _near_polyline(x, y, points, width):
    """True within `width` of the polyline through `points`."""
    near = np.zeros(np.broadcast(x, y).shape, bool)
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        t = np.clip(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
        near |= np.hypot(x - ax - t * dx, y - ay - t * dy) < width
    return near


def foot_shape(x, y):
    """True inside the footprint."""
    fx, fy = _rotate(x, y, -FOOT_LEAN)
    inside = np.zeros(np.broadcast(x, y).shape, bool)
    for part in FOOT_PARTS:
        inside |= _ellipse(fx, fy, part)
    return inside


def brain_shape(x, y, bold=1.0):
    """Side view of a brain, front to the right: (inside, grooves) masks.

    The cerebrum gets a handful of bold fold strokes and the cerebellum fine stripes:
    about as much as survives at a dozen pixels across. bold > 1 thickens the strokes.
    """
    cx, cy, rx, ry = CEREBRUM
    r = np.hypot((x - cx) / rx, (y - cy) / ry)
    theta = np.arctan2((y - cy) / ry, (x - cx) / rx)
    lumpy = r < 1 + 0.05 * np.sin(11 * theta) * (y > cy - 0.2)     # bumps along the top of the outline
    cerebrum = lumpy | _ellipse(x, y, TEMPORAL_LOBE)
    cerebellum = _ellipse(x, y, CEREBELLUM) & ~cerebrum
    folds = np.zeros_like(cerebrum)
    for stroke in BRAIN_FOLDS:
        folds |= _near_polyline(x, y, stroke, 0.05 * bold)
    folds &= cerebrum
    stripes = cerebellum & (np.abs((y * 9) % 1 - 0.5) < 0.18)
    return cerebrum | cerebellum, folds | stripes


# ----- zombie dice -----------------------------------------------------------------

def symbol_texture(face, res=48, ink=0.05):
    """A die face: dark ink on the light face, drawn from the same shapes as the Dice Kept tokens."""
    tex, u, v = face_texture(res)
    if face == BRAIN:
        inside, grooves = brain_shape((u - 0.5) * 2.3, (v - 0.46) * 2.3, bold=1.6)
        tex[inside] = ink
        tex[inside & grooves] = 0.5
    elif face == SHOTGUN:
        inside = (np.minimum(u, v) > 0.18) & (np.maximum(u, v) < 0.82)
        tex[inside & ((np.abs(u - v) < 0.1) | (np.abs(u + v - 1) < 0.1))] = ink
    elif face == FEET:
        tex[foot_shape((u - 0.58) * 2.4, (v - 0.5) * 2.4)] = ink
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
        self.renderer.resize(width, height, screen.cell_pixels)
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


# ----- kept-dice tokens: a brain, a footprint, a big X ---------------------------

def brain_mesh(bold=1.2):
    """The side-view brain as a puffy badge, painted with bold folds.

    A dozen pixels across is too few for sculpted folds, and a round 3D brain reads as a
    blob from most angles; a flat, evenly lit face with dark painted grooves reads like an icon.
    """
    res, span = 64, 1.1
    mesh = pillow_mesh(lambda x, y: brain_shape(x, y)[0], span=span)
    c = ((np.arange(res) + 0.5) / res * 2 - 1) * span
    x, y = np.meshgrid(c, -c)
    inside, grooves = brain_shape(x, y, bold)
    mesh.textures = [np.where(inside & grooves, 0.0, 1.0)]  # grooves as black ink: dim shades of a hue stay too colourful
    return mesh


def foot_mesh():
    """A bare footprint in the GNOME-logo style, facing the camera (+Z): a bean-shaped sole with four toes.

    It is nearly flat and evenly lit like a printed logo, with chunky toes and wide gaps so the toes
    stay separate in a 12x6-cell panel slot, and leans like the logo does.
    """
    parts = [
        blob_mesh((0.3, 0.28, 0.06), (-0.06, -0.55, 0.0), rings=8, segments=16),   # heel
        blob_mesh((0.42, 0.38, 0.07), (0.04, -0.08, 0.0), rings=8, segments=16),   # ball of the foot
    ]
    toes = ((-0.3, 0.62, 0.18, 0.2), (0.14, 0.72, 0.14, 0.15), (0.5, 0.58, 0.12, 0.12), (0.76, 0.3, 0.1, 0.1))
    for x, y, rx, ry in toes:  # big toe down to little toe, curving round the top of the sole
        parts.append(blob_mesh((rx, ry, 0.06), (x, y, 0.0), rings=6, segments=12))
    foot = merge_meshes(parts)
    foot.vertices = foot.vertices @ quat_to_matrix(quat_axis_angle((0, 0, 1), -0.3)).T  # lean the toes right
    return foot


def cross_mesh():
    """A thick X, lying in the XY plane."""
    return merge_meshes([block_mesh((0.0, 0.0, 0.0), (0.26, 1.3, 0.26), quat_to_matrix(quat_axis_angle((0, 0, 1), a)))
                         for a in (np.pi / 4, -np.pi / 4)])


TOKEN_MESHES = {BRAIN: brain_mesh, FEET: foot_mesh, SHOTGUN: cross_mesh}
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
    """This turn's dice, each shown as a rocking token for what it rolled: brain, foot or X."""

    CELL_W, CELL_H = 12, 7
    LABEL = {BRAIN: "Brain", SHOTGUN: "Shotgun", FEET: "Ran"}
    SPIN = 0.9    # radians per second
    STEPS = 72    # cached frames per turn of the spin
    TILT = {BRAIN: 0.0, FEET: 0.0, SHOTGUN: 0.0}  # lean the top toward the camera

    def __init__(self):
        self.renderer = Renderer(1, 1, fog=0.1)  # the tokens are small and mostly flat; fog would only muddy them
        self.camera = Camera(position=np.array([0.0, 0.0, 6.0]), fov=24.0)
        # Soft, mostly-frontal light: at this size, shading gradients would drown out the painted detail.
        self.light = Light(direction=np.array([0.3, -0.5, -1.0]), ambient=0.5, diffuse=0.5, specular=0.1)
        self.token = Object3D(None)
        self.t = 0.0
        self._frames = {}  # (face, color, width, height, step) -> FrameBuffer

    def update(self, dt):
        self.t += dt

    def capacity(self, width, height):
        return max(width // self.CELL_W, 1) * max(height // self.CELL_H, 0)

    def angle(self, face, t):
        """Yaw at time t: the tokens are flat-faced, so they rock rather than spin and never turn edge-on."""
        return 0.6 * np.sin(t * self.SPIN * 1.5)

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
        if (cell_w, token_h, screen.cell_pixels) != (self.renderer.width, self.renderer.height, self.renderer.cell_pixels):
            self.renderer.resize(cell_w, token_h, screen.cell_pixels)
            self._frames.clear()
            # Fit a rocking token (about 1.9 units across) into the cell.
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
