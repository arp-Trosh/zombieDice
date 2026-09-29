"""3D pieces of the game: the title logo, zombie dice, the dice tray and the Dice Kept tokens.

Everything here is decoration: whatever the 3D shows (rolls, the cup, busts, the winner) is also
written out as text by the UI, so the game plays the same with the graphics at their plainest.
"""
import weakref

import numpy as np

from unicode3d.examples.dice import RollAnimation, face_texture, orientation_showing
from unicode3d.background import Sky
from unicode3d.mesh import BOX_FACES, Mesh, make_box
from unicode3d.shapes import blob_mesh, block_mesh, merge_meshes, pillow_mesh, text_bitmap, bitmap_mesh
from unicode3d.scene import Camera, Light, Node, Object3D, PointLight, Renderer
from unicode3d.color import Color
from unicode3d.transforms import UP, look_at, normalize, perspective, quat_axis_angle, quat_mul, quat_to_matrix

from .rules import BRAIN, FACES, FEET, GREEN, RED, SHOTGUN, YELLOW

DIE_COLOR = {GREEN: Color.GREEN, YELLOW: Color.YELLOW, RED: Color.RED}
FACE_LABEL = {BRAIN: "BRAIN", SHOTGUN: "BLAM!", FEET: "RAN"}
FACE_NAME = {BRAIN: "brain", SHOTGUN: "shotgun", FEET: "footsteps"}
WHITE = (255, 255, 255)  # object colour that shows a mesh's own vertex colours or texture as they are


# ----- graphics settings shared by every renderer ------------------------------------

class GraphicsSettings:
    """Shadows and reflections for all of the game's renderers at once.

    It looks like a Renderer to unicode3d's DisplayControls (which switches `shadows` and
    `reflections`), so F5 and F6 in the status line change every 3D view in the game.
    """

    def __init__(self):
        self._renderers = weakref.WeakSet()
        self._shadows = True
        self._reflections = True

    def track(self, renderer):
        """Put a renderer under these settings; returns it."""
        renderer.shadows, renderer.reflections = self._shadows, self._reflections
        self._renderers.add(renderer)
        return renderer

    @property
    def shadows(self):
        return self._shadows

    @shadows.setter
    def shadows(self, value):
        self._shadows = bool(value)
        for r in list(self._renderers):
            r.shadows = self._shadows

    @property
    def reflections(self):
        return self._reflections

    @reflections.setter
    def reflections(self, value):
        self._reflections = bool(value)
        for r in list(self._renderers):
            r.reflections = self._reflections


GRAPHICS = GraphicsSettings()


# ----- mesh and camera helpers --------------------------------------------------------

def lathe_mesh(profile, segments=24, cap_bottom=True, cap_top=False):
    """A surface of revolution about the Y axis: profile is [(radius, y), ...] from bottom to top.

    The outside is the side to the right of the profile walking up it, so a profile that
    goes up the outside of a bowl and back down its inside makes a bowl with a hollow.
    """
    profile = np.asarray(profile, float)
    n = len(profile)
    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    r, y = profile[:, 0:1], profile[:, 1:2]
    verts = np.stack([r * np.cos(theta), np.broadcast_to(y, (n, segments)), r * np.sin(theta)], axis=2).reshape(-1, 3)
    faces = []
    for i in range(n - 1):
        for j in range(segments):
            k = (j + 1) % segments
            a, b, c, d = i * segments + j, i * segments + k, (i + 1) * segments + k, (i + 1) * segments + j
            faces += [(a, c, b), (a, d, c)]
    verts = list(verts)
    if cap_bottom and profile[0, 0] > 0:
        centre = len(verts)
        verts.append((0.0, profile[0, 1], 0.0))
        faces += [(centre, j, (j + 1) % segments) for j in range(segments)]
    if cap_top and profile[-1, 0] > 0:
        centre, base = len(verts), (n - 1) * segments
        verts.append((0.0, profile[-1, 1], 0.0))
        faces += [(centre, base + (j + 1) % segments, base + j) for j in range(segments)]
    return Mesh(np.array(verts, float), np.array(faces, int))


def flat_mesh(x0, x1, z0, z1, y=0.0, texture=None):
    """A flat rectangle facing up, textured edge to edge if given a texture."""
    mesh = Mesh(np.array([(x0, y, z0), (x0, y, z1), (x1, y, z1), (x1, y, z0)], float), np.array([(0, 1, 2), (0, 2, 3)]))
    if texture is not None:
        uv = np.array([(0, 1), (0, 0), (1, 0), (1, 1)], float)
        mesh.uvs = uv[mesh.faces]
        mesh.materials = np.zeros(2, int)
        mesh.textures = [texture]
    return mesh


def disc_mesh(radius, y=0.0, segments=32):
    """A flat disc facing up."""
    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    verts = np.r_[[(0.0, y, 0.0)], np.c_[radius * np.cos(theta), np.full(segments, y), radius * np.sin(theta)]]
    faces = [(0, 1 + (j + 1) % segments, 1 + j) for j in range(segments)]
    return Mesh(verts, np.array(faces, int))


def facing(forward, up=UP):
    """Quaternion turning an object's +Z to `forward`, keeping its +Y as near `up` as it can."""
    z = normalize(forward)
    x = normalize(np.cross(up, z))
    y = np.cross(z, x)
    m = np.c_[x, y, z]
    w = np.sqrt(max(1.0 + m[0, 0] + m[1, 1] + m[2, 2], 1e-12)) / 2
    if w > 1e-3:
        return np.array([w, (m[2, 1] - m[1, 2]) / (4 * w), (m[0, 2] - m[2, 0]) / (4 * w), (m[1, 0] - m[0, 1]) / (4 * w)])
    # Turned half way round: fall back on the largest diagonal element.
    i = int(np.argmax(np.diag(m)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = np.sqrt(max(1.0 + m[i, i] - m[j, j] - m[k, k], 1e-12)) * 2
    q = np.zeros(4)
    q[0] = (m[k, j] - m[j, k]) / s
    q[1 + i] = s / 4
    q[1 + j] = (m[j, i] + m[i, j]) / s
    q[1 + k] = (m[k, i] + m[i, k]) / s
    return q


def fit_distance(camera, direction, points, aspect, x_lim=0.95, y_lo=-0.95, y_hi=0.95):
    """How far back along `direction` from camera.target the camera must be for every point to show
    within the given NDC limits (x within +-x_lim, y between y_lo and y_hi)."""
    points = np.c_[np.asarray(points, float), np.ones(len(points))]
    proj = perspective(np.radians(camera.fov), aspect, 0.1, 1000.0)

    def fits(d):
        clip = points @ (proj @ look_at(camera.target + direction * d, camera.target, camera.up)).T
        if (clip[:, 3] <= 1e-6).any():
            return False
        ndc = clip[:, :2] / clip[:, 3:4]
        return (np.abs(ndc[:, 0]) <= x_lim).all() and (ndc[:, 1] >= y_lo).all() and (ndc[:, 1] <= y_hi).all()

    lo, hi = 0.5, 400.0
    for _ in range(32):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if fits(mid) else (mid, hi)
    return hi


# ----- 3D lettering ----------------------------------------------------------------

# A 5x7 font for text_mesh ("#" is ink): the title, and the words that pop up over the dice.
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "!": ["#", "#", "#", "#", "#", ".", "#"],
    " ": ["..", "..", "..", "..", "..", "..", ".."],
}
FONT_H = 7


def graded_text_mesh(text, top, bottom, drips=0, rng=None, depth=1.6):
    """Extruded text coloured from `top` to `bottom` (per vertex), optionally with `drips` of slime
    running down from the letters' lower edges: (mesh, width, height), centred on the letters."""
    cells = text_bitmap(text, FONT)
    h, w = cells.shape
    if drips:
        rng = rng or np.random.default_rng(13)
        grid = np.zeros((h + drips, w), bool)
        grid[:h] = cells
        for x in np.flatnonzero(cells[-1]):
            if rng.random() < 0.35:
                grid[h:h + int(rng.integers(1, drips + 1)), x] = True
        cells = grid
    mesh = bitmap_mesh(cells, depth)
    # bitmap_mesh centres the whole grid; shift so the letters themselves are centred, drips hanging below.
    mesh.vertices = mesh.vertices + [0.0, -drips / 2, 0.0]
    t = np.clip((FONT_H / 2 - mesh.vertices[:, 1]) / (FONT_H + drips), 0, 1)[:, None]
    mesh.vertex_colors = (np.asarray(top, float) * (1 - t) + np.asarray(bottom, float) * t) / 255.0
    return mesh, w, h


class Logo:
    """ "ZOMBIE / DICE" in chunky 3D, slime dripping off ZOMBIE: flies in with a spin, then wobbles.

    It is a Node with the two words as children, placed each frame in front of whatever camera
    shows it (see place()), so it can float in the sky of a larger scene.
    """

    LINES = (("ZOMBIE", (170, 255, 110), (40, 150, 30), 3, 4.5), ("DICE", (255, 110, 80), (170, 20, 15), 0, -5.0))
    HEIGHT = 20.0  # units from the top of ZOMBIE to the bottom of DICE, with a margin

    def __init__(self):
        self.node = Node()
        self.parts = []
        self.width = 0
        for text, top, bottom, drips, y in self.LINES:
            mesh, w, _ = graded_text_mesh(text, top, bottom, drips)
            self.width = max(self.width, w)
            self.parts.append(Object3D(mesh, np.array([0.0, y, 0.0]), color=WHITE, emissive=0.55, reflectivity=0.2,
                                       cast_shadows=False, parent=self.node))
        self.t = 0.0
        self.wobble = np.array([1.0, 0.0, 0.0, 0.0])
        self.grow = 0.0

    @property
    def objects(self):
        return self.parts

    def update(self, dt):
        self.t += dt
        t = self.t
        intro = min(t / 1.6, 1.0)
        ease = 1 - (1 - intro) ** 3
        self.grow = ease * (1 + 0.15 * np.sin(np.pi * intro))  # overshoot a little
        yaw = 0.3 * np.sin(0.8 * t) + 2 * np.pi * (1 - ease)
        pitch = 0.12 * np.sin(1.1 * t + 0.5)
        roll = 0.05 * np.sin(0.7 * t + 1.0)
        self.wobble = quat_mul(quat_axis_angle(UP, yaw), quat_mul(quat_axis_angle((1, 0, 0), pitch),
                                                                   quat_axis_angle((0, 0, 1), roll)))

    def place(self, camera, aspect, top, bottom, distance=9.0):
        """Float the logo `distance` in front of the camera, filling the band of the view from `top`
        to `bottom` (fractions of its height, 0 at the top)."""
        eye = np.asarray(camera.position, float)
        forward = normalize(np.asarray(camera.target, float) - eye)
        right = normalize(np.cross(forward, camera.up))
        up = np.cross(right, forward)
        tan_half = np.tan(np.radians(camera.fov) / 2)
        centre = 1 - (top + bottom)  # NDC y of the band's middle
        band_h = (bottom - top) * 2 * distance * tan_half
        view_w = 2 * distance * tan_half * aspect
        size = min(0.92 * band_h / self.HEIGHT, 0.9 * view_w / (self.width + 4))
        self.node.position = eye + forward * distance + up * (centre * distance * tan_half)
        self.node.rotation = quat_mul(facing(-forward, up), self.wobble)
        self.node.scale = max(size * self.grow, 1e-4)


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


def wood_texture(res=128, seed=3, base=(0.42, 0.27, 0.16)):
    """Planks of wood: grain running along u, darker seams between the planks."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:res, 0:res] / res
    planks = 5
    plank = np.floor(y * planks)
    shade = 0.85 + 0.3 * rng.random(planks)[plank.astype(int)]
    grain = 0.5 + 0.5 * np.sin((y * 90 + 2.5 * np.sin(x * 9 + plank * 1.7) + plank * 3) * 2)
    tex = np.asarray(base)[None, None, :] * (shade * (0.8 + 0.25 * grain))[..., None]
    seam = (y * planks) % 1 < 0.04
    tex[seam] *= 0.35
    return np.clip(tex, 0, 1)


TRAY_SKY = Sky(zenith=(12, 10, 24), horizon=(46, 40, 52), ground=(20, 14, 12))
CUP_GLASS = (205, 230, 255)
GOLD = (245, 190, 60)
CONFETTI_COLORS = ((230, 60, 60), (70, 200, 80), (250, 210, 50), (80, 140, 250), (220, 90, 220), (60, 210, 220))


class DiceTray:
    """The 3D area where the current roll tumbles in and lands.

    A lacquered tray (the dice reflect in it) on a wooden table, lit by a lamp overhead and a
    candle off to one side, both casting shadows. Left of the tray stands a glass cup holding
    the dice still in the cup this turn; rolled dice pour out of it. A bust flashes the tray red
    and shakes it, banking brains flashes it green, and a game over puts a golden trophy on the
    tray under falling confetti. Clicking a die or the cup describes it (see describe()).
    """

    SPACING = 1.6
    CAMERA_DIR = normalize([0.0, 0.93, 0.37])  # steep, so the faces the dice land on face the camera
    TROPHY_CAMERA_DIR = normalize([0.0, 0.4, 0.9])
    TRAY = (-2.65, 2.65, -0.95, 1.2)  # inner x0, x1, z0, z1 of the tray: just room for three dice
    RIM_H, RIM_W = 0.3, 0.25
    CUP_R, CUP_H = 0.72, 1.7
    CUP_AT = np.array([-2.65 - 0.25 - 0.72 - 0.2, 0.0, -0.1])  # on the table, left of the tray
    MINI = 0.3  # size of the dice in the cup

    def __init__(self, rng=None):
        self.rng = rng or np.random.default_rng()
        self.renderer = GRAPHICS.track(Renderer(1, 1, background=TRAY_SKY, fog=0.2))
        self.camera = Camera(target=np.array([0.0, 0.3, -0.5]), fov=35.0)
        self.lamp = Light(direction=np.array([0.35, -1.0, -0.45]), ambient=0.25, diffuse=0.65, specular=0.3,
                          shadows=True)
        self.candle = PointLight(np.array([-5.6, 2.6, -1.4]), color=(255, 160, 80), diffuse=0.55, specular=0.2,
                                 range=10.0, shadows=True)
        self.flash_light = PointLight(np.array([0.0, 2.6, 1.2]), color=(255, 60, 40), diffuse=0.0, range=9.0)
        x0, x1, z0, z1 = self.TRAY
        w, h = self.RIM_W, self.RIM_H
        self.table = Object3D(flat_mesh(-14, 14, -11, 10, -0.02, wood_texture(256)), color=WHITE)
        self.floor = Object3D(flat_mesh(x0, x1, z0, z1), color=(70, 16, 22), reflectivity=0.3)
        rim = merge_meshes([block_mesh(((x0 + x1) / 2, h / 2 - 0.02, z0 - w / 2), (x1 - x0 + 2 * w, h, w)),
                            block_mesh(((x0 + x1) / 2, h / 2 - 0.02, z1 + w / 2), (x1 - x0 + 2 * w, h, w)),
                            block_mesh((x0 - w / 2, h / 2 - 0.02, (z0 + z1) / 2), (w, h, z1 - z0)),
                            block_mesh((x1 + w / 2, h / 2 - 0.02, (z0 + z1) / 2), (w, h, z1 - z0))])
        self.rim = Object3D(rim, color=(60, 34, 20))
        profile = [(self.CUP_R * 0.92, 0.0), (self.CUP_R, 0.08), (self.CUP_R, self.CUP_H)]
        self.cup = Object3D(lathe_mesh(profile, 28), self.CUP_AT.copy(), color=CUP_GLASS, opacity=0.2)
        self.cup_dice = []
        self.cup_counts = None
        self.trophy = Object3D(trophy_mesh(), np.array([0.0, 0.0, 0.1]), scale=1.4, color=GOLD, reflectivity=0.45,
                               emissive=0.12, visible=False)
        self.confetti = []
        self.popups = []   # [Object3D, age, velocity]
        self.flash = (0.0, 1.0)  # (strength, seconds it lasts)
        self.flash_t = 0.0
        self.shake = 0.0
        self.celebrating = False
        self._framing = {}  # (width, height, top_rows, celebrating) -> (camera target, distance)
        self.clear()

    # ----- what is on the table ---------------------------------------------------------

    def clear(self):
        self.dice, self.anims, self.faces, self.colors, self.t = [], [], [], [], 0.0

    def roll(self, dice):
        """Animate a roll pouring out of the cup; dice is a list of (color, face)."""
        self.clear()
        n = len(dice)
        for i, (color, face) in enumerate(dice):
            rest = np.array([(i - (n - 1) / 2) * self.SPACING, 0.5, 0.1])
            options = [k for k, f in enumerate(FACES[color]) if f == face]
            face_index = int(self.rng.choice(options))
            anim = RollAnimation(face_index, rest, self.rng, drop_height=1.8, scatter=0.7)  # out over the cup's rim
            # Land square to the camera with the symbol upright (give or take a little), so it reads clearly.
            anim.final_rotation = orientation_showing(face_index, upright_yaw(face_index) + self.rng.uniform(-0.25, 0.25))
            anim.start = self.CUP_AT + [0.5, 0.0, self.rng.uniform(-0.3, 0.3)]  # out over the rim nearest the tray
            obj = Object3D(zombie_die_mesh(color), color=DIE_COLOR[color])
            obj.position, obj.rotation = anim.pose(0.0)
            self.dice.append(obj)
            self.anims.append(anim)
            self.faces.append(face)
            self.colors.append(color)

    def set_cup(self, counts):
        """Show {color: n} dice standing in the cup (None for an empty, idle cup)."""
        key = None if counts is None else tuple(int(counts.get(c, 0)) for c in (GREEN, YELLOW, RED))
        if key == self.cup_counts:
            return
        self.cup_counts = key
        self.cup_dice = []
        if key is None:
            return
        colors = [c for c, k in zip((GREEN, YELLOW, RED), key) for _ in range(k)]
        rng = np.random.default_rng(hash(key) & 0xFFFF)  # the same jumble for the same counts
        rng.shuffle(colors)
        m = self.MINI
        for i, color in enumerate(colors):
            layer, slot = divmod(i, 4)
            a = slot * np.pi / 2 + layer * 0.8
            offset = np.array([np.cos(a) * 0.3, m / 2 + 0.1 + layer * m * 1.05, np.sin(a) * 0.3])
            tilt = quat_mul(quat_axis_angle(UP, rng.uniform(0, 2 * np.pi)),
                            quat_axis_angle(normalize(rng.normal(size=3)), rng.uniform(0, 0.35)))
            self.cup_dice.append(Object3D(zombie_die_mesh(color), self.CUP_AT + offset, tilt, scale=m,
                                          color=DIE_COLOR[color]))

    def bust(self):
        """Flash the tray red and shake it, and pop up BLAM!"""
        self._flash((255, 40, 30), 1.4, 0.9)
        self.shake = 0.6
        self._popup("BLAM!", (255, 70, 50))

    def bank(self):
        """Flash the tray green and pop up BRAINS!"""
        self._flash((90, 255, 110), 0.9, 0.8)
        self._popup("BRAINS!", (240, 150, 170))

    def celebrate(self, on):
        """The game over trophy and confetti, or back to dice."""
        if on == self.celebrating:
            return
        self.celebrating = on
        self.trophy.visible = on
        self.confetti = []
        if on:
            self.clear()
            self.popups = []
            self.set_cup(None)
            square = flat_mesh(-0.5, 0.5, -0.5, 0.5)
            for i in range(70):
                obj = Object3D(square, np.array([self.rng.uniform(-4, 4), self.rng.uniform(1, 9), self.rng.uniform(-2, 1.5)]),
                               scale=0.18, color=CONFETTI_COLORS[i % len(CONFETTI_COLORS)], double_sided=True,
                               emissive=0.25)
                self.confetti.append((obj, normalize(self.rng.normal(size=3)), self.rng.uniform(2, 6)))

    def _flash(self, color, strength, seconds):
        self.flash_light.color = color
        self.flash, self.flash_t = (strength, seconds), 0.0

    def _popup(self, word, color):
        mesh, w, _ = graded_text_mesh(word, color, np.asarray(color) * 0.45)
        obj = Object3D(mesh, np.array([0.0, 1.4, -0.4]), scale=0.01, color=WHITE, emissive=0.5, cast_shadows=False)
        self.popups = [[obj, 0.0, 4.6 / max(w, 1)]]  # target scale: about 4.6 units across

    # ----- animation --------------------------------------------------------------------

    @property
    def animating(self):
        return any(not a.done(self.t) for a in self.anims)

    def update(self, dt):
        self.t += dt
        for obj, anim, face in zip(self.dice, self.anims, self.faces):
            obj.position, obj.rotation = anim.pose(self.t)
            since = self.t - anim.duration
            # A shotgun die flares up as it lands: the humans fire back.
            obj.emissive = 0.9 * np.exp(-since * 4) if face == SHOTGUN and since >= 0 else 0.0
        if self.anims and any(f == SHOTGUN for f in self.faces):
            landed = [self.t - a.duration for a, f in zip(self.anims, self.faces) if f == SHOTGUN]
            recent = [s for s in landed if 0 <= s < 0.08]
            if recent and self.flash_t >= self.flash[1] * 0.5:
                self._flash((255, 230, 150), 0.8, 0.3)  # a muzzle flash
        self.flash_t += dt
        self.shake = max(self.shake - dt, 0.0)
        for pop in self.popups:
            pop[1] += dt
        self.popups = [p for p in self.popups if p[1] < 1.6]
        for p in self.popups:
            obj, age, size = p
            grow = min(age / 0.25, 1.0)
            obj.scale = size * (grow + 0.12 * np.sin(grow * np.pi))
            obj.position = np.array([0.0, 1.4 + age * 0.6, -0.4])  # over the tray, rising
            # Facing the camera, which looks steeply down.
            obj.rotation = quat_axis_angle((1, 0, 0), -np.arctan2(self.CAMERA_DIR[1], self.CAMERA_DIR[2]))
            obj.opacity = float(np.clip((1.6 - age) / 0.5, 0, 1))
        if self.celebrating:
            self.trophy.rotation = quat_axis_angle(UP, self.t * 0.8)
            for obj, axis, speed in self.confetti:
                obj.position = obj.position + [np.sin(self.t * 2 + speed) * dt * 0.6, -speed * dt * 0.5, 0.0]
                if obj.position[1] < 0.02:
                    obj.position = obj.position + [0.0, 9.0, 0.0]
                obj.rotation = quat_axis_angle(axis, self.t * speed)

    def lights(self):
        lights = [self.lamp, self.candle]
        strength, seconds = self.flash
        k = max(1.0 - self.flash_t / seconds, 0.0)
        if k > 0:
            self.flash_light.diffuse = strength * k * k
            self.flash_light.ambient = 0.35 * strength * k * k
            lights.append(self.flash_light)
        # The candle flickers.
        self.candle.diffuse = 0.5 + 0.06 * np.sin(self.t * 13.0) + 0.04 * np.sin(self.t * 31.0 + 1.0)
        return lights

    # ----- drawing ----------------------------------------------------------------------

    def objects(self):
        objs = [self.table, self.floor, self.rim]
        if not self.celebrating:
            objs += [self.cup, *self.cup_dice, *self.dice]
        else:
            objs += [self.trophy, *(o for o, _, _ in self.confetti)]
        return objs + [p[0] for p in self.popups]

    def render(self, screen, top, left, width, height, top_rows=1):
        """Draw the tray into the area; the scene is framed below its first `top_rows` rows (the banner)."""
        if width < 4 or height < 3:
            return
        self.top, self.left = top, left
        self.renderer.resize(width, height, screen.cell_pixels)
        key = (width, height, tuple(screen.cell_pixels), top_rows, self.celebrating)
        if key not in self._framing:
            self._framing[key] = self._frame(width, height, top_rows)
        target, dist = self._framing[key]
        direction = self.TROPHY_CAMERA_DIR if self.celebrating else self.CAMERA_DIR
        self.camera.target = target.copy()
        if self.shake > 0:
            self.camera.target = self.camera.target + self.rng.normal(scale=0.12 * self.shake, size=3)
        self.camera.position = self.camera.target + direction * dist
        fb = self.renderer.render(self.objects(), self.camera, self.lights())
        screen.draw_frame(fb, top, left)
        if self.animating or self.celebrating:
            return
        # The roll in words, under each die.
        for anim, face, color in zip(self.anims, self.faces, self.colors):
            p = self.renderer.project(anim.rest + [0.0, -0.5, 0.75])
            if p is None:
                continue
            label = FACE_LABEL[face]
            y = min(int(p[1]) + 1, height - 1)
            screen.text(top + y, left + int(p[0]) - len(label) // 2, label, DIE_COLOR[color], bold=True)

    def _frame(self, width, height, top_rows):
        """Where to aim the camera and how far back to put it so the tray fills as much of the area as it can:
        (target, distance). The tray (with its rim) stays below the first `top_rows` rows and clear of the
        edges; the cup behind it may reach up under the banner."""
        aspect = width * self.renderer.cell_aspect / height
        x0, x1, z0, z1 = self.TRAY
        w, c = self.RIM_W, self.CUP_AT
        y_hi = 1 - 2 * (top_rows + 0.2) / height
        y_lo = -1 + 2 * 0.2 / height
        if self.celebrating:  # close in on the trophy
            groups = [([(x, y, z) for x in (-2.0, 2.0) for y in (0.0, 3.0) for z in (-1.0, 1.0)], 0.985, y_hi)]
            direction, centres = self.TROPHY_CAMERA_DIR, [(0.0, 1.2, 0.0)]
        else:
            # The tray fills the area right of the cup, which stands at the left edge; the cup's top may
            # reach up under the banner.
            tray = [(x, h, z) for x in (x0 - w, x1 + w) for z in (z0 - w, z1 + w) for h in (0.0, self.RIM_H)]
            cup = [(c[0] + dx, y, c[2] + dz) for dx in (-self.CUP_R, self.CUP_R) for dz in (-self.CUP_R, self.CUP_R)
                   for y in (0.0, self.CUP_H)]
            groups = [(tray, 0.985, y_hi), (cup, 0.995, 0.98)]
            direction = self.CAMERA_DIR
            centres = [(x, 0.3, z) for x in np.linspace(-1.6, 0.4, 11) for z in np.linspace(-0.8, 0.6, 8)]
        fits = []
        for centre in centres:
            self.camera.target = np.array(centre)
            fits.append((max(fit_distance(self.camera, direction, pts, aspect, xl, y_lo, hi) for pts, xl, hi in groups),
                         np.array(centre)))
        closest = min(d for d, _ in fits)
        # Of the framings about as close as the closest, the one with the tray most nearly centred up and down
        # in the room below the banner.
        proj = perspective(np.radians(self.camera.fov), aspect, 0.1, 1000.0)
        pts = np.c_[np.asarray(groups[0][0], float), np.ones(len(groups[0][0]))]

        def off_centre(dist, centre):
            clip = pts @ (proj @ look_at(centre + direction * dist, centre, self.camera.up)).T
            ys = clip[:, 1] / clip[:, 3]
            return abs((ys.min() + ys.max()) / 2 - (y_lo + y_hi) / 2)

        dist, centre = min((f for f in fits if f[0] <= closest * 1.01), key=lambda f: off_centre(*f))
        return centre, dist

    def describe(self, y, x):
        """What is at screen cell (y, x) of the tray as last drawn, in words: ("die", text), ("cup", text) or None."""
        hit = self.renderer.pick(x - getattr(self, "left", 0), y - getattr(self, "top", 0))
        if hit is None:
            return None
        obj = hit.object
        i = next((i for i, d in enumerate(self.dice) if d is obj), None)
        if i is not None:
            color, face = self.colors[i], self.faces[i]
            counts = {f: FACES[color].count(f) for f in (BRAIN, FEET, SHOTGUN)}
            return "die", (f"{color.capitalize()} die: {FACE_NAME[face]}. {color.capitalize()} dice have "
                           f"{counts[BRAIN]} brains, {counts[FEET]} footsteps, {counts[SHOTGUN]} shotguns.")
        if obj is self.cup or any(d is obj for d in self.cup_dice):
            g, yl, r = self.cup_counts or (0, 0, 0)
            return "cup", f"The cup holds {g} green, {yl} yellow and {r} red dice."
        if obj is self.trophy:
            return "trophy", "The winner's trophy."
        return None


def upright_yaw(face):
    """The turn about the vertical that, with box face `face` on top, points the top of its picture away
    from a camera looking along -Z (so it shows the right way up)."""
    up = quat_to_matrix(orientation_showing(face, 0.0)) @ np.array(BOX_FACES[face][2], float)
    return np.pi - np.arctan2(up[0], up[2])


def trophy_mesh():
    """A cup-shaped trophy on a stepped base, turned on a lathe: the bowl is hollow."""
    profile = [(0.75, 0.0), (0.75, 0.22), (0.55, 0.26), (0.55, 0.4), (0.18, 0.46), (0.12, 0.7), (0.1, 1.0),
               (0.3, 1.1), (0.62, 1.35), (0.78, 1.75), (0.82, 2.05), (0.74, 2.05), (0.66, 1.75), (0.5, 1.4),
               (0.0, 1.25)]
    body = lathe_mesh(profile, 32)
    handles = [blob_mesh((0.1, 0.34, 0.08), (s * 0.86, 1.62, 0.0), rings=8, segments=10) for s in (-1, 1)]
    return merge_meshes([body, *handles])


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

    def columns(self, width):
        """Tokens side by side in an area `width` cells wide."""
        return max(width // self.CELL_W, 1)

    def capacity(self, width, height):
        return self.columns(width) * max(height // self.CELL_H, 0)

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

    def render(self, screen, top, left, width, height, dice, start=0):
        """Draw (color, face) dice into the area, from dice[start] on (scrolled); returns how many fit."""
        cols = self.columns(width)
        cell_w = width // cols
        shown = dice[start:start + self.capacity(width, height)]
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
            # Each token keeps its own rocking phase however far the panel is scrolled.
            screen.draw_frame(self.frame(face, color, cell_w, token_h, self.t + (start + i) * 1.3 / self.SPIN), y, x)
            label = self.LABEL[face]
            screen.text(y + token_h, x + (cell_w - len(label)) // 2, label, DIE_COLOR[color], bold=True)
        return len(shown)
