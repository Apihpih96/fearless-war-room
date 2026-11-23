"""Tests for the reported roster self-scout (pipeline/build_roster.py).
Uses synthetic data in a temp directory — no GRID data needed.

Run: python -m unittest discover -s tests -v
"""
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


def make_rosters_csv(path, rows):
    fields = ["title", "series_id", "game_id", "game_number", "team_id", "team_name",
              "side", "player_id", "player_name", "character_id", "character_name",
              "participation_status", "session"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def make_games_csv(path, rows):
    fields = ["series_id", "game_id", "game_number", "patch", "event", "stage", "date",
              "format", "blue_id", "blue_name", "red_id", "red_name", "winner_id",
              "blue_picks", "red_picks", "blue_bans", "red_bans", "burned_before"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def make_drafts_csv(path, rows):
    fields = ["series_id", "game_id", "game_number", "patch", "event", "stage", "date",
              "seq", "action", "team_id", "team_name", "side", "opponent_id", "opponent_name",
              "champion", "champion_id", "won_game"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class BuildRosterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        cache = tmp / "cache"
        cache.mkdir()
        data_dir = tmp / "data"
        meta = data_dir / "meta"
        meta.mkdir(parents=True)
        out = tmp / "out"
        out.mkdir()

        # Create two players on different teams
        # Player A (id 100) on Team X, Player B (id 200) on Team Y
        # Player C (id 300) with whitespace in name "C "
        games = []
        rosters = []
        drafts = []

        # Game 1: Player A on Team X vs Team Y (Player B)
        g1_id = "g1"
        games.append({
            "series_id": "s1", "game_id": g1_id, "game_number": 1, "patch": "26.1",
            "event": "Test League", "stage": "Regular",
            "date": "2026-03-01T10:00:00Z", "format": "best-of-3",
            "blue_id": "1", "blue_name": "Team X", "red_id": "2", "red_name": "Team Y",
            "winner_id": "1",
            "blue_picks": "Achamp|Bchamp|Cchamp|Dchamp|Echamp",
            "red_picks": "Fchamp|Gchamp|Hchamp|Ichamp|Jchamp",
            "blue_bans": "Xchamp", "red_bans": "Ychamp",
            "burned_before": "",
        })
        rosters.append({
            "title": "lol", "series_id": "s1", "game_id": g1_id, "game_number": 1,
            "team_id": "1", "team_name": "Team X", "side": "blue",
            "player_id": "100", "player_name": "PlayerA",
            "character_id": "a1", "character_name": "Achamp",
            "participation_status": "active", "session": "1",
        })
        rosters.append({
            "title": "lol", "series_id": "s1", "game_id": g1_id, "game_number": 1,
            "team_id": "2", "team_name": "Team Y", "side": "red",
            "player_id": "200", "player_name": "PlayerB",
            "character_id": "f1", "character_name": "Fchamp",
            "participation_status": "active", "session": "1",
        })
        # Draft actions for g1
        for seq, (tid, action, champ) in enumerate([
            ("1", "ban", "Xchamp"), ("2", "ban", "Ychamp"),
            ("1", "pick", "Achamp"), ("2", "pick", "Fchamp"),
            ("2", "pick", "Gchamp"), ("1", "pick", "Bchamp"),
        ], 1):
            drafts.append({
                "series_id": "s1", "game_id": g1_id, "game_number": 1, "patch": "26.1",
                "event": "Test League", "stage": "Regular",
                "date": "2026-03-01T10:00:00Z", "seq": seq, "action": action,
                "team_id": tid, "team_name": "Team X" if tid == "1" else "Team Y",
                "side": "blue" if tid == "1" else "red",
                "opponent_id": "2" if tid == "1" else "1",
                "opponent_name": "Team Y" if tid == "1" else "Team X",
                "champion": champ, "champion_id": champ.lower(),
                "won_game": "1" if tid == "1" else "0",
            })

        # Game 2: same series, Player A's team won G1, burned champs
        g2_id = "g2"
        burned = "Achamp|Bchamp|Cchamp|Dchamp|Echamp|Fchamp|Gchamp|Hchamp|Ichamp|Jchamp"
        games.append({
            "series_id": "s1", "game_id": g2_id, "game_number": 2, "patch": "26.1",
            "event": "Test League", "stage": "Regular",
            "date": "2026-03-01T11:00:00Z", "format": "best-of-3",
            "blue_id": "2", "blue_name": "Team Y", "red_id": "1", "red_name": "Team X",
            "winner_id": "2",
            "blue_picks": "Kchamp|Lchamp|Mchamp|Nchamp|Ochamp",
            "red_picks": "Pchamp|Qchamp|Rchamp|Schamp|Tchamp",
            "blue_bans": "Uchamp", "red_bans": "Vchamp",
            "burned_before": burned,
        })
        rosters.append({
            "title": "lol", "series_id": "s1", "game_id": g2_id, "game_number": 2,
            "team_id": "1", "team_name": "Team X", "side": "red",
            "player_id": "100", "player_name": "PlayerA",
            "character_id": "p1", "character_name": "Pchamp",
            "participation_status": "active", "session": "1",
        })
        rosters.append({
            "title": "lol", "series_id": "s1", "game_id": g2_id, "game_number": 2,
            "team_id": "2", "team_name": "Team Y", "side": "blue",
            "player_id": "200", "player_name": "PlayerB",
            "character_id": "k1", "character_name": "Kchamp",
            "participation_status": "active", "session": "1",
        })

        # Game 3: Player C with whitespace in name "C " on Team Z
        g3_id = "g3"
        games.append({
            "series_id": "s2", "game_id": g3_id, "game_number": 1, "patch": "26.1",
            "event": "Test League", "stage": "Regular",
            "date": "2026-04-01T10:00:00Z", "format": "best-of-3",
            "blue_id": "3", "blue_name": "Team Z", "red_id": "4", "red_name": "Team W",
            "winner_id": "3",
            "blue_picks": "Cchamp1|Cchamp2|Cchamp3|Cchamp4|Cchamp5",
            "red_picks": "Wchamp1|Wchamp2|Wchamp3|Wchamp4|Wchamp5",
            "blue_bans": "Xchamp", "red_bans": "Ychamp",
            "burned_before": "",
        })
        rosters.append({
            "title": "lol", "series_id": "s2", "game_id": g3_id, "game_number": 1,
            "team_id": "3", "team_name": "Team Z", "side": "blue",
            "player_id": "300", "player_name": "C ",  # trailing whitespace
            "character_id": "c1", "character_name": "Cchamp1",
            "participation_status": "active", "session": "1",
        })

        # Game 4: Player A on a different team (tests multi-team)
        g4_id = "g4"
        games.append({
            "series_id": "s3", "game_id": g4_id, "game_number": 1, "patch": "26.1",
            "event": "Test League", "stage": "Regular",
            "date": "2026-05-01T10:00:00Z", "format": "best-of-3",
            "blue_id": "5", "blue_name": "Team New", "red_id": "6", "red_name": "Team Old",
            "winner_id": "5",
            "blue_picks": "Achamp|NewChamp|X1|X2|X3",
            "red_picks": "Y1|Y2|Y3|Y4|Y5",
            "blue_bans": "Z1", "red_bans": "Z2",
            "burned_before": "",
        })
        rosters.append({
            "title": "lol", "series_id": "s3", "game_id": g4_id, "game_number": 1,
            "team_id": "5", "team_name": "Team New", "side": "blue",
            "player_id": "100", "player_name": "PlayerA",
            "character_id": "a1", "character_name": "Achamp",
            "participation_status": "active", "session": "1",
        })

        # Write files
        make_games_csv(cache / "games.csv", games)
        make_drafts_csv(cache / "drafts.csv", drafts)
        make_rosters_csv(meta / "rosters.csv", rosters)

        # Players CSV
        with open(meta / "players.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title", "player_id", "name", "other_names", "latest_team_id",
                        "latest_team_name", "team_ids", "series_count", "first_seen", "last_seen"])
            w.writerow(["lol", "100", "PlayerA", "", "5", "Team New", "1; 5", "3",
                        "2026-03-01T10:00:00Z", "2026-05-01T10:00:00Z"])
            w.writerow(["lol", "200", "PlayerB", "", "2", "Team Y", "2", "1",
                        "2026-03-01T10:00:00Z", "2026-03-01T11:00:00Z"])
            w.writerow(["lol", "300", "C", "", "3", "Team Z", "3", "1",
                        "2026-04-01T10:00:00Z", "2026-04-01T10:00:00Z"])

        os.environ["FWR_CACHE_DIR"] = str(cache)
        os.environ["FWR_OUT_DIR"] = str(out)
        os.environ["STL_DATA_DIR"] = str(data_dir)

        # Import and reload
        import build_roster
        cls.br = importlib.reload(build_roster)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _build_pools(self, roster):
        """Helper: build player pools for a given roster config."""
        old_roster = self.br.ROSTER[:]
        self.br.ROSTER = roster
        valid_ids = self.br.load_cache_game_ids()
        games_csv = self.br.load_games_csv()
        drafts = self.br.load_drafts_for_games(valid_ids)
        pools = []
        for slot in roster:
            pools.append(self.br.build_player_pool(slot, valid_ids, games_csv, drafts))
        self.br.ROSTER = old_roster
        return pools

    def test_name_matching_with_whitespace(self):
        """Player name 'C ' with trailing whitespace should match 'C'."""
        roster = [{"role": "mid", "name": "C", "player_id": None}]
        pools = self._build_pools(roster)
        self.assertEqual(pools[0]["player_id"], "300")
        self.assertEqual(pools[0]["games"], 1)

    def test_name_matching_case_insensitive(self):
        """Name matching should be case-insensitive."""
        roster = [{"role": "mid", "name": "playera", "player_id": None}]
        pools = self._build_pools(roster)
        self.assertEqual(pools[0]["player_id"], "100")

    def test_dedupe_by_game_id_player_id(self):
        """If rosters.csv has duplicate rows for same (game_id, player_id), only count once."""
        # Our test data has no dupes, but the function should handle them
        roster = [{"role": "jungle", "name": "PlayerA", "player_id": "100"}]
        pools = self._build_pools(roster)
        # PlayerA has 3 games (g1, g2, g4)
        self.assertEqual(pools[0]["games"], 3)

    def test_player_on_two_teams_combined(self):
        """PlayerA plays for Team X and Team New; both should appear."""
        roster = [{"role": "jungle", "name": "PlayerA", "player_id": "100"}]
        pools = self._build_pools(roster)
        teams = pools[0]["teams"]
        self.assertIn("Team X", teams)
        self.assertIn("Team New", teams)

    def test_no_data_flag(self):
        """A player with no games should get status 'no_data'."""
        roster = [{"role": "top", "name": "UnknownPlayer", "player_id": None}]
        pools = self._build_pools(roster)
        self.assertEqual(pools[0]["status"], "no_data")
        self.assertEqual(pools[0]["games"], 0)
        self.assertEqual(pools[0]["top"], [])

    def test_thin_flag(self):
        """A player with <20 games should get status 'thin'."""
        # PlayerB has 2 games (< 20)
        roster = [{"role": "support", "name": "PlayerB", "player_id": "200"}]
        pools = self._build_pools(roster)
        self.assertEqual(pools[0]["status"], "thin")

    def test_win_record_from_team_perspective(self):
        """PlayerA's team won g1 and g4, lost g2 -> record 2-1."""
        roster = [{"role": "jungle", "name": "PlayerA", "player_id": "100"}]
        pools = self._build_pools(roster)
        # Achamp: played in g1 (won) and g4 (won) -> 2-0
        achamp = next(t for t in pools[0]["top"] if t["champion"] == "Achamp")
        self.assertEqual(achamp["record"], "2-0")
        # Pchamp: played in g2 (lost) -> 0-1
        pchamp = next(t for t in pools[0]["top"] if t["champion"] == "Pchamp")
        self.assertEqual(pchamp["record"], "0-1")

    def test_replacements_when_favorite_burned(self):
        """When PlayerA's favorite (Achamp) is burned in G2, they pick Pchamp."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        # PlayerA's favorite should be Achamp (2 picks)
        wfl = report["fearless"]["when_favorites_locked"]
        achamp_locked = next((w for w in wfl if w["champion"] == "Achamp"), None)
        self.assertIsNotNone(achamp_locked)
        self.assertEqual(achamp_locked["locked_games"], 1)  # g2 has Achamp burned
        # Replacement should be Pchamp
        self.assertTrue(any(r["champion"] == "Pchamp" for r in achamp_locked["replacements"]))

    def test_index_merge_idempotent(self):
        """Running merge_index twice should not duplicate entries."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)

        # First merge
        self.br.merge_index(report)
        index_path = self.br.OUT / "index.json"
        idx1 = json.load(open(index_path))
        c9_entries = [t for t in idx1["teams"] if t["id"] == "c9-2027"]
        self.assertEqual(len(c9_entries), 1)

        # Second merge
        self.br.merge_index(report)
        idx2 = json.load(open(index_path))
        c9_entries = [t for t in idx2["teams"] if t["id"] == "c9-2027"]
        self.assertEqual(len(c9_entries), 1)

    def test_no_game_id_or_series_id_in_output(self):
        """License check: output must not contain game_id or series_id values."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
            {"role": "support", "name": "PlayerB", "player_id": "200"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        blob = json.dumps(report)
        # Check that actual game/series ID values don't leak (as standalone values)
        # "G1" bucket keys and "g1_picks" field names are fine — they are structural
        import re
        # No standalone game_id or series_id keys
        self.assertNotIn('"game_id"', blob)
        self.assertNotIn('"series_id"', blob)
        # No raw UUID-style game ids or our synthetic ids as values
        for bad in ['"g1"', '"g2"', '"g3"', '"g4"', '"s1"', '"s2"', '"s3"']:
            self.assertNotIn(bad, blob, f"Leaked identifier: {bad}")

    def test_frog_no_data(self):
        """Frog should have no_data status (no LoL player found)."""
        roster = [{"role": "top", "name": "Frog", "player_id": None}]
        pools = self._build_pools(roster)
        self.assertEqual(pools[0]["status"], "no_data")
        self.assertEqual(pools[0]["games"], 0)

    def test_report_has_required_sections(self):
        """The report should have all required top-level sections."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
            {"role": "support", "name": "PlayerB", "player_id": "200"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        required = ["team", "sample", "champions", "top", "fearless", "players", "roster", "insights"]
        for section in required:
            self.assertIn(section, report, f"Missing section: {section}")

    def test_champion_entries_have_player_and_role(self):
        """Each champion entry should have player and role fields."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        for c in report["champions"]:
            self.assertIn("player", c)
            self.assertIn("role", c)

    def test_roster_flags_include_no_data_players(self):
        """Roster flags should mention players with no_data status."""
        roster = [
            {"role": "top", "name": "UnknownPlayer", "player_id": None},
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        flags = report["roster"]["flags"]
        self.assertTrue(any("UnknownPlayer" in f for f in flags))

    def test_by_bucket_stats(self):
        """by_bucket should have correct game counts."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        # PlayerA has g1 (G1), g2 (G2), g4 (G1) -> 2 G1, 1 G2, 0 G3+
        # But game_info dedupes by game_id, so 3 unique games
        by_bucket = report["sample"]["by_bucket"]
        self.assertEqual(by_bucket["G1"]["games"], 2)  # g1, g4
        self.assertEqual(by_bucket["G2"]["games"], 1)  # g2
        self.assertEqual(by_bucket["G3+"]["games"], 0)

    def test_champion_picks_denominator_is_player_games(self):
        """Champion picks.of must equal that player's own game count, not the union."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
            {"role": "support", "name": "PlayerB", "player_id": "200"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        # PlayerA has 3 games, PlayerB has 2 games
        # Achamp is played by PlayerA (2 picks in g1, g4)
        achamp = next((c for c in report["champions"] if c["champion"] == "Achamp"), None)
        self.assertIsNotNone(achamp)
        self.assertEqual(achamp["player"], "PlayerA")
        # Denominator should be PlayerA's game count (3), not union (3 unique games)
        self.assertEqual(achamp["picks"]["of"], 3)
        self.assertEqual(achamp["picks"]["n"], 2)
        # Fchamp is played by PlayerB (1 pick in g1)
        fchamp = next((c for c in report["champions"] if c["champion"] == "Fchamp"), None)
        self.assertIsNotNone(fchamp)
        self.assertEqual(fchamp["player"], "PlayerB")
        # Denominator should be PlayerB's game count (2)
        self.assertEqual(fchamp["picks"]["of"], 2)
        self.assertEqual(fchamp["picks"]["n"], 1)

    def test_champion_by_bucket_denominator_is_player_bucket_games(self):
        """by_bucket picks.of must equal that player's own bucket game count."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        # PlayerA: g1(G1), g2(G2), g4(G1) -> 2 G1 games, 1 G2 game
        # Achamp: picked in g1(G1) and g4(G1) -> 2 G1 picks
        achamp = next((c for c in report["champions"] if c["champion"] == "Achamp"), None)
        self.assertIsNotNone(achamp)
        # G1 denominator should be PlayerA's G1 game count (2)
        self.assertEqual(achamp["by_bucket"]["G1"]["picks"]["of"], 2)
        self.assertEqual(achamp["by_bucket"]["G1"]["picks"]["n"], 2)
        # Pchamp: picked in g2(G2) -> 1 G2 pick
        pchamp = next((c for c in report["champions"] if c["champion"] == "Pchamp"), None)
        self.assertIsNotNone(pchamp)
        # G2 denominator should be PlayerA's G2 game count (1)
        self.assertEqual(pchamp["by_bucket"]["G2"]["picks"]["of"], 1)
        self.assertEqual(pchamp["by_bucket"]["G2"]["picks"]["n"], 1)

    def test_sample_per_player_exists(self):
        """sample.per_player must be a dict with per-player game counts and by_bucket."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
            {"role": "support", "name": "PlayerB", "player_id": "200"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        per_player = report["sample"]["per_player"]
        self.assertIsInstance(per_player, dict)
        self.assertIn("PlayerA", per_player)
        self.assertIn("PlayerB", per_player)
        self.assertEqual(per_player["PlayerA"]["games"], 3)
        self.assertEqual(per_player["PlayerB"]["games"], 2)
        # by_bucket should exist
        self.assertIn("by_bucket", per_player["PlayerA"])
        self.assertEqual(per_player["PlayerA"]["by_bucket"]["G1"], 2)
        self.assertEqual(per_player["PlayerA"]["by_bucket"]["G2"], 1)
        self.assertEqual(per_player["PlayerA"]["by_bucket"]["G3+"], 0)

    def test_top_picks_denominator_is_player_bucket_games(self):
        """top.picks labels must use the player's own bucket game count."""
        roster = [
            {"role": "jungle", "name": "PlayerA", "player_id": "100"},
        ]
        pools = self._build_pools(roster)
        report = self.br.build_roster_report(pools)
        # PlayerA has 2 G1 games; Achamp is top G1 pick with 2 picks
        g1_tops = report["top"]["picks"]["G1"]
        achamp_top = next((t for t in g1_tops if t["champion"] == "Achamp"), None)
        self.assertIsNotNone(achamp_top)
        # Denominator should be PlayerA's G1 game count (2)
        self.assertEqual(achamp_top["of"], 2)
        self.assertEqual(achamp_top["label"], "2/2")


if __name__ == "__main__":
    unittest.main()
