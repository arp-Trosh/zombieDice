import random
import time
import unittest

import numpy as np

from zombie import bots
from zombie.graphics import text_mesh
from zombie.rules import BRAIN, CUP, FACES, FEET, GREEN, RED, SHOTGUN, WINNING_SCORE, YELLOW, Game, Player
from zombie.session import ClientSession, HostSession, host_session, single_player_session

def players(n):
    return [Player(i, f"P{i}") for i in range(n)]

class RiggedRng(random.Random):
    """Random whose choice() returns faces from a script (draws still shuffle normally)."""

    def __init__(self, faces):
        super().__init__(0)
        self.faces = list(faces)

    def choice(self, seq):
        if self.faces and self.faces[0] in seq:
            return self.faces.pop(0)
        return super().choice(seq)

class RulesTests(unittest.TestCase):
    def test_dice_breakdown(self):
        self.assertEqual((CUP.count(GREEN), CUP.count(YELLOW), CUP.count(RED)), (6, 4, 3))
        for color, (b, s) in {GREEN: (3, 1), YELLOW: (2, 2), RED: (1, 3)}.items():
            self.assertEqual((FACES[color].count(BRAIN), FACES[color].count(SHOTGUN), FACES[color].count(FEET)),
                             (b, s, 2))

    def test_roll_sorts_dice_and_keeps_feet_in_hand(self):
        g = Game(players(2), RiggedRng([BRAIN, FEET, SHOTGUN]))
        results, busted = g.roll()
        self.assertFalse(busted)
        self.assertEqual([f for _, f in results], [BRAIN, FEET, SHOTGUN])
        self.assertEqual((g.turn.brain_count, len(g.turn.shotguns), len(g.turn.feet)), (1, 1, 1))
        self.assertEqual(len(g.turn.cup), 10)
        # The footstep die is rerolled plus two fresh draws.
        feet_color = g.turn.feet[0]
        results, _ = g.roll()
        self.assertEqual(results[0][0], feet_color)
        self.assertEqual(len(g.turn.cup), 8)

    def test_three_shotguns_bust_and_score_nothing(self):
        g = Game(players(2), RiggedRng([BRAIN, BRAIN, SHOTGUN, SHOTGUN, SHOTGUN, BRAIN]))
        g.roll()
        _, busted = g.roll()
        self.assertTrue(busted)
        self.assertEqual(g.players[0].score, 0)
        self.assertEqual(g.current, 1)
        self.assertEqual(g.turn.rolls, 0)

    def test_stop_banks_brains_and_passes_turn(self):
        g = Game(players(3), RiggedRng([BRAIN, BRAIN, FEET]))
        self.assertFalse(g.can_stop)
        g.roll()
        self.assertEqual(g.stop(), 2)
        self.assertEqual(g.players[0].score, 2)
        self.assertEqual(g.current, 1)

    def test_empty_cup_recycles_brains(self):
        g = Game(players(2), RiggedRng([BRAIN] * 15))
        for _ in range(5):
            g.roll()
        self.assertEqual(g.turn.brain_count, 15)
        self.assertEqual(g.turn.recycled_brains, 12)
        self.assertEqual(len(g.turn.cup) + len(g.turn.brains), 13 - 0)

    def test_final_round_gives_everyone_else_one_turn(self):
        ps = players(3)
        g = Game(ps, random.Random(1), first=1)
        ps[1].score = WINNING_SCORE - 1
        g.turn.brains = [GREEN, GREEN]
        g.turn.rolls = 1
        g.stop()                      # P1 reaches 14 and triggers the final round
        self.assertTrue(g.final_round)
        self.assertEqual(g.current, 2)
        g.turn.rolls = 1
        g.stop()                      # P2's last turn
        self.assertFalse(g.over)
        self.assertEqual(g.current, 0)
        g.turn.rolls = 1
        g.stop()                      # P0's last turn; P1 does not go again
        self.assertTrue(g.over)
        self.assertEqual(g.winners(), [1])

    def test_random_games_finish(self):
        for seed in range(20):
            rng = random.Random(seed)
            g = Game(players(4), rng)
            for _ in range(10000):
                if g.over:
                    break
                if g.turn.rolls and g.turn.brain_count >= 2:
                    g.stop()
                else:
                    g.roll()
            self.assertTrue(g.over)
            self.assertGreaterEqual(max(p.score for p in g.players), WINNING_SCORE)

class BotTests(unittest.TestCase):
    def test_bot_always_opens_with_a_roll(self):
        g = Game(players(2), random.Random(0))
        self.assertTrue(bots.should_roll(g, 0.3))

    def test_bot_stops_at_two_shotguns_with_brains_at_stake(self):
        g = Game(players(2), random.Random(0))
        g.turn.rolls, g.turn.brains, g.turn.shotguns = 2, [GREEN] * 4, [RED, YELLOW]
        g.turn.cup = [c for c in g.turn.cup][:7]
        self.assertFalse(bots.should_roll(g, 0.45, random.Random(1)))

    def test_bot_banks_a_win(self):
        g = Game(players(2), random.Random(0))
        g.players[0].score = 11
        g.turn.rolls, g.turn.brains = 1, [GREEN, GREEN]
        self.assertFalse(bots.should_roll(g, 0.45))

    def test_bot_keeps_rolling_when_behind_in_final_round(self):
        g = Game(players(2), random.Random(0))
        g.final_round = True
        g.players[1].score = 14
        g.players[0].score = 10
        g.turn.rolls, g.turn.brains, g.turn.shotguns = 1, [GREEN] * 3, [RED, RED]
        self.assertTrue(bots.should_roll(g, 0.2))

    def test_bust_probability_bounds(self):
        g = Game(players(2), random.Random(0))
        self.assertLess(bots.bust_probability(g.turn, random.Random(0)), 0.1)
        g.turn.shotguns = [RED, RED]
        g.turn.feet = [RED, RED, RED]
        self.assertGreater(bots.bust_probability(g.turn, random.Random(0)), 0.8)

def run_until(pred, sessions, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for s in sessions:
            s.poll()
        if pred():
            return True
        time.sleep(0.005)
    return False

class SessionTests(unittest.TestCase):
    def test_single_player_bots_finish_a_game(self):
        s = single_player_session("Me", rng=random.Random(3), delays=(0, 0))
        self.assertEqual(len(s.players), 6)
        self.assertEqual(len({p.name for p in s.players}), 6)
        g = s.game
        for _ in range(20000):
            if g.over:
                break
            if g.current_player.id == s.my_id:
                s.act("roll" if g.turn.rolls == 0 else "stop")
            s.poll()
        self.assertTrue(g.over)
        self.assertEqual(s.snapshot()["phase"], "over")

    def test_single_player_table_size(self):
        for n in (2, 4, 8):
            s = single_player_session("Me", npcs=n - 1, rng=random.Random(1), delays=(0, 0))
            self.assertEqual(len(s.players), n)
            self.assertEqual(sum(p.bot for p in s.players), n - 1)

    def test_seats_limit_and_fill(self):
        host = HostSession("Hosty", max_players=3, delays=(0, 0))
        for _ in range(5):
            host.add_bot()
        self.assertEqual(len(host.players), 3)
        host.set_max_players(2)
        self.assertEqual((host.max_players, len(host.players)), (2, 2))
        host.remove_bot()
        host.set_max_players(1)  # never fewer than two seats
        self.assertEqual(host.max_players, 2)
        host.set_max_players(5)
        host.fill_seats()
        host.start_game()
        self.assertEqual(len(host.game.players), 5)
        self.assertEqual(host.snapshot()["max_players"], 5)

    def test_no_bots(self):
        host = HostSession("Hosty", max_players=4, delays=(0, 0))
        host.add_bot()
        host.set_allow_bots(False)
        self.assertEqual(len(host.players), 1)  # existing bots leave
        host.add_bot()
        host.fill_seats()
        self.assertEqual(len(host.players), 1)
        host.start_game()
        self.assertIsNone(host.game)  # can't play alone
        self.assertFalse(host.snapshot()["bots"])

    def test_leaver_skipped_without_bots(self):
        host = host_session("Hosty", 0, rng=random.Random(5), delays=(0, 0), allow_bots=False)
        try:
            a = ClientSession("A", "127.0.0.1", host.port)
            b = ClientSession("B", "127.0.0.1", host.port)
            try:
                self.assertTrue(run_until(lambda: len(host.players) == 3, [host, a, b]))
                host.start_game()
                a.close()
                self.assertTrue(run_until(lambda: not host.players[1].connected, [host]))
                leaver = host.players[1]
                self.assertFalse(leaver.bot)
                g = host.game
                for _ in range(5000):
                    if g.over:
                        break
                    cur = g.current_player
                    if cur.id == host.my_id:
                        host.act("roll" if g.turn.rolls == 0 else "stop")
                    elif cur.id == leaver.id:
                        host.poll()
                    else:
                        before = host.event["id"]
                        b.act("roll" if g.turn.rolls == 0 else "stop")
                        self.assertTrue(run_until(lambda: host.event["id"] != before, [host, b]))
                self.assertTrue(g.over)
                self.assertEqual(leaver.score, 0)
                host.start_game()  # play again without the leaver
                self.assertEqual(len(host.players), 2)
            finally:
                a.close()
                b.close()
        finally:
            host.close()

    def test_join_refused_when_table_full(self):
        host = host_session("Hosty", 0, max_players=2, delays=(0, 0))
        try:
            first = ClientSession("First", "127.0.0.1", host.port)
            second = None
            try:
                self.assertTrue(run_until(lambda: len(host.players) == 2, [host, first]))
                second = ClientSession("Second", "127.0.0.1", host.port)
                self.assertTrue(run_until(lambda: second.error is not None, [host, first, second]))
                self.assertIn("full", second.error)
                host.set_max_players(1)  # can't unseat a human
                self.assertEqual(host.max_players, 2)
            finally:
                first.close()
                if second:
                    second.close()
        finally:
            host.close()

    def test_host_and_client_over_tcp(self):
        host = host_session("Hosty", 0, rng=random.Random(5), delays=(0, 0))
        try:
            client = ClientSession("Joiner", "127.0.0.1", host.port)
            try:
                self.assertTrue(run_until(lambda: client.my_id is not None and len(host.players) == 2, [host, client]))
                client.chat("hello there")
                self.assertTrue(run_until(lambda: any(l.get("text") == "hello there" for l in host.history),
                                          [host, client]))
                self.assertTrue(any(l.get("text") == "hello there" for l in client.history)
                                or run_until(lambda: any(l.get("text") == "hello there" for l in client.history),
                                             [host, client]))

                host.start_game()
                self.assertTrue(run_until(lambda: any(st["phase"] == "playing" for st in client.states), [host, client]))
                g = host.game
                # Only the current player may act.
                other = [p for p in host.players if p.id != g.current_player.id][0]
                rolls_before = g.turn.rolls
                if other.id == client.my_id:
                    client.act("roll")
                    run_until(lambda: False, [host, client], timeout=0.2)
                else:
                    host.act("roll")
                self.assertEqual(g.turn.rolls, rolls_before)

                # Play the game out from both ends.
                for _ in range(5000):
                    if g.over:
                        break
                    actor = host if g.current_player.id == host.my_id else client
                    before = host.event["id"]
                    actor.act("roll" if g.turn.rolls == 0 else "stop")
                    self.assertTrue(run_until(lambda: host.event["id"] != before, [host, client]))
                self.assertTrue(g.over)
                self.assertTrue(run_until(lambda: client.states and client.states[-1]["phase"] == "over",
                                          [host, client]))
            finally:
                client.close()
            self.assertTrue(run_until(lambda: len(host.conn_players) == 0, [host]))
        finally:
            host.close()

    def test_client_leaving_mid_game_becomes_bot(self):
        host = host_session("Hosty", 0, rng=random.Random(5), delays=(0, 0))
        try:
            client = ClientSession("Leaver", "127.0.0.1", host.port)
            run_until(lambda: len(host.players) == 2, [host, client])
            host.start_game()
            client.close()
            self.assertTrue(run_until(lambda: host.players[1].bot, [host]))
            self.assertFalse(host.players[1].connected)
        finally:
            host.close()

    def test_join_refused_while_playing(self):
        host = host_session("Hosty", 0, delays=(0, 0))
        try:
            host.add_bot()
            host.start_game()
            client = ClientSession("Late", "127.0.0.1", host.port)
            try:
                self.assertTrue(run_until(lambda: client.error is not None, [host, client]))
                self.assertIn("in progress", client.error)
            finally:
                client.close()
        finally:
            host.close()

class GraphicsTests(unittest.TestCase):
    def test_text_mesh_is_closed(self):
        # Every edge of a closed, consistently wound mesh is shared by exactly two triangles in opposite directions
        # -- except where merged runs create T-junctions, so just check the volume is right instead.
        mesh, width = text_mesh("I", depth=1.0)
        v = mesh.vertices[mesh.faces]
        volume = abs(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum()) / 6
        self.assertAlmostEqual(volume, 11.0)  # "I" has 11 pixels
        self.assertEqual(width, 3)

    def test_kept_tokens_fill_their_cells(self):
        from zombie.graphics import KeptDice, token_mesh

        class Screen:
            cell_pixels = (1, 2)

            def __init__(self):
                self.frames, self.labels = [], []

            def draw_frame(self, fb, y, x):
                self.frames.append(fb.alpha.copy())

            def text(self, y, x, s, *args, **kwargs):
                self.labels.append(s)

        for face in (BRAIN, SHOTGUN, FEET):
            radius = np.linalg.norm(token_mesh(face).vertices, axis=1).max()
            self.assertAlmostEqual(radius, 1.0)
        kept, screen = KeptDice(), Screen()
        dice = [(GREEN, BRAIN), (RED, SHOTGUN), (YELLOW, FEET)]
        self.assertEqual(kept.render(screen, 0, 0, 24, 14, dice), 3)
        self.assertEqual(screen.labels, ["Brain", "Shotgun", "Ran"])
        for alpha in screen.frames:
            self.assertGreater((alpha >= 0.25).mean(), 0.25)  # the token covers a good part of its cell
        kept.t = 5.0
        kept.render(screen, 0, 0, 24, 14, dice)  # cached frames must not be overwritten by later renders
        self.assertTrue(all((a > 0).any() for a in screen.frames))


class DisplaySettingsTests(unittest.TestCase):
    def app_frame(self, app, screen, keys=()):
        app.frame(screen, 1 / 30, list(keys))
        return "".join(screen.chars[-1])

    def test_cycle(self):
        from zombie.ui import FPS_STEPS, cycle
        self.assertEqual(cycle(FPS_STEPS, 30), 60)
        self.assertEqual(cycle(FPS_STEPS, 144), 30)
        self.assertEqual(cycle(FPS_STEPS, 45), 60)   # not listed: the next one up
        self.assertEqual(cycle(FPS_STEPS, 200), 30)

    def test_function_keys_cycle_the_display(self):
        from unicode3d.keys import Key
        from unicode3d.terminal import Screen
        from zombie.ui import App
        app, screen = App("Tester"), Screen(glyphs="quad", color="truecolor", size=(30, 100))
        self.assertTrue(self.app_frame(app, screen).endswith("F2 quad     F3 truecolor  F4 --/30fps   "))
        self.app_frame(app, screen, [Key.F2, Key.F3, Key.F4])
        self.assertEqual((screen.mode, screen.color_mode, screen.fps), ("sextant", "256", 60))
        screen.measured_fps = 41.0
        self.assertTrue(self.app_frame(app, screen).endswith("F2 sextant  F3 256        F4 41/60fps   "))

    def test_game_buttons_fit_narrow_terminals(self):
        from unicode3d.terminal import Screen
        from zombie.ui import App, GameView
        for cols, row in ((80, "[ R Roll ] [ S Stop ] [ F x1 ] [ Q Leave ]"),
                          (130, "[ Roll Dice (R) ] [ Stop & Eat Brains (S) ] [ Speed x1 (F) ] [ Leave (Q) ]")):
            app = App("Me")
            app.view = GameView(app, single_player_session("Me", rng=random.Random(3), delays=(0, 0)))
            screen = Screen(glyphs="quad", color="truecolor", size=(24, cols))
            app.frame(screen, 1 / 30, [])
            self.assertTrue(any(row in "".join(line) for line in screen.chars), cols)
            app.close()

    def test_status_line_stays_put(self):
        from unicode3d.keys import Key
        from unicode3d.terminal import Screen
        from zombie.ui import App
        app, screen = App("Tester"), Screen(glyphs="half", color="mono", size=(24, 80))
        screen.fps = 144
        starts = set()
        for glyphs in screen.glyph_modes:
            for color in ("truecolor", "16"):
                for measured in (None, 7.0, 143.6):
                    screen.set_glyphs(glyphs)
                    screen.set_color(color)
                    screen.measured_fps = measured
                    row = self.app_frame(app, screen)
                    starts.add(tuple(row.index(k) for k in ("F2", "F3", "F4")))
        self.assertEqual(len(starts), 1)
        # The menu's own bottom line moves up a row rather than being covered.
        self.assertIn("Up/Down + Enter, or click", "".join(screen.chars[-2]))

import numpy as np  # noqa: E402

if __name__ == "__main__":
    unittest.main()
