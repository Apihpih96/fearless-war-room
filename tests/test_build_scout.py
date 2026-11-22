"""Tests for the opponent scout. Uses a tiny synthetic draft cache, so it runs
without the licensed GRID data:  python -m unittest discover tests"""
import csv
import importlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

# Standard pro draft order: (team slot 0 = first pick team, action)
ORDER = [(0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"),
         (0, "pick"), (1, "pick"), (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick"),
         (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"),
         (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick")]
A, B = ("1", "Alpha"), ("2", "Bravo")


def game(series, n, fp_team, fp_side, winner, a_picks, b_picks, a_bans, b_bans, burned):
    """fp_team picks first; fp_side is its side (2026 First Selection allows red)."""
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
                     "event": "LCS - Split 1 2026", "stage": "Regular", "date": f"Sat 2026-02-0{n} 7:00 AM (UTC+08:00)",
                     "seq": seq, "action": act, "team_id": t[0], "team_name": t[1], "side": sides[t[0]],
                     "opponent_id": o[0], "opponent_name": o[1], "champion": champ, "champion_id": champ.lower(),
                     "won_game": int(t[0] == winner)})
    blue = A if sides[A[0]] == "blue" else B
    red = B if blue == A else A
    grow = {"series_id": series, "game_id": gid, "game_number": n, "patch": "26.1", "event": "LCS - Split 1 2026",
            "stage": "Regular", "date": rows[0]["date"], "format": "best-of-3",
            "blue_id": blue[0], "blue_name": blue[1], "red_id": red[0], "red_name": red[1], "winner_id": winner,
            "blue_picks": "|".join(a_picks if blue == A else b_picks), "red_picks": "|".join(b_picks if blue == A else a_picks),
            "blue_bans": "|".join(a_bans if blue == A else b_bans), "red_bans": "|".join(b_bans if blue == A else a_bans),
            "burned_before": "|".join(burned)}
    return rows, grow


def champs(prefix, k=5):
    return [f"{prefix}{i}" for i in range(k)]


class ScoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        drafts, games = [], []
        # Three Bo3s. Alpha always first-picks "Azir" in G1 (on RED side once, to test First Selection).
        for s, side in (("s1", "blue"), ("s2", "red"), ("s3", "blue")):
            a1, b1 = ["Azir"] + champs(f"{s}a", 4), champs(f"{s}b")
            d, g = game(s, 1, A, side, "1", a1, b1, ["Vi"] + champs(f"{s}x", 4), champs(f"{s}y"), [])
            drafts += d; games.append(g)
            a2, b2 = ["Lulu"] + champs(f"{s}c", 4), champs(f"{s}d")
            d, g = game(s, 2, B, "blue", "2", a2, b2, ["Vi"] + champs(f"{s}z", 4), champs(f"{s}w"), a1 + b1)
            drafts += d; games.append(g)
            a3, b3 = ["Lulu2"] + champs(f"{s}e", 4), champs(f"{s}f")
            d, g = game(s, 3, A, "blue", "1", a3, b3, champs(f"{s}q"), champs(f"{s}r"), a1 + b1 + a2 + b2)
            drafts += d; games.append(g)
        for name, rows in (("drafts.csv", drafts), ("games.csv", games)):
            with open(tmp / name, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        os.environ["FWR_CACHE_DIR"] = str(tmp)
        os.environ["FWR_OUT_DIR"] = str(tmp / "out")
        os.environ["STL_DATA_DIR"] = str(tmp / "no-grid")  # no rosters: exercise the fallback
        import build_scout
        cls.bs = importlib.reload(build_scout)
        sys.argv = ["build_scout.py", "--min-games", "1"]
        cls.bs.main()
        cls.out = tmp / "out"
        cls.alpha = json.load(open(cls.out / "teams" / "1.json"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_index_lists_both_teams(self):
        ix = json.load(open(self.out / "index.json"))
        self.assertEqual({t["id"] for t in ix["teams"]}, {"1", "2"})
        self.assertTrue(all(t["lcs_2026"] for t in ix["teams"]))

    def test_sample_and_buckets(self):
        s = self.alpha["sample"]
        self.assertEqual((s["series"], s["games"], s["wins"]), (3, 9, 6))
        self.assertEqual(s["by_bucket"]["G1"], {"games": 3, "wins": 3, "win_rate": 1.0})
        self.assertEqual(s["by_bucket"]["G2"]["wins"], 0)

    def test_first_pick_from_draft_order_not_side(self):
        s = self.alpha["sample"]
        self.assertEqual(s["first_pick_rate"]["label"], "6/9")   # G1 + G3 of each series
        self.assertEqual(s["blue_side_rate"]["label"], "5/9")    # s2 G1 was red-side first pick
        azir = next(c for c in self.alpha["champions"] if c["champion"] == "Azir")
        self.assertEqual(azir["first_picks"]["label"], "3/6")
        self.assertEqual(azir["by_bucket"]["G1"]["picks"]["label"], "3/3")

    def test_bans_and_presence(self):
        vi = next(c for c in self.alpha["champions"] if c["champion"] == "Vi")
        self.assertEqual(vi["bans"]["label"], "6/9")
        self.assertEqual(self.alpha["champions"][0]["champion"], "Vi")  # most present
        self.assertEqual(self.alpha["top"]["first_bans"][0]["champion"], "Vi")

    def test_fearless_shift(self):
        f = self.alpha["fearless"]
        self.assertEqual(f["by_bucket"]["G1"]["new_vs_g1_pool"]["n"], 0)
        self.assertEqual(f["by_bucket"]["G3+"]["new_vs_g1_pool"]["label"], "15/15")
        az = next(x for x in f["when_favorites_locked"] if x["champion"] == "Azir")
        self.assertEqual(az["locked_games"], 6)          # burned in every G2 and G3
        self.assertEqual(az["replacements"][0]["champion"], "Lulu")

    def test_insights_answer_both_questions_with_evidence(self):
        ins = self.alpha["insights"]
        self.assertTrue(3 <= len(ins) <= 5)
        qs = {i["question"] for i in ins}
        self.assertTrue(any("repeat" in q for q in qs) and any("Fearless" in q for q in qs))
        self.assertTrue(all(i["evidence"] and i["text"] for i in ins))

    def test_no_per_game_rows_leak(self):
        """License rule: output holds aggregates only, never game or series ids."""
        blob = "".join(p.read_text() for p in self.out.rglob("*.json"))
        for gid in ("s1-1", "s2-3", "game_id", "series_id"):
            self.assertNotIn(gid, blob)


if __name__ == "__main__":
    unittest.main()
