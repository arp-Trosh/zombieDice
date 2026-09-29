"""The living (and undead) scenery: the graveyard behind the menus and the table in the lobby.

In the graveyard, zombies shamble after humans, catch them and eat their brains, and the eaten
rise again as zombies; now and then a hunter walks in and shotguns zombies into flying pieces
(click a zombie to do it yourself). The menus are plain text drawn over it.

People are built as scene graphs (a Node per joint), so a walk is a few joint angles.
"""
import numpy as np

from unicode3d.background import SkyBox
from unicode3d.color import HUE_RGB
from unicode3d.mesh import Mesh
from unicode3d.scene import Camera, Light, Node, Object3D, PointLight, Renderer
from unicode3d.shapes import blob_mesh, block_mesh, merge_meshes, pillow_mesh, text_bitmap
from unicode3d.transforms import UP, normalize, quat_axis_angle, quat_mul

from .graphics import (CUP_GLASS, FONT, GRAPHICS, WHITE, Logo, disc_mesh, facing, fit_distance, graded_text_mesh,
                       lathe_mesh, zombie_die_mesh)
from .rules import GREEN, RED, YELLOW

X_AXIS, Z_AXIS = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
LEG = 0.8     # hip height of a standing figure
GRAVITY = 9.8

ZOMBIE_SKIN = ((110, 160, 90), (90, 140, 100), (135, 150, 80), (100, 170, 125), (120, 135, 110))
ZOMBIE_CLOTHES = ((90, 70, 60), (70, 80, 110), (110, 40, 40), (80, 90, 60), (60, 60, 70), (120, 110, 90))
ZOMBIE_EYES = ((255, 40, 30), (255, 220, 60), (255, 90, 20))
HUMAN_SKIN = ((240, 200, 170), (205, 155, 115), (150, 100, 70), (95, 65, 45))
HUMAN_SHIRTS = ((40, 120, 240), (235, 235, 235), (240, 130, 40), (200, 50, 160), (250, 215, 50), (60, 190, 200))
PANTS = ((45, 60, 120), (70, 55, 40), (40, 40, 45), (90, 90, 95))


# ----- people ----------------------------------------------------------------------

_MESHES = {}


def _mesh(name):
    """The body-part meshes, made once and shared by every figure (the renderer packs shared meshes once)."""
    if not _MESHES:
        _MESHES.update(
            torso=block_mesh((0.0, 0.35, 0.0), (0.5, 0.7, 0.28)),
            head=blob_mesh((0.19, 0.22, 0.2), rings=8, segments=12),
            eye=blob_mesh((0.045, 0.045, 0.03), rings=4, segments=6),
            arm=block_mesh((0.0, -0.28, 0.0), (0.13, 0.6, 0.14)),
            leg=block_mesh((0.0, -0.4, 0.0), (0.17, 0.8, 0.2)),
            gun=merge_meshes([block_mesh((0.0, -0.62, 0.04), (0.07, 0.95, 0.07)),
                              block_mesh((0.0, -0.3, 0.1), (0.09, 0.3, 0.12))]),
            hat=merge_meshes([block_mesh((0.0, 0.2, 0.0), (0.52, 0.04, 0.52)), block_mesh((0.0, 0.3, 0.0), (0.3, 0.18, 0.3))]),
            brain=blob_mesh((0.2, 0.15, 0.26), rings=10, segments=16,
                            bump=lambda d: 1 + 0.09 * np.sin(14 * np.arctan2(d[:, 2], d[:, 0])) * np.sin(10 * d[:, 1] + 1)
                            - 0.25 * np.exp(-(d[:, 0] / 0.12) ** 2) * (d[:, 1] > 0)),
            chunk=blob_mesh((0.09, 0.07, 0.08), rings=4, segments=6),
            flash=blob_mesh((0.22, 0.22, 0.22), rings=6, segments=8),
        )
    return _MESHES[name]


class Figure:
    """A blocky person as a scene graph: root (where they stand and which way they face) > hips >
    torso, head (> eyes), shoulders (> arms) and hip joints (> legs)."""

    def __init__(self, skin, shirt, pants, eyes=(20, 20, 20), glowing_eyes=False, hunter=False, opacity=1.0):
        self.root = Node()
        self.hips = Node(np.array([0.0, LEG, 0.0]), parent=self.root)
        part = lambda mesh, at, color, parent, **kw: Object3D(_mesh(mesh), np.array(at, float), color=color,
                                                              parent=parent, opacity=opacity, **kw)
        self.torso = part("torso", (0, 0, 0), shirt, self.hips)
        self.head = part("head", (0, 0.92, 0), skin, self.hips)
        glow = 1.0 if glowing_eyes else 0.0
        self.eyes = [part("eye", (s * 0.075, 0.03, 0.17), eyes, self.head, emissive=glow, cast_shadows=not glowing_eyes)
                     for s in (-1, 1)]
        self.shoulders = [Node(np.array([s * 0.33, 0.62, 0.0]), parent=self.hips) for s in (-1, 1)]
        self.arms = [part("arm", (0, 0, 0), shirt if hunter else skin, sh) for sh in self.shoulders]
        self.joints = [Node(np.array([s * 0.12, 0.0, 0.0]), parent=self.hips) for s in (-1, 1)]
        self.legs = [part("leg", (0, 0, 0), pants, j) for j in self.joints]
        self.parts = [self.torso, self.head, *self.eyes, *self.arms, *self.legs]
        self.gun = None
        if hunter:
            self.gun = part("gun", (0, 0, 0), (45, 38, 32), self.shoulders[1])
            self.parts += [self.gun, part("hat", (0, 0, 0), (70, 95, 45), self.head)]

    @property
    def objects(self):
        return self.parts

    def place(self, x, z, heading, y=0.0):
        self.root.position = np.array([x, y, z])
        self.root.rotation = quat_axis_angle(UP, heading)

    def pose(self, phase=0.0, stride=0.0, arms="down", lean=0.0, sway=0.0, fall=0.0, hips_y=LEG, crouch=0.0):
        """Joint angles: legs swing by `stride` at walk `phase`; arms "down", "zombie" (reaching forward),
        "run" (pumping), "aim" or "eat"; the body leans forward by `lean`, rolls by `sway`, falls back
        by `fall` (pi/2 is flat on the back) and crouches by `crouch` (0..1)."""
        swing = stride * np.sin(phase)
        legs = (swing - lean - 0.9 * crouch, -swing - lean - 0.9 * crouch)
        for joint, a in zip(self.joints, legs):
            joint.rotation = quat_axis_angle(X_AXIS, a)
        if arms == "zombie":
            reach = (-np.pi / 2 + 0.12 * np.sin(phase * 0.5) - lean, -np.pi / 2 + 0.12 * np.sin(phase * 0.5 + 2) - lean)
        elif arms == "run":
            reach = (-1.1 * swing - lean, 1.1 * swing - lean)
        elif arms == "aim":
            reach = (-1.35, -np.pi / 2)
        elif arms == "eat":
            reach = (-0.9 - 0.3 * np.sin(phase * 3), -0.9 - 0.3 * np.sin(phase * 3 + 1.5))
        else:
            reach = (0.12 * np.sin(phase), -0.12 * np.sin(phase))
        for sh, a in zip(self.shoulders, reach):
            sh.rotation = quat_axis_angle(X_AXIS, a)
        bob = 0.05 * abs(np.sin(phase)) * min(stride * 2, 1.0)
        self.hips.position = np.array([0.0, hips_y - 0.35 * crouch + bob, 0.0])
        self.hips.rotation = quat_mul(quat_axis_angle(X_AXIS, lean + 0.6 * crouch - fall), quat_axis_angle(Z_AXIS, sway))
        self.head.rotation = quat_axis_angle(Z_AXIS, 0.6 * sway)

    def fade(self, opacity):
        for p in self.parts:
            p.opacity = opacity


def zombie_figure(rng):
    pick = lambda options: options[int(rng.integers(len(options)))]
    return Figure(pick(ZOMBIE_SKIN), pick(ZOMBIE_CLOTHES), pick(PANTS), pick(ZOMBIE_EYES), glowing_eyes=True)


def human_figure(rng, hunter=False):
    pick = lambda options: options[int(rng.integers(len(options)))]
    shirt = (255, 120, 20) if hunter else pick(HUMAN_SHIRTS)
    return Figure(pick(HUMAN_SKIN), shirt, pick(PANTS), hunter=hunter)


# ----- the graveyard ------------------------------------------------------------------

FIELD = (-11.0, 11.0, -13.0, 5.0)  # x0, x1, z0, z1: where the people stay


def night_sky(rng, res=384):
    """A sky box: stars overhead, a sickly green glow along the horizon, dark ground."""
    def stars(tex, rows):
        n = res * res // 700
        ys, xs = rng.integers(0, rows, n), rng.integers(0, res, n)
        tex[ys, xs] = rng.uniform(0.3, 1.0, (n, 1)) ** 2 * (1.0, 0.97, 0.88)

    def side():
        v = np.linspace(1.0, 0.0, res)[:, None, None]
        tex = np.broadcast_to((0.02, 0.025, 0.07) + (1 - v) ** 4 * np.array([0.12, 0.3, 0.14]), (res, res, 3)).copy()
        stars(tex, res * 2 // 3)
        return tex

    top = np.ones((res, res, 3)) * (0.02, 0.025, 0.07)
    stars(top, res)
    return SkyBox([side(), side(), top, np.ones((res, res, 3)) * 0.02, side(), side()])


def ground_mesh(rng, x0=-32, x1=32, z0=-45, z1=16, step=1.6):
    """Flat ground, coloured in patches of dark grass, dead grass and dirt (per vertex)."""
    xs, zs = np.arange(x0, x1 + step, step), np.arange(z0, z1 + step, step)
    gx, gz = np.meshgrid(xs, zs)
    verts = np.c_[gx.ravel(), np.zeros(gx.size), gz.ravel()]
    nx = len(xs)
    idx = np.arange(gx.size).reshape(gx.shape)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    faces = np.r_[np.c_[a, c, d], np.c_[a, d, b]]
    mesh = Mesh(verts, faces)
    noise = (np.sin(gx * 0.7 + rng.uniform(0, 6)) + np.sin(gz * 0.9 + gx * 0.3 + rng.uniform(0, 6))
             + rng.uniform(-0.8, 0.8, gx.shape)).ravel()
    grass, dead, dirt = np.array([(38, 62, 32), (78, 76, 42), (66, 48, 32)], float)
    t = np.clip((noise + 1.5) / 3, 0, 1)[:, None]
    mesh.vertex_colors = np.where(t < 0.5, grass * (1 - 2 * t) + dead * 2 * t, dead * (2 - 2 * t) + dirt * (2 * t - 1)) / 255
    return mesh


def puddle_mesh(rng, radius):
    """A flat, irregular puddle."""
    mesh = disc_mesh(radius, 0.015, 20)
    k = 1 + 0.25 * np.sin(np.arange(len(mesh.vertices)) * 2.1 + rng.uniform(0, 6))
    k[0] = 1
    mesh.vertices = mesh.vertices * np.c_[k, np.ones(len(k)), k * 0.6]
    return mesh


def tombstone_mesh():
    """A round-topped headstone with R.I.P. carved in it, standing on y = 0 and facing +Z."""
    shape = lambda x, y: ((np.abs(x) < 0.6) & (y > -1.0) & (y < 0.35)) | (x ** 2 + (y - 0.35) ** 2 < 0.36)
    mesh = pillow_mesh(shape, res=18, span=1.05, thickness=0.14, rim=2)
    res = 64
    tex = np.ones((res, res))
    letters = text_bitmap("RIP", FONT)
    h, w = letters.shape
    cell = 2
    top, left = int(res * 0.28), (res - w * cell) // 2
    tex[top:top + h * cell, left:left + w * cell] = np.where(np.kron(letters, np.ones((cell, cell))), 0.3, 1.0)
    mesh.textures = [tex]
    mesh.vertices = mesh.vertices + [0.0, 1.0, 0.0]
    return mesh


def tree_mesh(rng):
    """A dead tree: a trunk with crooked branches."""
    parts = [block_mesh((0.0, 1.4, 0.0), (0.35, 2.8, 0.35))]

    def branch(base, direction, length, width, depth):
        d = normalize(direction)
        end = base + d * length
        rot = np.c_[normalize(np.cross(d, (0.3, 0.1, 1.0))), d, np.cross(normalize(np.cross(d, (0.3, 0.1, 1.0))), d)]
        parts.append(block_mesh((base + end) / 2, (width, length, width), rot))
        if depth:
            for _ in range(2):
                branch(end, d + rng.normal(scale=0.7, size=3) + (0, 0.3, 0), length * 0.65, width * 0.7, depth - 1)

    for a in rng.uniform(0, 2 * np.pi, 3):
        branch(np.array([0.0, 2.4 + rng.uniform(0, 0.4), 0.0]), (np.cos(a), 0.9, np.sin(a)), 1.4, 0.2, 2)
    return merge_meshes(parts)


def fence_mesh(x0, x1, z):
    """A wrought-iron fence: spiked bars between two rails."""
    parts = [block_mesh(((x0 + x1) / 2, y, z), (x1 - x0, 0.07, 0.07)) for y in (0.35, 1.25)]
    for x in np.arange(x0, x1 + 0.01, 0.55):
        parts.append(block_mesh((x, 0.75, z), (0.06, 1.5, 0.06)))
        parts.append(block_mesh((x, 1.55, z), (0.12, 0.12, 0.06), quat_to_matrix_z(np.pi / 4)))
    return merge_meshes(parts)


def quat_to_matrix_z(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


class Actor:
    """Someone in the graveyard: a zombie, a human or a hunter, and what they are up to."""

    def __init__(self, kind, figure, x, z, heading, speed, state):
        self.kind, self.figure = kind, figure
        self.x, self.z, self.heading, self.speed, self.state = x, z, heading, speed, state
        self.phase = 0.0
        self.timer = 0.0
        self.target = None
        self.shots = 0
        self.stamina = 1.0
        self.eat_at = self.eat_face = None  # where a feeding zombie kneels, and the head it faces

    @property
    def pos(self):
        return np.array([self.x, self.z])

    def forward(self):
        return np.array([np.sin(self.heading), np.cos(self.heading)])

    def steer(self, direction, dt, rate=3.0):
        want = np.arctan2(direction[0], direction[1])
        diff = (want - self.heading + np.pi) % (2 * np.pi) - np.pi
        self.heading += np.clip(diff, -rate * dt, rate * dt)

    def walk(self, dt, speed):
        f = self.forward()
        self.x += f[0] * speed * dt
        self.z += f[1] * speed * dt
        self.phase += speed * dt * 4.2


class Gib:
    """A flying piece of a shotgunned zombie: falls, bounces, spins and fades away."""

    LIFE = 3.0

    def __init__(self, obj, velocity, spin, rng):
        self.obj, self.velocity = obj, velocity
        self.axis, self.spin = normalize(rng.normal(size=3)), spin
        self.age = 0.0
        self.base_opacity = obj.opacity

    def update(self, dt):
        self.age += dt
        self.velocity[1] -= GRAVITY * dt
        p = self.obj.position + self.velocity * dt
        if p[1] < 0.08:
            p[1] = 0.08
            self.velocity = self.velocity * [0.6, -0.35, 0.6]
            self.spin *= 0.6
        self.obj.position = p
        self.obj.rotation = quat_mul(quat_axis_angle(self.axis, self.spin * dt), self.obj.rotation)
        self.obj.opacity = self.base_opacity * float(np.clip((self.LIFE - self.age) / 1.0, 0.0, 1.0))
        if hasattr(self.obj, "emissive") and self.obj.emissive:
            self.obj.emissive *= 0.97

    @property
    def done(self):
        return self.age >= self.LIFE


class Graveyard:
    """The scene behind the menus: see the module's docstring. update(dt), then render()."""

    MAX_ZOMBIES, MIN_ZOMBIES, MIN_HUMANS = 9, 4, 3

    def __init__(self, seed=None):
        self.rng = rng = np.random.default_rng(seed)
        self.renderer = GRAPHICS.track(Renderer(1, 1, fog=0.5, edge_samples=4, background=night_sky(rng)))
        self.camera = Camera(position=np.array([0.0, 4.2, 10.5]), target=np.array([0.0, 1.2, -5.0]), fov=50.0,
                             far=250.0)
        moon_at = np.array([-62.0, 38.0, -95.0])
        self.moonlight = Light(direction=normalize(np.array([0.0, 0.0, -4.0]) - moon_at), ambient=0.2, diffuse=0.5,
                               specular=0.03, color=(170, 185, 255), shadows=True)
        # A faint cool light from behind the camera, so that faces turned towards it aren't black.
        self.fill = Light(direction=np.array([-0.3, -0.6, -1.0]), ambient=0.0, diffuse=0.3, specular=0.0,
                          color=(140, 160, 230))
        self.fire_at = np.array([5.5, 0.0, -3.0])
        self.fire = PointLight(self.fire_at + [0.0, 0.9, 0.0], color=(255, 140, 50), diffuse=0.9, range=9.0,
                               shadows=True)
        self.lantern_at = np.array([-7.5, 2.5, -7.0])
        self.lantern = PointLight(self.lantern_at, color=(150, 255, 170), diffuse=0.6, range=7.0)
        self.logo = Logo()
        self.static = self._scenery(rng, moon_at)
        self.actors = []
        self.gibs = []
        self.effects = []   # [Object3D, age, life, kind]
        self.flashes = []   # [PointLight, age]
        self.brains = {}    # victim Actor -> brain Object3D
        self.t = 0.0
        self.hunter_timer = 6.0
        self.spawn_timer = 0.0
        self.owner = {}     # id(Object3D) -> Actor, for clicks
        for _ in range(6):
            self._add_zombie(rng.uniform(-9, 9), rng.uniform(-12, -2), "shamble")
        for _ in range(3):
            self._add_human(rng.uniform(-8, 8), rng.uniform(-11, 1))

    # ----- the scenery -------------------------------------------------------------

    def _scenery(self, rng, moon_at):
        objs = [Object3D(ground_mesh(rng), color=WHITE, cast_shadows=False)]
        for x, z, r in ((-5.0, -6.5, 1.8),):
            objs.append(Object3D(puddle_mesh(rng, r), np.array([x, 0.0, z]), color=(30, 40, 55), reflectivity=0.6))
        stone = tombstone_mesh()
        self.graves = []
        mounds = []
        for x, z in ((-8.5, -10.5), (-5.5, -11.5), (-2.0, -10.8), (1.5, -11.6), (4.5, -10.9), (-9.8, -4.5),
                     (9.5, -4.0), (-1.0, -6.5), (2.8, -6.2), (8.8, -12.5)):
            x, z = x + rng.uniform(-0.3, 0.3), z + rng.uniform(-0.3, 0.3)
            grey = int(rng.integers(120, 175))
            tilt = quat_mul(quat_axis_angle(UP, rng.uniform(-0.25, 0.25)), quat_axis_angle(Z_AXIS, rng.uniform(-0.12, 0.12)))
            objs.append(Object3D(stone, np.array([x, 0.0, z]), tilt, scale=0.75, color=(grey, grey, grey - 8)))
            mounds.append(blob_mesh((0.55, 0.16, 0.95), (x, 0.0, z + 1.05), rings=6, segments=10))
            self.graves.append(np.array([x, z + 1.05]))
        objs.append(Object3D(merge_meshes(mounds), color=(70, 52, 36)))
        crosses = [merge_meshes([block_mesh((x, 0.75, z), (0.12, 1.5, 0.12)), block_mesh((x, 1.1, z), (0.7, 0.12, 0.12))])
                   for x, z in ((-3.8, -13.2), (6.8, -13.8), (-11.0, -8.0))]
        objs.append(Object3D(merge_meshes(crosses), color=(92, 70, 48)))
        for x, z in ((-12.5, -12.0), (11.5, -9.5)):
            objs.append(Object3D(tree_mesh(rng), np.array([x, 0.0, z]), color=(48, 38, 34)))
        objs.append(Object3D(fence_mesh(-18.0, 18.0, -16.0), color=(40, 40, 46), cast_shadows=False))
        # The survivors' campfire: logs, see-through flames, and the light it throws.
        logs = merge_meshes([block_mesh((0.0, 0.12, 0.0), (1.1, 0.18, 0.18), quat_to_matrix_y(a)) for a in (0.3, 1.4, 2.4)])
        objs.append(Object3D(logs, self.fire_at.copy(), color=(80, 50, 30)))
        self.flames = [Object3D(blob_mesh((0.22, 0.5, 0.22), rings=6, segments=8), self.fire_at + [dx, 0.45, dz],
                                color=c, emissive=1.0, opacity=0.7, cast_shadows=False)
                       for dx, dz, c in ((0.0, 0.0, (255, 150, 40)), (0.15, 0.1, (255, 210, 80)), (-0.12, -0.08, (255, 90, 20)))]
        objs += self.flames
        # A lantern on a post, glowing green.
        objs.append(Object3D(block_mesh((0.0, 1.2, 0.0), (0.1, 2.4, 0.1)), self.lantern_at * [1, 0, 1], color=(30, 30, 30)))
        objs.append(Object3D(blob_mesh((0.16, 0.2, 0.16)), self.lantern_at.copy(), color=(160, 255, 180), emissive=1.0,
                             cast_shadows=False))
        objs.append(Object3D(blob_mesh((5.0, 5.0, 5.0), rings=12, segments=16), moon_at, color=(245, 240, 205),
                             emissive=1.0, cast_shadows=False))
        return objs

    # ----- people coming and going ---------------------------------------------------

    def _add(self, actor):
        self.actors.append(actor)
        for obj in actor.figure.objects:
            self.owner[id(obj)] = actor
        return actor

    def _remove(self, actor):
        if actor in self.actors:
            self.actors.remove(actor)
        for obj in actor.figure.objects:
            self.owner.pop(id(obj), None)
        brain = self.brains.pop(actor, None)
        if brain is not None:
            self.effects.append([brain, 0.0, 0.4, "fade"])

    def _add_zombie(self, x, z, state="rise_grave", heading=None):
        a = Actor("zombie", zombie_figure(self.rng), x, z, self.rng.uniform(0, 2 * np.pi) if heading is None else heading,
                  self.rng.uniform(0.6, 0.95), state)
        a.phase = self.rng.uniform(0, 6)
        if state.startswith("rise"):
            a.timer = 2.0
        return self._add(a)

    def _add_human(self, x, z, hunter=False):
        a = Actor("hunter" if hunter else "human", human_figure(self.rng, hunter), x, z, 0.0,
                  1.2 if hunter else self.rng.uniform(1.9, 2.3), "enter" if hunter else "run")
        return self._add(a)

    def _enter_from_edge(self, hunter=False):
        side = self.rng.choice([-1, 1])
        x, z = side * (FIELD[1] + 2.0), self.rng.uniform(-10, 0)
        a = self._add_human(x, z, hunter)
        a.heading = np.arctan2(-side, 0.0)
        a.timer = 0.0
        return a

    # ----- updating --------------------------------------------------------------------

    def update(self, dt):
        dt = min(dt, 0.1)
        self.t += dt
        self.logo.update(dt)
        zombies = [a for a in self.actors if a.kind == "zombie" and a.state in ("shamble", "eat")]
        prey = [a for a in self.actors if a.kind != "zombie" and a.state in ("run", "enter", "hunt", "leave", "trip")]
        for a in list(self.actors):
            getattr(self, "_" + a.kind)(a, dt, zombies, prey)
        self._spawn(dt, zombies, prey)
        for g in self.gibs:
            g.update(dt)
        self.gibs = [g for g in self.gibs if not g.done]
        for e in self.effects:
            e[1] += dt
            obj, age, life, kind = e
            k = max(1 - age / life, 0.0)
            if kind == "flash":
                obj.scale = 0.6 + age * 6
                obj.opacity = 0.85 * k
            elif kind == "word":
                obj.position = obj.position + [0.0, dt * 0.9, 0.0]
                obj.opacity = min(k * 2, 1.0)
            else:
                obj.opacity = k
        self.effects = [e for e in self.effects if e[1] < e[2]]
        for f in self.flashes:
            f[1] += dt
            f[0].diffuse = 2.2 * max(1 - f[1] / 0.25, 0.0)
        self.flashes = [f for f in self.flashes if f[1] < 0.25]
        # Flickering fire.
        flick = 0.85 + 0.1 * np.sin(self.t * 17) + 0.06 * np.sin(self.t * 29 + 1)
        self.fire.diffuse = 0.9 * flick
        for i, fl in enumerate(self.flames):
            fl.scale = 0.9 + 0.2 * np.sin(self.t * (11 + 4 * i) + i)
        self.camera.position = np.array([3.5 * np.sin(self.t * 0.05), 4.2 + 0.4 * np.sin(self.t * 0.13), 10.5])

    def _keep_in(self, a, margin=1.0):
        """A push back towards the field for someone near its edge."""
        x0, x1, z0, z1 = FIELD
        push = np.zeros(2)
        push[0] = max(x0 + margin - a.x, 0) - max(a.x - (x1 - margin), 0)
        push[1] = max(z0 + margin - a.z, 0) - max(a.z - (z1 - margin), 0)
        return push

    def _nearest(self, a, others, reach):
        best, best_d = None, reach
        for o in others:
            d = np.hypot(o.x - a.x, o.z - a.z)
            if d < best_d and o is not a:
                best, best_d = o, d
        return best, best_d

    def _zombie(self, a, dt, zombies, prey):
        f = a.figure
        if a.state in ("rise_grave", "rise_body"):
            a.timer -= dt
            k = 1 - max(a.timer, 0) / 2.0
            if a.state == "rise_grave":   # clawing up out of the ground
                f.place(a.x, a.z, a.heading, y=-1.9 * (1 - k) ** 1.5)
                f.pose(self.t * 6, 0.3, "zombie", sway=0.2 * np.sin(self.t * 5))
            else:                         # a fresh zombie sitting up, then standing
                f.place(a.x, a.z, a.heading)
                f.pose(0.0, 0.0, "zombie", fall=np.pi / 2 * (1 - k), hips_y=0.16 + (LEG - 0.16) * k)
            if a.timer <= 0:
                a.state = "shamble"
            return
        if a.state == "eat":
            a.timer -= dt
            a.phase += dt * 2
            brain = self.brains.get(a.target)
            if brain is not None:
                brain.scale = max(a.timer / 3.0, 0.05)
            # Step round to the victim's head, then crouch over it.
            to_spot = a.eat_at - a.pos
            gap = np.hypot(*to_spot)
            if gap > 0.02:
                step = min(gap, 1.6 * dt)
                a.x, a.z = a.pos + to_spot / gap * step
                a.phase += step * 4.2
            face = a.eat_face - a.pos
            a.steer(face, dt, 6.0)
            f.place(a.x, a.z, a.heading)
            if gap > 0.1:
                f.pose(a.phase, 0.35, "zombie", lean=0.12)
            else:
                f.pose(a.phase, 0.0, "eat", crouch=1.0)
            if a.timer <= 0:
                victim = a.target
                a.state, a.target = "shamble", None
                if victim is not None and victim in self.actors:
                    self._remove(victim)
                    if len([z for z in self.actors if z.kind == "zombie"]) < self.MAX_ZOMBIES:
                        self._add_zombie(victim.x, victim.z, "rise_body", victim.heading)
            return
        target, d = self._nearest(a, prey, 9.0)
        if target is not None:
            a.steer(target.pos - a.pos + self._keep_in(a) * 3, dt, 1.5)
            speed = a.speed * 1.25
            if d < 0.6 and target.state != "down":
                self._catch(a, target)
                return
        else:
            wander = a.forward() + self.rng.normal(scale=0.4, size=2) + self._keep_in(a, 2.0) * 2
            a.steer(wander, dt, 0.8)
            speed = a.speed * 0.6
        a.walk(dt, speed)
        f.place(a.x, a.z, a.heading)
        f.pose(a.phase, 0.35, "zombie", lean=0.12, sway=0.14 * np.sin(a.phase * 0.5))

    def _catch(self, zombie, victim):
        victim.state = "down"
        victim.timer = 0.0
        zombie.state, zombie.target, zombie.timer = "eat", victim, 3.4
        # The victim falls on their back, head behind them: the zombie goes round to kneel beyond the head.
        head = victim.pos - victim.forward() * (0.92 + 0.22)
        away = zombie.pos - head
        away = away / np.hypot(*away) if np.hypot(*away) > 0.1 else -victim.forward()
        zombie.eat_face, zombie.eat_at = head, head + away * 1.0
        brain = Object3D(_mesh("brain"), np.array([victim.x, 0.45, victim.z]), color=(240, 140, 160), emissive=0.15)
        self.brains[victim] = brain
        self._place_brain(victim)

    def _place_brain(self, victim):
        """Put the victim's brain where it belongs: poking out of the top of their skull, wherever their head is."""
        brain = self.brains.get(victim)
        if brain is None:
            return
        head = victim.figure.head
        brain.position = head.to_world((0.0, 0.24, 0.0)) + [0.0, 0.1, 0.0]
        brain.rotation = head.world_transform()[1]

    def _human(self, a, dt, zombies, prey):
        f = a.figure
        if a.state == "down":
            a.timer += dt
            fall = min(a.timer / 0.35, 1.0)
            f.place(a.x, a.z, a.heading)
            f.pose(0.0, 0.0, "down", fall=np.pi / 2 * fall, hips_y=LEG - (LEG - 0.16) * fall)
            self._place_brain(a)
            if a.timer > 6.0 and not any(z.target is a for z in self.actors):
                self._remove(a)  # the zombie that caught them was shot: they stay dead
            return
        if a.state == "trip":
            a.timer -= dt
            f.place(a.x, a.z, a.heading)
            f.pose(a.phase, 0.0, "run", lean=0.5, crouch=0.6)
            if a.timer <= 0:
                a.state = "run"
            return
        threat = np.zeros(2)
        near = 99.0
        for z in zombies:
            d = a.pos - z.pos
            dist = np.hypot(*d)
            near = min(near, dist)
            if dist < 7.0:
                threat += d / max(dist, 0.3) ** 2
        inside = self._keep_in(a, 1.5)
        if near < 7.0:
            a.steer(threat + inside * 4 + self.rng.normal(scale=0.3, size=2), dt, 4.0)
            a.stamina = max(a.stamina - dt * 0.12, 0.25)
            speed = a.speed * a.stamina
            if self.rng.random() < dt * 0.12:  # panicking people trip
                a.state, a.timer = "trip", 1.2
        else:
            a.steer(a.forward() + self.rng.normal(scale=0.5, size=2) + inside * 3, dt, 1.0)
            a.stamina = min(a.stamina + dt * 0.1, 1.0)
            speed = 0.8
        a.walk(dt, speed)
        f.place(a.x, a.z, a.heading)
        running = speed > 1.0
        f.pose(a.phase, 0.7 if running else 0.35, "run" if running else "down", lean=0.25 if running else 0.0)

    def _hunter(self, a, dt, zombies, prey):
        f = a.figure
        if a.state == "down":
            return self._human(a, dt, zombies, prey)
        if a.state in ("enter", "leave"):
            if a.state == "leave":
                a.steer(np.array([np.sign(a.x) or 1.0, 0.0]), dt, 2.0)
            elif abs(a.x) < FIELD[1] - 2.5:
                a.state, a.timer = "hunt", 0.8
            a.walk(dt, a.speed)
            f.place(a.x, a.z, a.heading)
            f.pose(a.phase, 0.4, "down")
            if a.state == "leave" and abs(a.x) > FIELD[1] + 3:
                self._remove(a)
            return
        a.timer -= dt
        target, d = self._nearest(a, [z for z in zombies if z.state in ("shamble", "eat")], 10.0)
        if target is None or a.shots >= 3:
            a.state = "leave"
            return
        a.steer(target.pos - a.pos, dt, 4.0)
        f.place(a.x, a.z, a.heading)
        f.pose(0.0, 0.0, "aim")
        if a.timer <= 0:
            if d > 7.0:  # too far for a shotgun: close in
                a.walk(dt, a.speed)
                f.place(a.x, a.z, a.heading)
                f.pose(a.phase, 0.4, "aim")
                return
            muzzle = f.shoulders[1].to_world((0.0, -1.1, 0.04))
            self.shoot(target, muzzle)
            a.shots += 1
            a.timer = 1.4

    def _spawn(self, dt, zombies, prey):
        self.spawn_timer -= dt
        self.hunter_timer -= dt
        n_zombies = len([a for a in self.actors if a.kind == "zombie"])
        n_humans = len([a for a in self.actors if a.kind == "human" and a.state != "down"])
        if self.spawn_timer <= 0:
            if n_zombies < self.MIN_ZOMBIES:
                x, z = self.graves[int(self.rng.integers(len(self.graves)))]
                self._add_zombie(x, z + 0.3, "rise_grave", heading=self.rng.uniform(-0.5, 0.5))
                self.spawn_timer = 1.5
            elif n_humans < self.MIN_HUMANS:
                self._enter_from_edge()
                self.spawn_timer = 2.0
        hunting = any(a.kind == "hunter" for a in self.actors)
        if not hunting and self.hunter_timer <= 0 and n_zombies >= 5:
            self._enter_from_edge(hunter=True)
            self.hunter_timer = self.rng.uniform(10, 16)

    # ----- shotguns ----------------------------------------------------------------------

    def shoot(self, zombie, muzzle=None):
        """Blow a zombie to pieces, with a muzzle flash where the shot came from (if anywhere)."""
        if zombie not in self.actors:
            return
        if muzzle is not None:
            flash = Object3D(_mesh("flash"), np.asarray(muzzle, float), color=(255, 230, 140), emissive=1.0, opacity=0.85,
                             cast_shadows=False)
            self.effects.append([flash, 0.0, 0.15, "flash"])
            self.flashes.append([PointLight(np.asarray(muzzle, float), color=(255, 220, 150), diffuse=2.2, range=9.0), 0.0])
        centre = zombie.figure.hips.to_world((0.0, 0.4, 0.0))
        for obj in zombie.figure.objects:
            pos, rot, scale, _ = obj.world_transform()
            obj.parent, obj.position, obj.rotation, obj.scale = None, pos, rot, scale
            push = normalize(pos - centre + self.rng.normal(scale=0.3, size=3)) * self.rng.uniform(3, 6)
            self.gibs.append(Gib(obj, push + [0.0, self.rng.uniform(2, 5), 0.0], self.rng.uniform(4, 14), self.rng))
        for i in range(12):  # goo and gore
            color = (150, 20, 20) if i % 3 else (90, 170, 60)
            obj = Object3D(_mesh("chunk"), centre + self.rng.normal(scale=0.15, size=3), color=color,
                           scale=self.rng.uniform(0.6, 1.4))
            v = normalize(self.rng.normal(size=3)) * self.rng.uniform(2, 7) + [0.0, 3.0, 0.0]
            self.gibs.append(Gib(obj, v, self.rng.uniform(5, 15), self.rng))
        mesh, w, _ = graded_text_mesh("BLAM!", (255, 230, 120), (255, 80, 30), depth=1.0)
        word = Object3D(mesh, centre + [0.0, 1.6, 0.0], facing(self.camera.position - centre), scale=1.4 / w,
                        color=WHITE, emissive=0.8, cast_shadows=False)
        self.effects.append([word, 0.0, 1.2, "word"])
        victim = zombie.target
        self._remove(zombie)
        if victim is not None and victim.state == "down":
            victim.timer = max(victim.timer, 4.5)  # dead, not rising: gone soon, as nobody is eating them
        self.owner = {id(o): a for a in self.actors for o in a.figure.objects}

    def click(self, x, y):
        """A click at cell (x, y) of the frame as last drawn: shoots the zombie there, if any. Returns
        whether it hit one."""
        hit = self.renderer.pick(x, y)
        if hit is None:
            return False
        actor = self.owner.get(id(hit.object))
        if actor is None or actor.kind != "zombie" or actor.state.startswith("rise"):
            return False
        self.shoot(actor)
        return True

    # ----- drawing ------------------------------------------------------------------------

    def objects(self):
        objs = list(self.static) + self.logo.objects
        for a in self.actors:
            objs += a.figure.objects
        objs += list(self.brains.values())
        objs += [g.obj for g in self.gibs] + [e[0] for e in self.effects]
        return objs

    def lights(self):
        return [self.moonlight, self.fill, self.fire, self.lantern] + [f[0] for f in self.flashes]

    def render(self, screen, top, left, width, height, logo_rows):
        """Draw the scene into the area, with the logo filling its first `logo_rows` rows."""
        if width < 4 or height < 3:
            return
        self.top, self.left = top, left
        self.renderer.resize(width, height, screen.cell_pixels)
        aspect = width * self.renderer.cell_aspect / height
        self.logo.place(self.camera, aspect, 0.5 / height, max(logo_rows - 0.5, 1) / height)
        screen.draw_frame(self.renderer.render(self.objects(), self.camera, self.lights()), top, left)


def quat_to_matrix_y(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


# ----- the lobby table --------------------------------------------------------------------

class LobbyTable:
    """The lobby in 3D: a round table under a hanging lamp, one chair per seat. Players sit as zombies
    in their name colour (bots with blue eyes); open seats hold see-through ghosts. The dice and the
    glass cup wait on the table, which is polished enough to mirror them."""

    RADIUS = 1.9

    def __init__(self):
        self.renderer = GRAPHICS.track(Renderer(1, 1, fog=0.3, background=(10, 10, 16)))
        self.camera = Camera(target=np.array([0.0, 0.6, 0.0]), fov=40.0)
        self.lamp = PointLight(np.array([0.0, 2.7, 0.0]), color=(255, 215, 150), diffuse=1.2, range=9.0, shadows=True,
                               ambient=0.15)
        self.fill = Light(direction=np.array([0.3, -1.0, -0.6]), ambient=0.2, diffuse=0.25, specular=0.1)
        top = Object3D(disc_mesh(1.25, 0.82, 40), color=(80, 45, 28), reflectivity=0.35)
        base = Object3D(lathe_mesh([(0.6, 0.0), (0.55, 0.06), (0.14, 0.12), (0.12, 0.7), (1.25, 0.76), (1.25, 0.82)],
                                   32), color=(60, 34, 20))
        bulb = Object3D(blob_mesh((0.14, 0.14, 0.14)), np.array([0.0, 2.7, 0.0]), color=(255, 235, 190), emissive=1.0,
                        cast_shadows=False)
        shade = Object3D(lathe_mesh([(0.55, 2.55), (0.18, 2.95), (0.0, 2.97)], 24, cap_bottom=False), color=(40, 70, 40),
                         double_sided=True)
        cord = Object3D(block_mesh((0.0, 3.6, 0.0), (0.03, 1.3, 0.03)), color=(20, 20, 20))
        self.scenery = [Object3D(disc_mesh(9.0, 0.0, 24), color=(45, 38, 34)), base, top, bulb, shade, cord]
        self.scenery += [Object3D(zombie_die_mesh(c), np.array([x, 0.97, z]), quat_axis_angle(UP, a), scale=0.3,
                                  color={GREEN: (50, 205, 50), YELLOW: (240, 200, 40), RED: (225, 45, 35)}[c])
                         for c, x, z, a in ((GREEN, -0.3, 0.25, 0.3), (YELLOW, 0.1, 0.4, 1.1), (RED, 0.35, 0.05, 2.0))]
        self.scenery.append(Object3D(lathe_mesh([(0.2, 0.0), (0.24, 0.05), (0.24, 0.5)], 20), np.array([0.0, 0.82, -0.4]),
                                     color=CUP_GLASS, opacity=0.2))
        self.chair = merge_meshes([block_mesh((0.0, 0.42, 0.0), (0.55, 0.08, 0.55)),
                                   block_mesh((0.0, 0.85, -0.25), (0.55, 0.8, 0.07))]
                                  + [block_mesh((x, 0.2, z), (0.06, 0.4, 0.06)) for x in (-0.22, 0.22) for z in (-0.22, 0.22)])
        self.seats = []   # (key, chair, figure)
        self.t = 0.0

    def seat(self, players, seats, name_color):
        """Seat the players ([{"name", "bot"}, ...]) and ghosts in the open seats; name_color(name) gives
        each player's colour, as in the lobby's list."""
        key = (seats, tuple((p["name"], p["bot"]) for p in players))
        if self.seats and self.seats[0][0] == key:
            return
        self.seats = []
        rng = np.random.default_rng(7)
        for i in range(seats):
            a = 2 * np.pi * i / max(seats, 1)
            x, z = self.RADIUS * np.sin(a), self.RADIUS * np.cos(a)
            heading = a + np.pi  # facing the middle
            chair = Object3D(self.chair, np.array([x, 0.0, z]), quat_axis_angle(UP, heading), color=(90, 60, 40))
            if i < len(players):
                p = players[i]
                shirt = HUE_RGB[name_color(p["name"])]
                eyes = (80, 170, 255) if p["bot"] else (255, 50, 30)
                fig = Figure(ZOMBIE_SKIN[i % len(ZOMBIE_SKIN)], shirt, PANTS[i % len(PANTS)], eyes, glowing_eyes=True)
                label = p["name"]
            else:
                fig = Figure((200, 220, 255), (200, 220, 255), (200, 220, 255), (200, 240, 255), glowing_eyes=True,
                             opacity=0.22)
                label = None
            fig.place(x * 0.93, z * 0.93, heading)
            self.seats.append((key, chair, fig, label, name_color(p["name"]) if label else None, rng.uniform(0, 6)))

    def update(self, dt):
        self.t += dt
        for _, _, fig, label, _, phase in self.seats:
            if label is None:  # ghosts bob gently
                fig.root.position = fig.root.position * [1, 0, 1] + [0.0, 0.08 + 0.05 * np.sin(self.t * 1.5 + phase), 0.0]
                fig.pose(self.t + phase, 0.0, "down", hips_y=0.52, lean=-0.05)
                for leg in fig.joints:
                    leg.rotation = quat_axis_angle(X_AXIS, -np.pi / 2)
                continue
            fig.pose(self.t * 1.3 + phase, 0.0, "zombie", hips_y=0.52, lean=0.1, sway=0.08 * np.sin(self.t + phase))
            for leg in fig.joints:
                leg.rotation = quat_axis_angle(X_AXIS, -np.pi / 2 - 0.1)
            for sh in fig.shoulders:  # arms resting on the table, drumming
                sh.rotation = quat_axis_angle(X_AXIS, -1.25 + 0.06 * np.sin(self.t * 6 + phase))

    def render(self, screen, top, left, width, height):
        if width < 8 or height < 4:
            return
        self.renderer.resize(width, height, screen.cell_pixels)
        aspect = width * self.renderer.cell_aspect / height
        a = self.t * 0.12
        direction = normalize([np.sin(a), 0.75, np.cos(a)])
        r = self.RADIUS + 0.5
        points = [(r * np.sin(b), y, r * np.cos(b)) for b in np.linspace(0, 2 * np.pi, 12, endpoint=False)
                  for y in (0.0, 1.5)]
        dist = fit_distance(self.camera, direction, points, aspect, 0.95, -0.92, 0.8)
        self.camera.position = self.camera.target + direction * dist
        objs = list(self.scenery)
        for _, chair, fig, _, _, _ in self.seats:
            objs += [chair, *fig.objects]
        screen.draw_frame(self.renderer.render(objs, self.camera, [self.lamp, self.fill]), top, left)
        # Players' names over their heads, as text; nearer seats first so they win overlaps.
        used = []
        order = sorted(self.seats, key=lambda s: -float(direction @ s[2].root.position))
        for _, _, fig, label, color, _ in order:
            if label is None:
                continue
            p = self.renderer.project(fig.head.to_world((0.0, 0.45, 0.0)))
            if p is None:
                continue
            text = label[:10]
            y, x = int(p[1]), int(p[0]) - len(text) // 2
            x = min(max(x, 0), width - len(text))
            if not 0 <= y < height or any(uy == y and ux < x + len(text) + 1 and x < ux + ul + 1 for uy, ux, ul in used):
                continue
            used.append((y, x, len(text)))
            screen.text(top + y, left + x, text, color, bold=True)
