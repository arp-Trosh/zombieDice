"""Computer players: names, decision making and trash talk."""
import random

from .rules import FACES, HAND_SIZE, MAX_SHOTGUNS, SHOTGUN, WINNING_SCORE

NPC_NAMES = (
    "Rotten Ronnie", "Grave Dave", "Count Chompula", "Lady Gutsworth", "Sir Shambles",
    "Necro Nancy", "Brainy McBrainface", "Mortimer Munch", "Ghoulia Roberts", "Jawless Jim",
    "Moldy Mildred", "Cadaver Carl", "Decomposing Dwayne", "Zed Zeppelin", "Rigor Mortis Ray",
    "Auntie Entrails", "Limpy Lou", "Dr. Cranium", "Putrid Pete", "Earless Earl",
)

QUIPS = {
    "bust": (
        "Ow. My everything.", "Not the face! ...well, what's left of it.", "Who brings a shotgun to a brain party?",
        "I'll just pick up my arm and go.", "Rude.", "That's gonna leave a mark. Another one.",
    ),
    "bank": (
        "BRAAAAINS!", "Mmm, cerebellum.", "Delicious. Needs salt.", "Nom nom nom.",
        "I'll save these for later.", "Food coma incoming.",
    ),
    "big_bank": (
        "Now THAT'S a buffet!", "All you can eat, baby!", "I'm gonna need a bigger stomach.",
    ),
    "win": ("The horde is mine!", "GG. Good Ghouls.", "Winner winner, brain dinner!"),
    "gloat": ("Hehe. Headshot.", "Should've stopped, fleshbag... er, fellow zombie.", "Ouch! Anyway..."),
}


def pick_names(n, rng=random, taken=()):
    pool = [name for name in NPC_NAMES if name not in taken]
    rng.shuffle(pool)
    return pool[:n]


def random_risk(rng=random):
    """A bot's appetite for risk: the bust chance it will accept with nothing at stake."""
    return rng.uniform(0.22, 0.48)


def bust_probability(turn, rng=random, samples=400):
    """Monte Carlo estimate of busting on the next roll."""
    need = MAX_SHOTGUNS - len(turn.shotguns)
    draw = HAND_SIZE - len(turn.feet)
    pool = list(turn.cup)
    if len(pool) < draw:
        pool += turn.brains
    draw = min(draw, len(pool))
    busts = 0
    for _ in range(samples):
        hand = turn.feet + rng.sample(pool, draw)
        if sum(rng.choice(FACES[c]) == SHOTGUN for c in hand) >= need:
            busts += 1
    return busts / samples


def should_roll(game, risk, rng=random):
    """Decide whether the current (bot) player keeps rolling."""
    t = game.turn
    me = game.current_player
    if t.rolls == 0:
        return True
    total = me.score + t.brain_count
    if game.final_round:
        # Last chance: stopping only helps if it beats everyone.
        best_other = max(p.score for p in game.players if p is not me)
        return total <= best_other
    if total >= WINNING_SCORE:
        return False
    # The more brains at stake, the less risk worth taking.
    threshold = risk / (1.0 + t.brain_count / 5.0)
    return bust_probability(t, rng) < threshold
