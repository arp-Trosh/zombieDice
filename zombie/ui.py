"""Screens: main menu, multiplayer setup, lobby and the game table."""
from unicode3d.color import COLOR_MODES, Color
from unicode3d.keys import Key, MouseEvent

from .graphics import DIE_COLOR, DiceTray, KeptDice
from .net import DEFAULT_PORT, local_ip
from .rules import BRAIN, FACES, FEET, GREEN, MAX_SHOTGUNS, RED, SHOTGUN, WINNING_SCORE, YELLOW
from .session import MAX_NAME, MAX_PLAYERS, ClientSession, host_session, single_player_session

MIN_COLS, MIN_ROWS = 80, 24
ENTER = (10, 13, Key.ENTER)
BACKSPACE = (8, 127, Key.BACKSPACE)
ESC, TAB = 27, 9
NAME_COLORS = (Color.CYAN, Color.MAGENTA, Color.YELLOW, Color.GREEN, Color.BLUE, Color.RED)
FACE_WORD = {BRAIN: "brain", SHOTGUN: "shotgun", FEET: "footsteps"}
FACE_CHAR = {BRAIN: "B", SHOTGUN: "X", FEET: "F"}
FPS_STEPS = (30, 60, 120, 144)
# Status line fields: the longest glyph set, colour mode and "achieved/target" frame rate.
STATUS_WIDTHS = (len("sextant"), len("truecolor"), len("144/144fps"))
STATUS_WIDTH = sum(3 + w for w in STATUS_WIDTHS) + 2 * (len(STATUS_WIDTHS) - 1)  # "F2 " before each, 2 between


class ViewArea:
    """The screen as a view sees it: everything but the bottom row, which the App keeps for its status line."""

    def __init__(self, screen):
        self._screen = screen

    def __getattr__(self, name):
        return getattr(self._screen, name)

    def size(self):
        rows, cols = self._screen.size()
        return rows - 1, cols


class Click:
    def __init__(self, y, x):
        self.y, self.x = y, x


def name_color(name):
    return NAME_COLORS[sum(map(ord, name)) % len(NAME_COLORS)]


class TextField:
    def __init__(self, value="", max_len=32, allowed=None):
        self.value = value
        self.max_len = max_len
        self.allowed = allowed

    def handle(self, k):
        if k in BACKSPACE:
            self.value = self.value[:-1]
        elif isinstance(k, int) and 32 <= k < 127:
            ch = chr(k)
            if len(self.value) < self.max_len and (self.allowed is None or ch in self.allowed):
                self.value += ch
        else:
            return False
        return True

    def draw(self, screen, y, x, width, focused):
        shown = (self.value + ("_" if focused else ""))[-width:]
        screen.text(y, x, shown.ljust(width), Color.WHITE if focused else Color.DEFAULT, reverse=focused)


class Stepper:
    """A number picked with Left/Right (or -/+), drawn as "< n >"; clicks on the arrows work too."""
    DEC = (Key.LEFT, ord("-"), ord("_"))
    INC = (Key.RIGHT, ord("+"), ord("="))

    def __init__(self, value, lo, hi):
        self.lo, self.hi = lo, hi
        self.value = max(lo, min(hi, value))

    def step(self, delta):
        self.value = max(self.lo, min(self.hi, self.value + delta))

    def handle(self, k):
        if k in self.DEC:
            self.step(-1)
        elif k in self.INC:
            self.step(1)
        else:
            return False
        return True

    def draw(self, view, screen, y, x, focused, suffix=""):
        screen.text(y, x, "<", Color.YELLOW if self.value > self.lo else Color.DEFAULT, bold=True, dim=self.value <= self.lo)
        screen.text(y, x + 2, f"{self.value}", Color.WHITE, bold=True, reverse=focused)
        screen.text(y, x + 4, ">", Color.YELLOW if self.value < self.hi else Color.DEFAULT, bold=True, dim=self.value >= self.hi)
        if suffix:
            screen.text(y, x + 6, suffix, dim=True)
        view.hits.append((y, x, x + 2, lambda: self.step(-1)))
        view.hits.append((y, x + 4, x + 6, lambda: self.step(1)))


class Toggle:
    """A Yes/No choice flipped with Left/Right, space or a click, drawn as "< Yes >"."""

    def __init__(self, value):
        self.value = bool(value)

    def flip(self):
        self.value = not self.value

    def handle(self, k):
        if k in (Key.LEFT, Key.RIGHT, ord(" ")):
            self.flip()
            return True
        return False

    def draw(self, view, screen, y, x, focused, suffix=""):
        screen.text(y, x, "<", Color.YELLOW, bold=True)
        screen.text(y, x + 2, "Yes" if self.value else "No ", Color.GREEN if self.value else Color.RED,
                    bold=True, reverse=focused)
        screen.text(y, x + 6, ">", Color.YELLOW, bold=True)
        if suffix:
            screen.text(y, x + 8, suffix, dim=True)
        view.hits.append((y, x, x + 7, self.flip))


def cycle(options, current):
    """The option after `current`, wrapping round; for a number not listed, the next one up."""
    if current in options:
        return options[(options.index(current) + 1) % len(options)]
    return next((o for o in options if o > current), options[0])


def button_row_width(buttons):
    """Columns View.button_row takes for these buttons: "[ label ]" each, one space between."""
    return sum(len(label) + 4 for label, _, _ in buttons) + len(buttons) - 1


def draw_box(screen, top, left, height, width, title=None, color=Color.DEFAULT):
    if height < 2 or width < 2:
        return
    screen.text(top, left, "+" + "-" * (width - 2) + "+", color)
    for y in range(top + 1, top + height - 1):
        screen.text(y, left, "|", color)
        screen.text(y, left + width - 1, "|", color)
    screen.text(top + height - 1, left, "+" + "-" * (width - 2) + "+", color)
    if title:
        screen.text(top, left + 2, f" {title} ", color, bold=True)


def draw_segments(screen, y, x, segments, max_width=None):
    """Draw [(text, color, bold), ...] left to right; returns the x after the last one."""
    end = None if max_width is None else x + max_width
    for text, color, bold in segments:
        if end is not None:
            text = text[:max(end - x, 0)]
        screen.text(y, x, text, color, bold=bold)
        x += len(text)
    return x


def wrap_segments(segments, width):
    """Split coloured segments into lines of at most `width` characters."""
    lines, line, used = [], [], 0
    for text, color, bold in segments:
        while text:
            room = width - used
            if room <= 0:
                lines.append(line)
                line, used = [], 0
                room = width
            line.append((text[:room], color, bold))
            used += len(text[:room])
            text = text[room:]
    lines.append(line)
    return lines


class View:
    """A full-screen page. Subclasses implement key(), draw() and optionally tick()."""

    def __init__(self, app):
        self.app = app
        self.hits = []

    def tick(self, dt):
        pass

    def frame(self, screen, dt, keys):
        for k in keys:
            if isinstance(k, Click):
                for y, x0, x1, action in self.hits:
                    if k.y == y and x0 <= k.x < x1:
                        action()
                        break
            else:
                self.key(k)
            if self.app.view is not self:
                return
        self.hits = []
        screen.erase()
        self.draw(screen, dt)

    def key(self, k):
        pass

    def draw(self, screen, dt):
        pass

    def button(self, screen, y, x, label, action, focused=False, enabled=True, color=Color.DEFAULT):
        text = f"[ {label} ]"
        screen.text(y, x, text, color if enabled else Color.DEFAULT,
                    bold=enabled and focused, reverse=enabled and focused, dim=not enabled)
        if enabled:
            self.hits.append((y, x, x + len(text), action))
        return len(text)

    def button_row(self, screen, y, x, buttons, focus):
        """buttons: [(label, action, enabled)]. Returns the x after the row."""
        for i, (label, action, enabled) in enumerate(buttons):
            x += self.button(screen, y, x, label, action, focused=(i == focus), enabled=enabled) + 1
        return x


# ----- menus -----------------------------------------------------------------------

class MenuView(View):
    ITEMS = ("Single Player", "Multiplayer", "Quit")

    def __init__(self, app):
        super().__init__(app)
        self.focus = 0

    def key(self, k):
        if k in (Key.UP, ord("k")):
            self.focus = (self.focus - 1) % len(self.ITEMS)
        elif k in (Key.DOWN, ord("j"), TAB):
            self.focus = (self.focus + 1) % len(self.ITEMS)
        elif k in ENTER or k == ord(" "):
            self.choose(self.focus)
        elif k in (ord("q"), ESC):
            self.app.running = False

    def choose(self, i):
        self.app.flash = ""
        if i == 0:
            self.app.view = SinglePlayerView(self.app)
        elif i == 1:
            self.app.view = MultiplayerView(self.app)
        else:
            self.app.running = False

    def draw(self, screen, dt):
        rows, cols = screen.size()
        self.app.logo.update(dt)
        title_h = max(10, int(rows * 0.62))
        self.app.logo.render(screen, 0, 0, cols, title_h)
        y = title_h + 1
        for i, item in enumerate(self.ITEMS):
            label = f"{item:^17}"
            x = (cols - len(label) - 4) // 2
            self.button(screen, y, x, label, lambda i=i: self.choose(i), focused=(i == self.focus),
                        color=(Color.GREEN, Color.YELLOW, Color.RED)[i])
            y += 2
        if self.app.flash:
            msg = self.app.flash[:cols - 2]
            screen.text(rows - 2, (cols - len(msg)) // 2, msg, Color.YELLOW, bold=True)
        hint = "Up/Down + Enter, or click"
        screen.text(rows - 1, (cols - len(hint)) // 2, hint, dim=True)


class SinglePlayerView(View):
    """Pick how many zombies sit at the table before a single player game."""

    def __init__(self, app):
        super().__init__(app)
        self.players = Stepper(app.sp_players, 2, MAX_PLAYERS)
        self.items = [("Players", self.players), ("Start Game", self.start), ("Back", self.back)]
        self.focus = 1

    def key(self, k):
        label, item = self.items[self.focus]
        if k in (Key.UP, ord("k")):
            self.focus = (self.focus - 1) % len(self.items)
        elif k in (Key.DOWN, ord("j"), TAB):
            self.focus = (self.focus + 1) % len(self.items)
        elif k in (ESC, ord("q")):
            self.back()
        elif self.players.handle(k):
            self.app.sp_players = self.players.value
        elif k in ENTER or k == ord(" "):
            if isinstance(item, Stepper):
                self.start()
            else:
                item()

    def start(self):
        self.app.sp_players = self.players.value
        self.app.view = GameView(self.app, single_player_session(self.app.name, npcs=self.players.value - 1))

    def back(self):
        self.app.view = MenuView(self.app)

    def draw(self, screen, dt):
        rows, cols = screen.size()
        self.app.logo.update(dt)
        title_h = max(8, int(rows * 0.5))
        self.app.logo.render(screen, 0, 0, cols, title_h)
        left = (cols - 40) // 2
        y = title_h + 1
        screen.text(y, left, "SINGLE PLAYER", Color.GREEN, bold=True)
        y += 2
        for i, (label, item) in enumerate(self.items):
            focused = i == self.focus
            if isinstance(item, Stepper):
                screen.text(y, left, f"{label:>9}: ", bold=focused)
                bots = item.value - 1
                item.draw(self, screen, y, left + 11, focused, f"you + {bots} bot{'s' * (bots != 1)}")
                self.hits.append((y, left, left + 11, lambda i=i: setattr(self, "focus", i)))
                y += 2
            else:
                self.button(screen, y, left + 11, label, item, focused=focused,
                            color=Color.GREEN if label != "Back" else Color.DEFAULT)
                y += 1
        hint = "Left/Right or -/+ to change players, Enter to start, Esc to go back"
        screen.text(rows - 1, max((cols - len(hint)) // 2, 0), hint[:cols], dim=True)


class MultiplayerView(View):
    def __init__(self, app):
        super().__init__(app)
        digits = "0123456789"
        self.name = TextField(app.name, MAX_NAME)
        self.host_port = TextField(str(app.host_port), 5, digits)
        self.join_addr = TextField(app.join_addr, 64, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:")
        self.join_port = TextField(str(app.join_port), 5, digits)
        self.players = Stepper(app.mp_players, 2, MAX_PLAYERS)
        self.bots = Toggle(app.mp_bots)
        self.items = [
            ("Your name", self.name),
            ("Host on port", self.host_port),
            ("Players", self.players),
            ("Bots", self.bots),
            ("Host Game", self.host),
            ("Join address", self.join_addr),
            ("Join port", self.join_port),
            ("Join Game", self.join),
            ("Back", self.back),
        ]
        self.focus = 4
        self.error = ""

    def key(self, k):
        label, item = self.items[self.focus]
        if k in (Key.UP,):
            self.focus = (self.focus - 1) % len(self.items)
        elif k in (Key.DOWN, TAB):
            self.focus = (self.focus + 1) % len(self.items)
        elif k == ESC:
            self.back()
        elif isinstance(item, TextField):
            if k in ENTER:
                self.focus = (self.focus + 1) % len(self.items)
            else:
                item.handle(k)
                self.remember()
        elif isinstance(item, (Stepper, Toggle)):
            if k in ENTER:
                self.focus = (self.focus + 1) % len(self.items)
            elif item.handle(k):
                self.remember()
        elif k in ENTER or k == ord(" "):
            item()

    def remember(self):
        self.app.name = self.name.value.strip() or self.app.name
        self.app.join_addr = self.join_addr.value
        self.app.mp_players = self.players.value
        self.app.mp_bots = self.bots.value
        for field, attr in ((self.host_port, "host_port"), (self.join_port, "join_port")):
            if field.value.isdigit():
                setattr(self.app, attr, int(field.value))

    def port(self, field):
        if field.value.isdigit() and 1 <= int(field.value) <= 65535:
            return int(field.value)
        self.error = "Ports must be a number from 1 to 65535."
        return None

    def player_name(self):
        name = self.name.value.strip()
        if not name:
            self.error = "Please enter a name."
        return name

    def host(self):
        self.remember()
        name, port = self.player_name(), self.port(self.host_port)
        if not name or port is None:
            return
        try:
            session = host_session(name, port, max_players=self.players.value,
                                   allow_bots=self.bots.value)
        except OSError as e:
            self.error = f"Can't host on port {port}: {e.strerror or e}"
            return
        self.app.view = LobbyView(self.app, session)

    def join(self):
        self.remember()
        name, port = self.player_name(), self.port(self.join_port)
        addr = self.join_addr.value.strip()
        if not name or port is None:
            return
        if not addr:
            self.error = "Enter the host's address."
            return
        try:
            session = ClientSession(name, addr, port)
        except OSError as e:
            self.error = f"Can't connect to {addr}:{port}: {e.strerror or e}"
            return
        self.app.view = LobbyView(self.app, session)

    def back(self):
        self.app.view = MenuView(self.app)

    def draw(self, screen, dt):
        rows, cols = screen.size()
        self.app.logo.update(dt)
        title_h = max(8, int(rows * 0.4))
        self.app.logo.render(screen, 0, 0, cols, title_h)
        width = 50
        left = (cols - width) // 2
        y = title_h + 1
        screen.text(y, left, "MULTIPLAYER", Color.YELLOW, bold=True)
        y += 2
        for i, (label, item) in enumerate(self.items):
            focused = i == self.focus
            if label == "Join address":
                y += 1
            if isinstance(item, TextField):
                screen.text(y, left, f"{label:>14}: ", bold=focused)
                item.draw(screen, y, left + 16, 22, focused)
                self.hits.append((y, left, left + 38, lambda i=i: setattr(self, "focus", i)))
            elif isinstance(item, Stepper):
                screen.text(y, left, f"{label:>14}: ", bold=focused)
                item.draw(self, screen, y, left + 16, focused, "seats")
                self.hits.append((y, left, left + 16, lambda i=i: setattr(self, "focus", i)))
            elif isinstance(item, Toggle):
                screen.text(y, left, f"{label:>14}: ", bold=focused)
                item.draw(self, screen, y, left + 16, focused,
                          "fill empty seats" if item.value else "humans only")
                self.hits.append((y, left, left + 16, lambda i=i: setattr(self, "focus", i)))
            else:
                self.button(screen, y, left + 16, label, item, focused=focused,
                            color=Color.GREEN if label != "Back" else Color.DEFAULT)
            y += 1
        if self.error:
            screen.text(y + 1, left, self.error[:cols - left - 1], Color.RED, bold=True)
        hint = "Up/Down/Tab to move, type or Left/Right to edit, Enter to select, Esc to go back"
        screen.text(rows - 1, max((cols - len(hint)) // 2, 0), hint[:cols], dim=True)


# ----- shared chat handling --------------------------------------------------------

class SessionView(View):
    """Base for views attached to a live session: polling, chat, and leaving."""

    def __init__(self, app, session):
        super().__init__(app)
        self.session = session
        self.chat_field = TextField("", 200)
        self.chatting = False
        self.focus = 0

    def tick(self, dt):
        self.session.poll()
        if self.session.error:
            self.leave(self.session.error)

    def leave(self, message=""):
        self.session.close()
        self.app.flash = message
        self.app.view = MenuView(self.app)

    def chat_key(self, k):
        """Handle a key while the chat box has focus."""
        if k in ENTER:
            if self.chat_field.value.strip():
                self.session.chat(self.chat_field.value)
            self.chat_field.value = ""
            self.chatting = False
        elif k in (ESC, TAB):
            self.chatting = False
        else:
            self.chat_field.handle(k)

    def start_chat(self):
        self.chatting = True

    def draw_chat(self, screen, top, left, height, width):
        draw_box(screen, top, left, height, width, "Chat", Color.CYAN if self.chatting else Color.DEFAULT)
        inner = width - 4
        lines = []
        for entry in self.session.history:
            name, text, kind = entry.get("name"), str(entry.get("text", "")), entry.get("kind")
            if kind == "chat" and name:
                segs = [(f"{name}: ", name_color(name), True), (text, Color.WHITE, False)]
            elif kind == "system":
                segs = [(f"* {text}", Color.CYAN, False)]
            else:
                segs = [(text, entry.get("color") or Color.DEFAULT, False)]
            lines += wrap_segments(segs, inner)
        visible = height - 3
        for i, line in enumerate(lines[-visible:] if visible > 0 else []):
            draw_segments(screen, top + 1 + i, left + 2, line)
        y = top + height - 2
        if self.chatting:
            screen.text(y, left + 2, "> ", Color.CYAN, bold=True)
            self.chat_field.draw(screen, y, left + 4, inner - 2, True)
        else:
            screen.text(y, left + 2, "Press T or Tab to talk"[:inner], dim=True)
        self.hits.append((y, left, left + width, self.start_chat))


class LobbyView(SessionView):
    def __init__(self, app, session):
        super().__init__(app, session)
        self.state = None
        self.address = f"{local_ip()}:{session.port}" if session.is_host else session.address

    def tick(self, dt):
        super().tick(dt)
        if self.app.view is not self:
            return
        while self.session.states:
            s = self.session.states.popleft()
            if s.get("phase") != "lobby":
                self.session.states.appendleft(s)
                self.app.view = GameView(self.app, self.session)
                return
            self.state = s

    def buttons(self):
        if not self.session.is_host:
            return [("Leave", self.leave, True)]
        seats, allow_bots = self.session.max_players, self.session.allow_bots
        humans = sum(not p["bot"] for p in self.state["players"]) if self.state else 1
        return [
            ("Start Game", self.start, allow_bots or humans >= 2),
            ("Players -", lambda: self.change_seats(-1), seats > max(2, humans)),
            ("Players +", lambda: self.change_seats(1), seats < MAX_PLAYERS),
            (f"Bots: {'On' if allow_bots else 'Off'}", self.toggle_bots, True),
            ("Leave", self.leave, True),
        ]

    def toggle_bots(self):
        self.session.set_allow_bots(not self.session.allow_bots)

    def start(self):
        self.session.fill_seats()
        self.session.start_game()

    def change_seats(self, delta):
        self.session.set_max_players(self.session.max_players + delta)

    def key(self, k):
        if self.chatting:
            return self.chat_key(k)
        buttons = self.buttons()
        if k in (Key.LEFT,):
            self.focus = (self.focus - 1) % len(buttons)
        elif k in (Key.RIGHT,):
            self.focus = (self.focus + 1) % len(buttons)
        elif k in ENTER or k == ord(" "):
            label, action, enabled = buttons[min(self.focus, len(buttons) - 1)]
            if enabled:
                action()
        elif k in (ord("t"), TAB):
            self.start_chat()
        elif k in (ord("q"), ESC):
            self.leave()
        elif self.session.is_host and k in Stepper.DEC[1:]:
            self.change_seats(-1)
        elif self.session.is_host and k in Stepper.INC[1:]:
            self.change_seats(1)
        elif self.session.is_host and k == ord("s"):
            self.start()
        elif self.session.is_host and k == ord("b"):
            self.toggle_bots()

    def draw(self, screen, dt):
        rows, cols = screen.size()
        chat_h = max(8, rows // 3)
        chat_top = rows - chat_h
        screen.text(0, 2, "LOBBY", Color.GREEN, bold=True)
        if self.session.is_host:
            info = f"Hosting at {self.address} - friends choose Multiplayer > Join with this address"
        else:
            info = f"Connected to {self.address}"
        screen.text(0, 9, info[:cols - 10], Color.YELLOW)

        list_h = chat_top - 4
        players = self.state["players"] if self.state else []
        seats = self.state.get("max_players", len(players)) if self.state else 0
        draw_box(screen, 2, 2, list_h, 44, f"Players {len(players)}/{seats}")
        for i in range(len(players), min(seats, list_h - 2)):
            screen.text(3 + i, 4, "(open seat)", dim=True)
        for i, p in enumerate(players[:list_h - 2]):
            tags = []
            if p["id"] == self.session.my_id:
                tags.append("you")
            if i == 0 and not p["bot"]:
                tags.append("host")
            if p["bot"]:
                tags.append("bot")
            screen.text(3 + i, 4, f"{p['name']:<18}", name_color(p["name"]), bold=p["id"] == self.session.my_id)
            screen.text(3 + i, 23, ", ".join(tags), dim=True)
        bots_on = self.state.get("bots", True) if self.state else True
        seats_note = "Bots fill open seats at Start." if bots_on else "Humans only - no bots."
        if not self.session.is_host:
            tips = [("Waiting for the host", Color.CYAN), ("to start the game...", Color.CYAN), (seats_note, None)]
        else:
            tips = [(seats_note, Color.CYAN), ("Keys: S start  -/+ players", None), ("      B bots  T talk  Q leave", None)]
        for i, (tip, color) in enumerate(tips):
            screen.text(3 + i, 49, tip[:cols - 50], color or Color.DEFAULT, dim=color is None)

        buttons = self.buttons()
        self.focus = min(self.focus, len(buttons) - 1)
        self.button_row(screen, chat_top - 1, 2, buttons, None if self.chatting else self.focus)
        self.draw_chat(screen, chat_top, 0, chat_h, cols)


# ----- the game table --------------------------------------------------------------

class GameView(SessionView):
    SIDE_W = 30
    CTRL_H = 4

    def __init__(self, app, session):
        super().__init__(app, session)
        self.tray = DiceTray()
        self.kept = KeptDice()
        self.shown = None         # state currently on display
        self.anim_state = None    # state waiting for its roll animation to land
        self.anim_event = None
        self.last_event_id = None
        self.game_id = None
        self.confirm_leave = False

    # ----- state flow --------------------------------------------------------------

    def tick(self, dt):
        super().tick(dt)
        if self.app.view is not self:
            return
        self.tray.update(dt * self.session.speed)
        self.kept.update(dt)
        if self.anim_state is not None and not self.tray.animating:
            s, self.anim_state = self.anim_state, None
            self.landed(s)
        while self.anim_state is None and self.session.states:
            self.apply(self.session.states.popleft())

    def player_name(self, s, index):
        return s["players"][index]["name"]

    def apply(self, s):
        if s.get("phase") == "lobby":
            return
        if s["game_id"] != self.game_id:
            self.game_id = s["game_id"]
            self.tray.clear()
            self.shown = None
            self.session.log(f"A new game begins! First to {WINNING_SCORE} brains triggers the final round.", Color.GREEN)
        ev = s.get("event")
        if ev and ev["id"] != self.last_event_id:
            self.last_event_id = ev["id"]
            if ev["kind"] == "roll":
                self.tray.roll([tuple(d) for d in ev["dice"]])
                self.anim_state, self.anim_event = s, ev
                return
            if ev["kind"] == "stop":
                n = ev["brains"]
                self.session.log(f"{self.player_name(s, ev['player'])} stops and eats {n} brain{'s' * (n != 1)} "
                                 f"(total {ev['score']}).", Color.GREEN)
        self.show(s)

    def landed(self, s):
        ev = self.anim_event
        name = self.player_name(s, ev["player"])
        faces = ", ".join(FACE_WORD[face] for _, face in ev["dice"])
        self.session.log(f"{name} rolled: {faces}.")
        if ev["busted"]:
            lost = ev["brains"]
            dropped = f"drops {lost} brain{'s' * (lost != 1)}" if lost else "the turn is over"
            self.session.log(f"BLAM! {name} took {ev['shotguns']} shotgun blasts - {dropped}.", Color.RED)
        self.show(s)

    def show(self, s):
        prev, self.shown = self.shown, s
        if s["phase"] == "over":
            if prev is None or prev["phase"] != "over":
                names = [self.player_name(s, i) for i in s["winners"]]
                score = s["players"][s["winners"][0]]["score"]
                who = names[0] if len(names) == 1 else " and ".join(names)
                verb = "wins" if len(names) == 1 else "tie"
                self.session.log(f"GAME OVER - {who} {verb} with {score} brains!", Color.YELLOW)
            return
        if s.get("final_round") and not (prev and prev.get("final_round")):
            t = s["triggered_by"]
            self.session.log(f"{self.player_name(s, t)} reached {s['players'][t]['score']} brains! "
                             "FINAL ROUND - everyone else gets one last turn.", Color.YELLOW)
        if prev is None or prev.get("current") != s.get("current"):
            p = s["players"][s["current"]]
            if p["id"] == self.session.my_id:
                self.session.log("Your turn! Press R to roll.", Color.CYAN)
            else:
                self.session.log(f"{p['name']}'s turn.", None)

    # ----- input -------------------------------------------------------------------

    @property
    def busy(self):
        return self.anim_state is not None or bool(self.session.states) or self.tray.animating

    @property
    def my_turn(self):
        s = self.shown
        return (s is not None and s["phase"] == "playing" and not self.busy
                and s["players"][s["current"]]["id"] == self.session.my_id)

    def roll(self):
        if self.my_turn:
            self.confirm_leave = False
            self.session.act("roll")

    def stop(self):
        if self.my_turn and self.shown["turn"]["rolls"] > 0:
            self.confirm_leave = False
            self.session.act("stop")

    def toggle_speed(self):
        if self.single_player:
            self.session.speed = 1.0 if self.session.speed > 1 else 3.0

    def play_again(self):
        if self.session.is_host and self.shown and self.shown["phase"] == "over":
            self.session.start_game()

    def request_leave(self):
        if self.confirm_leave or (self.shown and self.shown["phase"] == "over"):
            self.leave()
        else:
            self.confirm_leave = True

    @property
    def single_player(self):
        return self.session.is_host and self.session.server is None

    def buttons(self, compact=False):
        """[(label, action, enabled)]; compact labels, key first, for narrow terminals."""
        label = (lambda full, short: short) if compact else (lambda full, short: full)
        leave = (label("Really leave? (Q)", "Q Leave?") if self.confirm_leave else label("Leave (Q)", "Q Leave"),
                 self.request_leave, True)
        if self.shown and self.shown["phase"] == "over":
            if self.session.is_host:
                return [(label("Play Again (P)", "P Again"), self.play_again, True), leave]
            return [leave]
        mine = self.my_turn
        rolled = bool(self.shown and self.shown["turn"]["rolls"] > 0)
        buttons = [(label("Roll Dice (R)", "R Roll"), self.roll, mine),
                   (label("Stop & Eat Brains (S)", "S Stop"), self.stop, mine and rolled)]
        if self.single_player:
            speed = 3 if self.session.speed > 1 else 1
            buttons.append((label(f"Speed x{speed} (F)", f"F x{speed}"), self.toggle_speed, True))
        return buttons + [leave]

    def key(self, k):
        if self.chatting:
            return self.chat_key(k)
        buttons = self.buttons()
        if k != ord("q") and k != ESC and not (k in ENTER and buttons[self.focus % len(buttons)][1] == self.request_leave):
            self.confirm_leave = False
        if k == Key.LEFT:
            self.focus = (self.focus - 1) % len(buttons)
        elif k == Key.RIGHT:
            self.focus = (self.focus + 1) % len(buttons)
        elif k in ENTER or k == ord(" "):
            label, action, enabled = buttons[self.focus % len(buttons)]
            if enabled:
                action()
        elif k in (ord("r"), ord("R")):
            self.roll()
        elif k in (ord("s"), ord("S")):
            self.stop()
        elif k in (ord("f"), ord("F")):
            self.toggle_speed()
        elif k in (ord("p"), ord("P")):
            self.play_again()
        elif k in (ord("q"), ord("Q")):
            self.request_leave()
        elif k == ESC:
            self.confirm_leave = False
        elif k in (ord("t"), ord("T"), TAB):
            self.start_chat()

    # ----- drawing -----------------------------------------------------------------

    def draw(self, screen, dt):
        rows, cols = screen.size()
        chat_h = max(7, rows // 4)
        chat_top = rows - chat_h
        side_w = self.SIDE_W
        main_w = cols - side_w
        tray_h = chat_top - self.CTRL_H

        kept_w = 26 if cols >= 120 else 14
        self.draw_kept(screen, 0, 0, tray_h, kept_w)
        self.tray.render(screen, 0, kept_w, main_w - 1 - kept_w, tray_h)
        self.draw_tray_overlay(screen, kept_w, main_w - 1 - kept_w, tray_h)
        screen.text(tray_h, 0, "-" * (main_w - 1))
        self.draw_status(screen, tray_h + 1, main_w - 2)
        buttons = self.buttons()
        if button_row_width(buttons) > main_w - 2:  # the row ends where the scoreboard begins
            buttons = self.buttons(compact=True)
        self.focus %= len(buttons)
        self.button_row(screen, chat_top - 1, 1, buttons, None if self.chatting else self.focus)
        self.draw_scoreboard(screen, 0, main_w - 1, chat_top, side_w + 1)
        self.draw_chat(screen, chat_top, 0, chat_h, cols)

    def draw_kept(self, screen, top, left, height, width):
        """The "Dice Kept" panel: this turn's shotguns (X), brains, and footsteps waiting to be rerolled (feet)."""
        draw_box(screen, top, left, height, width, "Dice Kept", Color.GREEN)
        s = self.shown
        if s is None or s["phase"] == "over":
            return
        t = s["turn"]
        brains = len(t["brains"]) + t["recycled"]
        inner_w = width - 2
        y = top + 1
        header = [(f"Brains {brains}", Color.GREEN, True), (f"Shots {len(t['shotguns'])}/{MAX_SHOTGUNS}", Color.RED, True)]
        if inner_w >= 20:
            draw_segments(screen, y, left + 1, [header[0], ("  ", Color.DEFAULT, False), header[1]], inner_w)
            y += 1
        else:
            for seg in header:
                draw_segments(screen, y, left + 1, [seg], inner_w)
                y += 1
        if t["recycled"]:
            note = f"+{t['recycled']} brains eaten earlier" if inner_w >= 24 else f"+{t['recycled']} earlier"
            screen.text(y, left + 1, note[:inner_w], dim=True)
            y += 1
        dice = [(c, SHOTGUN) for c in t["shotguns"]] + [(c, BRAIN) for c in t["brains"]] + [(c, FEET) for c in t["feet"]]
        if not dice:
            msg = "Nothing yet"
            screen.text(y + 1, left + 1 + max((inner_w - len(msg)) // 2, 0), msg[:inner_w], dim=True)
            return
        area_h = top + height - 1 - y
        if len(dice) > self.kept.capacity(inner_w, area_h):
            area_h -= 1  # leave a row for the overflow note
        drawn = self.kept.render(screen, y, left + 1, inner_w, area_h, dice)
        if drawn < len(dice):
            screen.text(top + height - 2, left + 1, f"+{len(dice) - drawn} more"[:inner_w], Color.WHITE, bold=True)

    def draw_tray_overlay(self, screen, x0, width, height):
        s = self.shown
        if s is None:
            return
        if s["phase"] == "over":
            names = [self.player_name(s, i) for i in s["winners"]]
            score = s["players"][s["winners"][0]]["score"]
            lines = ["G A M E   O V E R", "",
                     (f"{names[0]} wins with {score} brains!" if len(names) == 1
                      else f"Tie at {score} brains: {', '.join(names)}")]
            if any(s["players"][i]["id"] == self.session.my_id for i in s["winners"]):
                lines.append("You are the ultimate zombie!")
            box_w = min(max(len(line) for line in lines) + 6, width - 2)
            top, left = max(height // 2 - 3, 0), x0 + max((width - box_w) // 2, 0)
            for i in range(len(lines) + 2):
                screen.text(top + i, left, " " * box_w)
            draw_box(screen, top, left, len(lines) + 2, box_w, None, Color.YELLOW)
            for i, line in enumerate(lines):
                screen.text(top + 1 + i, left + (box_w - len(line)) // 2, line[:box_w - 2], Color.YELLOW, bold=True)
            return
        p = s["players"][s["current"]]
        banner = "~ YOUR TURN ~" if p["id"] == self.session.my_id else f"~ {p['name']}'s turn ~"
        if s.get("final_round"):
            banner += "   FINAL ROUND"
        screen.text(0, x0 + (width - len(banner)) // 2, banner[:width], name_color(p["name"]), bold=True)
        if not self.tray.dice and s["turn"]["rolls"] == 0:
            hint = "Press R to roll!" if self.my_turn else "Shaking the cup..."
            screen.text(height // 2, x0 + (width - len(hint)) // 2, hint, dim=not self.my_turn)

    def draw_status(self, screen, y, width):
        s = self.shown
        if s is None or s["phase"] == "over":
            return
        t = s["turn"]
        brains = len(t["brains"]) + t["recycled"]
        segs = [(f"Brains this turn: {brains} ", Color.WHITE, True)]
        segs += [("B", DIE_COLOR[c], True) for c in t["brains"]]
        segs += [("B", Color.WHITE, False)] * t["recycled"]
        segs += [(f"   Shotguns: {len(t['shotguns'])}/{MAX_SHOTGUNS} ", Color.WHITE, True)]
        segs += [("X", DIE_COLOR[c], True) for c in t["shotguns"]]
        draw_segments(screen, y, 1, segs, width)
        segs = [("Footsteps to reroll: ", Color.DEFAULT, False)]
        segs += [("F", DIE_COLOR[c], True) for c in t["feet"]] or [("-", Color.DEFAULT, False)]
        segs += [("   Cup: ", Color.DEFAULT, False)]
        for c in (GREEN, YELLOW, RED):
            segs.append((f"{t['cup'][c]} {c}  ", DIE_COLOR[c], False))
        draw_segments(screen, y + 1, 1, segs, width)

    def draw_scoreboard(self, screen, top, left, height, width):
        draw_box(screen, top, left, height, width, "Scoreboard", Color.GREEN)
        s = self.shown
        if s is None:
            return
        y = top + 1
        inner = width - 4
        players = s["players"]
        avail = height - 2
        legend_h = 8
        show_legend = avail - 2 * len(players) >= legend_h
        # Drop the progress bars before dropping players when space is tight.
        row_h = 2 if avail - (legend_h if show_legend else 0) >= 2 * len(players) else 1
        for i, p in enumerate(players):
            if y >= top + height - 1:
                break
            current = s["phase"] == "playing" and i == s["current"]
            winner = s["phase"] == "over" and i in s["winners"]
            mark = ">" if current else ("*" if winner else " ")
            me = p["id"] == self.session.my_id
            name = p["name"] + (" (you)" if me else "")
            screen.text(y, left + 1, mark, Color.YELLOW, bold=True)
            screen.text(y, left + 2, f"{name[:inner - 4]:<{inner - 4}}", name_color(p["name"]), bold=me or current)
            screen.text(y, left + width - 5, f"{p['score']:>3}", Color.WHITE, bold=True)
            if row_h == 2:
                filled = min(p["score"], WINNING_SCORE)
                tag = " left" if not p["connected"] else (" bot" if p["bot"] else "")
                screen.text(y + 1, left + 3, "#" * filled, Color.GREEN if filled < WINNING_SCORE else Color.RED)
                screen.text(y + 1, left + 3 + filled, "." * (WINNING_SCORE - filled), dim=True)
                screen.text(y + 1, left + 4 + WINNING_SCORE, tag, dim=True)
            y += row_h
        if not show_legend:
            return
        y = top + height - legend_h
        screen.text(y, left + 2, f"First to {WINNING_SCORE} brains", Color.WHITE, bold=True)
        screen.text(y + 1, left + 2, "Dice: B=brain F=feet X=shot", dim=True)
        for j, c in enumerate((GREEN, YELLOW, RED)):
            faces = "".join(FACE_CHAR[f] for f in FACES[c])
            screen.text(y + 2 + j, left + 2, f"{c:<7}{faces}", DIE_COLOR[c])
        screen.text(y + 6, left + 2, "R roll  S stop  T talk"[:width - 3], dim=True)


class App:
    def __init__(self, name):
        from .graphics import TitleLogo
        self.name = name
        self.host_port = DEFAULT_PORT
        self.join_port = DEFAULT_PORT
        self.join_addr = "127.0.0.1"
        self.sp_players = 6  # you + 5 bots
        self.mp_players = 4
        self.mp_bots = True
        self.logo = TitleLogo()
        self.flash = ""
        self.running = True
        self.view = MenuView(self)

    def frame(self, screen, dt, keys):
        display = {Key.F2: self.cycle_glyphs, Key.F3: self.cycle_color, Key.F4: self.cycle_fps}
        view_keys = []
        for k in self.translate_mouse(keys):
            if isinstance(k, int) and k in display:
                display[k](screen)
            else:
                view_keys.append(k)
        self.view.tick(dt)
        rows, cols = screen.size()
        if rows < MIN_ROWS or cols < MIN_COLS:
            screen.erase()
            screen.text(0, 0, f"Please enlarge the terminal to at least {MIN_COLS}x{MIN_ROWS} (now {cols}x{rows}).")
        else:
            self.view.frame(ViewArea(screen), dt, view_keys)
        self.draw_status_line(screen)
        screen.refresh()
        return self.running

    # F2/F3/F4 work on every screen, since function keys can't clash with typing a name or a chat line.
    @staticmethod
    def cycle_glyphs(screen):
        screen.set_glyphs(cycle(screen.glyph_modes, screen.mode))

    @staticmethod
    def cycle_color(screen):
        screen.set_color(cycle(COLOR_MODES, screen.color_mode))

    @staticmethod
    def cycle_fps(screen):
        screen.fps = cycle(FPS_STEPS, screen.fps)

    def draw_status_line(self, screen):
        """The bottom row: glyphs, colours and frame rate (achieved/target), each clickable to change it.

        Every field is as wide as its longest value, so nothing moves as the values change.
        """
        rows, cols = screen.size()
        measured = "--" if screen.measured_fps is None else f"{min(screen.measured_fps, 999):.0f}"
        fields = (("F2", screen.mode, STATUS_WIDTHS[0], self.cycle_glyphs),
                  ("F3", screen.color_mode, STATUS_WIDTHS[1], self.cycle_color),
                  ("F4", f"{measured}/{screen.fps}fps", STATUS_WIDTHS[2], self.cycle_fps))
        x = max(cols - STATUS_WIDTH - 1, 0)
        y = rows - 1
        screen.text(y, 0, " " * cols)
        for key, value, width, action in fields:
            screen.text(y, x, key, dim=True)
            screen.text(y, x + 3, f"{value:<{width}}", dim=True)
            self.view.hits.append((y, x, x + 3 + width, lambda action=action: action(screen)))
            x += 3 + width + 2

    @staticmethod
    def translate_mouse(keys):
        out = []
        for k in keys:
            if isinstance(k, MouseEvent):
                if k.button == MouseEvent.LEFT and k.pressed:
                    out.append(Click(k.y, k.x))
            else:
                out.append(k)
        return out

    def close(self):
        session = getattr(self.view, "session", None)
        if session:
            session.close()
