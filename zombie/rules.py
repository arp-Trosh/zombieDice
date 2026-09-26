"""Zombie Dice rules, independent of any UI or networking."""
import random
from dataclasses import dataclass, field

GREEN, YELLOW, RED = "green", "yellow", "red"
BRAIN, SHOTGUN, FEET = "brain", "shotgun", "feet"

FACES = {
    GREEN: (BRAIN, BRAIN, BRAIN, FEET, FEET, SHOTGUN),
    YELLOW: (BRAIN, BRAIN, FEET, FEET, SHOTGUN, SHOTGUN),
    RED: (BRAIN, FEET, FEET, SHOTGUN, SHOTGUN, SHOTGUN),
}
CUP = (GREEN,) * 6 + (YELLOW,) * 4 + (RED,) * 3
HAND_SIZE = 3
MAX_SHOTGUNS = 3
WINNING_SCORE = 13


@dataclass
class Player:
    id: int
    name: str
    bot: bool = False
    score: int = 0
    connected: bool = True


@dataclass
class Turn:
    cup: list
    feet: list = field(default_factory=list)      # footstep dice kept in hand; rerolled if the player continues
    brains: list = field(default_factory=list)
    shotguns: list = field(default_factory=list)
    recycled_brains: int = 0  # brains already counted whose dice went back into an empty cup
    rolls: int = 0

    @property
    def brain_count(self):
        return len(self.brains) + self.recycled_brains


class Game:
    """One game of Zombie Dice. `players` are Player objects in turn order."""

    def __init__(self, players, rng=None, first=0):
        if not players:
            raise ValueError("need at least one player")
        self.players = players
        self.rng = rng or random.Random()
        self.current = first
        self.final_round = False
        self.triggered_by = None       # index of the player who reached 13 first
        self.final_turns_left = set()  # indices still owed a turn in the final round
        self.over = False
        self.turn = self._new_turn()

    @property
    def current_player(self):
        return self.players[self.current]

    @property
    def can_roll(self):
        return not self.over

    @property
    def can_stop(self):
        return not self.over and self.turn.rolls > 0

    def roll(self):
        """Refill the hand to three dice and roll them.

        Returns (results, busted) where results is a list of (color, face).
        On a bust the turn is over and play has moved on.
        """
        if self.over:
            raise RuntimeError("game is over")
        t = self.turn
        hand, t.feet = t.feet, []
        while len(hand) < HAND_SIZE:
            if not t.cup:
                # Out of dice: note the brains, and put their dice back in the cup.
                t.recycled_brains += len(t.brains)
                t.cup, t.brains = t.brains, []
                self.rng.shuffle(t.cup)
                if not t.cup:
                    break
            hand.append(t.cup.pop())
        results = [(color, self.rng.choice(FACES[color])) for color in hand]
        for color, face in results:
            {BRAIN: t.brains, SHOTGUN: t.shotguns, FEET: t.feet}[face].append(color)
        t.rolls += 1
        busted = len(t.shotguns) >= MAX_SHOTGUNS
        if busted:
            self._end_turn(0)
        return results, busted

    def stop(self):
        """Bank this turn's brains. Returns how many were scored."""
        if not self.can_stop:
            raise RuntimeError("can't stop before rolling")
        brains = self.turn.brain_count
        self._end_turn(brains)
        return brains

    def skip_turn(self):
        """Pass the current player's turn without scoring (e.g. they left the game)."""
        if not self.over:
            self._end_turn(0)

    def winners(self):
        best = max(p.score for p in self.players)
        return [i for i, p in enumerate(self.players) if p.score == best]

    def _new_turn(self):
        cup = list(CUP)
        self.rng.shuffle(cup)
        return Turn(cup)

    def _end_turn(self, brains):
        self.current_player.score += brains
        n = len(self.players)
        if self.final_round:
            self.final_turns_left.discard(self.current)
        elif self.current_player.score >= WINNING_SCORE:
            self.final_round = True
            self.triggered_by = self.current
            self.final_turns_left = set(range(n)) - {self.current}
        if self.final_round and not self.final_turns_left:
            self.over = True
            return
        self.current = (self.current + 1) % n
        if self.final_round:
            while self.current not in self.final_turns_left:
                self.current = (self.current + 1) % n
        self.turn = self._new_turn()
