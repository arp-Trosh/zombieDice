"""Game sessions.

HostSession owns the rules and is used both for single player (no server) and
for hosting; ClientSession mirrors a remote host. The UI talks to either one
through the same interface:

    states   deque of state snapshots (dicts), to be consumed in order
    history  list of chat/log lines: {"name": str|None, "text": str, "kind": ...}
    my_id    this player's id (None until a client is welcomed)
    error    set when the session has failed (e.g. lost connection)
    poll()   process network traffic and computer players; call every frame
    act("roll" | "stop"), chat(text), close()
"""
import queue
import random
import time
from collections import deque

from . import bots
from .net import Client, Server
from .rules import GREEN, RED, YELLOW, Game, Player

PROTOCOL = 1
MAX_PLAYERS = 8
MAX_NAME = 16
MAX_CHAT = 200
ROLL_DELAY = 2.8   # seconds after a roll before a bot acts, so everyone sees the dice land
THINK_DELAY = 1.0  # seconds before a bot starts its turn or after it stops
HISTORY_SENT_ON_JOIN = 50


def clean_text(text, limit):
    return "".join(ch for ch in str(text or "") if ch.isprintable())[:limit].strip()


class SessionBase:
    is_host = False
    server = None
    speed = 1.0

    def __init__(self):
        self.states = deque()
        self.history = []
        self.error = None
        self.my_id = None

    def log(self, text, color=None):
        """Add a local-only line to the chat window (game events, hints)."""
        self.history.append({"name": None, "text": text, "kind": "log", "color": color})


class HostSession(SessionBase):
    is_host = True

    def __init__(self, name, server=None, rng=None, delays=(ROLL_DELAY, THINK_DELAY), max_players=MAX_PLAYERS,
                 allow_bots=True):
        super().__init__()
        self.allow_bots = allow_bots  # bots fill empty seats and take over players who leave
        self.max_players = max(2, min(MAX_PLAYERS, max_players))  # seats at the table
        self.rng = rng or random.Random()
        self.server = server
        self.roll_delay, self.think_delay = delays
        self.players = [Player(0, clean_text(name, MAX_NAME) or "Player")]
        self.my_id = 0
        self._next_id = 1
        self.conn_players = {}  # connection id -> player id
        self.risk = {}          # bot player id -> risk appetite
        self.game = None
        self.game_id = 0
        self.event = None
        self._event_id = 0
        self._quips = []        # (due time, name, text)
        self._next_bot_time = 0.0
        self.publish()

    # ----- queries -----------------------------------------------------------------

    @property
    def port(self):
        return self.server.port if self.server else None

    @property
    def phase(self):
        if self.game is None:
            return "lobby"
        return "over" if self.game.over else "playing"

    def player(self, pid):
        return next((p for p in self.players if p.id == pid), None)

    def snapshot(self):
        g = self.game
        s = {
            "phase": self.phase,
            "game_id": self.game_id,
            "port": self.port,
            "max_players": self.max_players,
            "bots": self.allow_bots,
            "players": [{"id": p.id, "name": p.name, "score": p.score, "bot": p.bot, "connected": p.connected}
                        for p in self.players],
            "event": self.event,
        }
        if g:
            t = g.turn
            s.update(
                current=g.current,
                final_round=g.final_round,
                triggered_by=g.triggered_by,
                winners=g.winners() if g.over else [],
                turn={
                    "brains": list(t.brains), "recycled": t.recycled_brains, "shotguns": list(t.shotguns),
                    "feet": list(t.feet), "rolls": t.rolls,
                    "cup": {c: t.cup.count(c) for c in (GREEN, YELLOW, RED)},
                },
            )
        return s

    # ----- lobby -------------------------------------------------------------------

    def add_bot(self):
        if self.phase != "lobby" or not self.allow_bots or len(self.players) >= self.max_players:
            return
        taken = {p.name for p in self.players}
        name = (bots.pick_names(1, self.rng, taken) or [f"Zombie #{self._next_id}"])[0]
        p = Player(self._new_id(), name, bot=True)
        self.risk[p.id] = bots.random_risk(self.rng)
        self.players.append(p)
        self.system(f"{name} shambles in.")
        self.publish()

    def remove_bot(self):
        if self.phase != "lobby":
            return
        for p in reversed(self.players):
            if p.bot:
                self.players.remove(p)
                self.system(f"{p.name} wanders off.")
                self.publish()
                return

    def set_max_players(self, n):
        """Change the number of seats; bots leave first, and humans already seated are never dropped."""
        if self.phase != "lobby":
            return
        humans = sum(not p.bot for p in self.players)
        n = max(2, humans, min(MAX_PLAYERS, n))
        while len(self.players) > n and any(p.bot for p in self.players):
            self.remove_bot()
        if n != self.max_players:
            self.max_players = n
            self.system(f"The table is set for {n} players.")
            self.publish()

    def set_allow_bots(self, allow):
        if self.phase != "lobby" or allow == self.allow_bots:
            return
        self.allow_bots = allow
        while any(p.bot for p in self.players):
            self.remove_bot()
        self.system("Bots will fill the empty seats." if allow else "No bots: humans only.")
        self.publish()

    def fill_seats(self):
        """Seat bots in every empty chair."""
        while self.phase == "lobby" and self.allow_bots and len(self.players) < self.max_players:
            self.add_bot()

    def start_game(self):
        """Start (or restart) a game with everyone currently seated."""
        if self.phase == "playing":
            return
        seated = [p for p in self.players if p.connected or p.bot]  # drop players who left with no bot
        if len(seated) < 2:
            if self.phase == "over":
                self.system("Need at least two players to start.")
            return
        self.players = seated
        for p in self.players:
            p.score = 0
        self.game = Game(self.players, self.rng, first=self.rng.randrange(len(self.players)))
        self.game_id += 1
        self._set_event("start")
        self._next_bot_time = time.monotonic() + self.think_delay / self.speed
        self.publish()

    # ----- actions -----------------------------------------------------------------

    def act(self, action):
        self._act(self.my_id, action)

    def chat(self, text):
        text = clean_text(text, MAX_CHAT)
        if text:
            self._line({"name": self.player(self.my_id).name, "text": text, "kind": "chat"})

    def system(self, text):
        self._line({"name": None, "text": text, "kind": "system"})

    def poll(self):
        now = time.monotonic()
        if self.server:
            self._poll_network()
        due = [q for q in self._quips if q[0] <= now]
        if due:
            self._quips = [q for q in self._quips if q[0] > now]
            for _, name, text in due:
                self._line({"name": name, "text": text, "kind": "chat"})
        g = self.game
        if g and not g.over and g.current_player.bot and now >= self._next_bot_time:
            p = g.current_player
            keep_going = bots.should_roll(g, self.risk.get(p.id, 0.35), self.rng)
            self._act(p.id, "roll" if keep_going else "stop")
        elif g and not g.over and not g.current_player.connected and now >= self._next_bot_time:
            g.skip_turn()  # a player who left with no bot to take over
            self._next_bot_time = now + self.think_delay / self.speed
            self.publish()

    def close(self):
        if self.server:
            self.server.close()
            self.server = None

    # ----- internals ---------------------------------------------------------------

    def _new_id(self):
        self._next_id += 1
        return self._next_id - 1

    def _set_event(self, kind, **data):
        self._event_id += 1
        self.event = {"id": self._event_id, "kind": kind, **data}

    def publish(self):
        s = self.snapshot()
        self.states.append(s)
        if self.server:
            self.server.broadcast({"t": "state", "state": s})

    def _line(self, line):
        self.history.append(line)
        if self.server:
            self.server.broadcast({"t": "chat", **line})

    def _quip(self, player, kind, delay, chance):
        if player.bot and player.connected and self.rng.random() < chance:
            self._quips.append((time.monotonic() + delay / self.speed, player.name, self.rng.choice(bots.QUIPS[kind])))

    def _act(self, pid, action):
        g = self.game
        if g is None or g.over or g.current_player.id != pid:
            return
        now = time.monotonic()
        idx, player, turn = g.current, g.current_player, g.turn
        if action == "roll":
            results, busted = g.roll()
            self._set_event("roll", player=idx, dice=results, busted=busted,
                            brains=turn.brain_count, shotguns=len(turn.shotguns))
            self._next_bot_time = now + self.roll_delay / self.speed
            if busted:
                self._quip(player, "bust", self.roll_delay * 0.6, 0.5)
                if not player.bot:
                    others = [p for p in self.players if p.bot and p.connected]
                    if others:
                        self._quip(self.rng.choice(others), "gloat", self.roll_delay * 0.7, 0.35)
        elif action == "stop" and g.can_stop:
            brains = g.stop()
            self._set_event("stop", player=idx, brains=brains, score=player.score)
            self._next_bot_time = now + self.think_delay / self.speed
            self._quip(player, "big_bank" if brains >= 6 else "bank", 0.3, 0.4)
        else:
            return
        if g.over:
            for i in g.winners():
                self._quip(self.players[i], "win", self.roll_delay, 1.0)
        self.publish()

    def _poll_network(self):
        while True:
            try:
                kind, cid, payload = self.server.inbox.get_nowait()
            except queue.Empty:
                return
            if kind == "msg":
                self._handle(cid, payload)
            elif kind == "disconnect":
                self._disconnect(cid)

    def _handle(self, cid, msg):
        t = msg.get("t")
        pid = self.conn_players.get(cid)
        if t == "hello" and pid is None:
            if self.phase != "lobby":
                return self._refuse(cid, "A game is already in progress on that host.")
            if len(self.players) >= self.max_players:
                return self._refuse(cid, "That game is full.")
            name = self._unique_name(clean_text(msg.get("name"), MAX_NAME) or "Zombie")
            p = Player(self._new_id(), name)
            self.players.append(p)
            self.conn_players[cid] = p.id
            self.server.send(cid, {"t": "welcome", "id": p.id})
            self.server.send(cid, {"t": "history", "lines": self.history[-HISTORY_SENT_ON_JOIN:]})
            self.system(f"{name} joined.")
            self.publish()
        elif pid is None:
            return
        elif t == "chat":
            text = clean_text(msg.get("text"), MAX_CHAT)
            if text:
                self._line({"name": self.player(pid).name, "text": text, "kind": "chat"})
        elif t == "act" and msg.get("action") in ("roll", "stop"):
            self._act(pid, msg["action"])

    def _refuse(self, cid, reason):
        self.server.send(cid, {"t": "error", "msg": reason})
        self.server.drop(cid)

    def _disconnect(self, cid):
        pid = self.conn_players.pop(cid, None)
        self.server.drop(cid)
        p = self.player(pid)
        if p is None:
            return
        if self.phase == "lobby":
            self.players.remove(p)
            self.system(f"{p.name} left.")
        elif self.allow_bots:
            p.connected, p.bot = False, True
            self.risk[p.id] = bots.random_risk(self.rng)
            self.system(f"{p.name} left; a bot is eating their brains now.")
        else:
            p.connected = False
            self.system(f"{p.name} left; their turns will be skipped.")
            self._next_bot_time = max(self._next_bot_time, time.monotonic() + self.think_delay)
        self.publish()

    def _unique_name(self, name):
        taken = {p.name for p in self.players}
        candidate, n = name, 2
        while candidate in taken:
            suffix = f" {n}"
            candidate = name[:MAX_NAME - len(suffix)] + suffix
            n += 1
        return candidate


def single_player_session(name, npcs=5, rng=None, **kwargs):
    session = HostSession(name, rng=rng, max_players=npcs + 1, **kwargs)
    session.fill_seats()
    session.history.clear()  # skip the lobby arrival messages
    session.start_game()
    return session


def host_session(name, port, **kwargs):
    return HostSession(name, server=Server(port), **kwargs)


class ClientSession(SessionBase):
    def __init__(self, name, host, port):
        super().__init__()
        self.address = f"{host}:{port}"
        self.client = Client(host, port)
        self.client.send({"t": "hello", "name": name, "v": PROTOCOL})

    def poll(self):
        while True:
            try:
                kind, _, msg = self.client.inbox.get_nowait()
            except queue.Empty:
                return
            if kind == "disconnect":
                self.error = self.error or "Lost connection to the host."
                continue
            t = msg.get("t")
            if t == "welcome":
                self.my_id = msg.get("id")
            elif t == "state" and isinstance(msg.get("state"), dict):
                self.states.append(msg["state"])
            elif t == "chat":
                self.history.append({"name": msg.get("name"), "text": str(msg.get("text", "")),
                                     "kind": msg.get("kind", "chat")})
            elif t == "history":
                self.history.extend(line for line in msg.get("lines", []) if isinstance(line, dict))
            elif t == "error":
                self.error = str(msg.get("msg", "The host refused the connection."))

    def act(self, action):
        self.client.send({"t": "act", "action": action})

    def chat(self, text):
        text = clean_text(text, MAX_CHAT)
        if text:
            self.client.send({"t": "chat", "text": text})

    def close(self):
        self.client.close()
