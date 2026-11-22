"""Tests for the win-probability model. Uses synthetic data so it runs
without the licensed GRID data:  python -m unittest discover tests"""
import csv
import importlib
import json
import math
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

# Standard pro draft order
ORDER = [(0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"),
         (0, "pick"), (1, "pick"), (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick"),
         (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"),
         (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick")]
A, B = ("1", "Alpha"), ("2", "Bravo")


def game(series, n, fp_team, fp_side, winner, a_picks, b_picks, a_bans, b_bans, burned):
    """fp_team picks first; fp_side is its side."""
    other = B if fp_team == A else A
    sides = {fp_team[0]: fp_side, other[0]: "red" if fp_side == "blue" else "blue"}
    picks = {A[0]: list(a_picks), B[0]: list(b_picks)}
    bans = {A[0]: list(a_bans), B[0]: list(b_bans)}
    gid = f"{series}-{n}"
    rows = []
    for seq, (slot, act) in enumerate(ORDER, 1):
        t = fp_team if slot == 0 else other
        o = other if slot == 0 else fp_team
        champ = (picks if act == "pick" else bans)[t[0]].pop(0)
        rows.append({"series_id": series, "game_id": gid, "game_number": n, "patch": "26.1",
                     "event": "LCS - Split 1 2026", "stage": "Regular",
                     "date": f"Sat 2026-02-0{n} 7:00 AM (UTC+08:00)",
                     "seq": seq, "action": act, "team_id": t[0], "team_name": t[1],
                     "side": sides[t[0]], "opponent_id": o[0], "opponent_name": o[1],
                     "champion": champ, "champion_id": champ.lower(),
                     "won_game": int(t[0] == winner)})
    blue = A if sides[A[0]] == "blue" else B
    red = B if blue == A else A
    grow = {"series_id": series, "game_id": gid, "game_number": n, "patch": "26.1",
            "event": "LCS - Split 1 2026", "stage": "Regular", "date": rows[0]["date"],
            "format": "best-of-3",
            "blue_id": blue[0], "blue_name": blue[1], "red_id": red[0], "red_name": red[1],
            "winner_id": winner,
            "blue_picks": "|".join(a_picks if blue == A else b_picks),
            "red_picks": "|".join(b_picks if blue == A else a_picks),
            "blue_bans": "|".join(a_bans if blue == A else b_bans),
            "red_bans": "|".join(b_bans if blue == A else a_bans),
            "burned_before": "|".join(burned)}
    return rows, grow


def champs(prefix, k=5):
    return [f"{prefix}{i}" for i in range(k)]


class BuildModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        drafts, games = [], []

        # Create multiple series with a dominant champion "GodChamp" always winning
        # Alpha always wins when they pick GodChamp
        for s_idx in range(6):
            s = f"series{s_idx}"
            for n in range(1, 4):
                date_day = min(28, s_idx * 3 + n)
                # Alpha picks GodChamp + 4 others, Bravo picks 5 random champs
                a_picks = ["GodChamp"] + champs(f"{s}a", 4)
                b_picks = champs(f"{s}b")
                a_bans = champs(f"{s}x", 5)
                b_bans = champs(f"{s}y", 5)
                winner = A[0]  # Alpha always wins
                burned = []
                d, g = game(s, n, A, "blue", winner, a_picks, b_picks, a_bans, b_bans, burned)
                drafts += d
                games.append(g)

        for name, rows in (("drafts.csv", drafts), ("games.csv", games)):
            with open(tmp / name, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)

        os.environ["FWR_CACHE_DIR"] = str(tmp)
        os.environ["FWR_OUT_DIR"] = str(tmp / "out")
        os.environ["STL_DATA_DIR"] = str(tmp / "no-grid")

        import build_model
        cls.bm = importlib.reload(build_model)
        cls.bm.main()
        cls.out = tmp / "out"
        cls.model = json.load(open(cls.out / "model.json"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_strong_champion_positive_strength(self):
        """GodChamp wins every game -> positive strength after shrinkage."""
        gc = self.model["champions"].get("GodChamp")
        self.assertIsNotNone(gc, "GodChamp should be in champion list")
        self.assertGreater(gc["strength"], 0, "GodChamp should have positive strength")
        self.assertEqual(gc["wins"], gc["games"], "GodChamp should win all its games")

    def test_elo_moves_winner_up(self):
        """Alpha wins every game -> Elo should be well above 1500."""
        alpha = self.model["teams"].get("1")
        self.assertIsNotNone(alpha, "Alpha should be in teams")
        self.assertGreater(alpha["rating"], 1500,
                           "Alpha's Elo should increase after winning all games")
        bravo = self.model["teams"].get("2")
        self.assertIsNotNone(bravo, "Bravo should be in teams")
        self.assertLess(bravo["rating"], 1500,
                        "Bravo's Elo should decrease after losing all games")

    def test_coefficients_finite(self):
        """All logistic regression coefficients should be finite numbers."""
        coef = self.model["coef"]
        self.assertIn("elo", coef)
        self.assertIn("draft", coef)
        self.assertIn("blue", coef)
        self.assertIn("first_pick", coef)
        for name, val in coef.items():
            self.assertTrue(math.isfinite(val), f"Coefficient {name} should be finite, got {val}")

    def test_no_per_game_rows(self):
        """License rule: output holds aggregates only, never game or series ids."""
        blob = "".join(p.read_text() for p in self.out.rglob("*.json"))
        for gid in ("series0-1", "series5-3", "game_id", "series_id"):
            self.assertNotIn(gid, blob, f"Per-game identifier '{gid}' leaked into output")

    def test_cv_runs(self):
        """Cross-validation metrics should be present and reasonable."""
        m = self.model["metrics"]
        self.assertIn("games", m)
        self.assertIn("log_loss", m)
        self.assertIn("accuracy", m)
        self.assertIn("baseline_log_loss", m)
        self.assertGreater(m["games"], 0, "CV should evaluate at least one game")
        self.assertTrue(0 <= m["accuracy"] <= 1, "Accuracy should be in [0, 1]")
        self.assertGreater(m["log_loss"], 0, "Log loss should be positive")
        self.assertGreater(m["baseline_log_loss"], 0, "Baseline log loss should be positive")

    def test_meta_fields(self):
        """Meta should contain generated timestamp, patches, events count."""
        meta = self.model["meta"]
        self.assertIn("generated", meta)
        self.assertIn("T", meta["generated"])  # ISO 8601
        self.assertIsInstance(meta["patches"], list)
        self.assertIsInstance(meta["events"], int)


if __name__ == "__main__":
    unittest.main()
