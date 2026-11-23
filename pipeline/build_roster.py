"""
Fearless War Room – Step 5a: Reported roster self-scout.

Builds a scouting report for a mixed roster (e.g. Cloud9 2027 reported lineup)
from each player's own games in the GRID data, on whatever team they played for.

Writes web/public/data/teams/c9-2027.json (aggregates only) and merges an entry
into web/public/data/index.json so the web app can select the roster.

Usage:
    python pipeline/build_roster.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = pathlib.Path(os.environ.get("STL_DATA_DIR", ROOT.parent / "stl-hackathon-2026-grid-starter"))
CACHE = pathlib.Path(os.environ.get("FWR_CACHE_DIR", ROOT / "cache"))
OUT = pathlib.Path(os.environ.get("FWR_OUT_DIR", ROOT / "web" / "public" / "data"))

BUCKETS = ("G1", "G2", "G3+")
FAVORITES = 5
TOP = 8
THIN_THRESHOLD = 20


# ---------------------------------------------------------------- roster config
ROSTER = [
    {"role": "top", "name": "Frog", "player_id": None},
    {"role": "jungle", "name": "Blaber", "player_id": "24165"},
    {"role": "mid", "name": "Loki", "player_id": "21565"},
    {"role": "bot", "name": "Yeon", "player_id": "21655"},
    {"role": "support", "name": "CoreJJ", "player_id": "24153"},
]
ROSTER_LABEL = "Cloud9 2027 (reported roster)"
ROSTER_REPORTED_DATE = "2026-11-23"
ROSTER_NOTE = "Reported, not officially confirmed"
ROSTER_TEAM_ID = "c9-2027"


# ---------------------------------------------------------------- helpers
def bucket(game_number: int) -> str:
    return "G1" if game_number == 1 else "G2" if game_number == 2 else "G3+"


def rate(n: int, of: int) -> dict:
    return {"n": n, "of": of, "rate": round(n / of, 3) if of else None, "label": f"{n}/{of}"}


def wr(wins: int, games: int) -> float | None:
    return round(wins / games, 3) if games else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(100 * x)}%"


def day(s: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else ""


def split_pipe(s: str) -> list[str]:
    return [x for x in s.split("|") if x]


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def record(w: int, g: int) -> str:
    return f"{w}-{g - w}"


# ---------------------------------------------------------------- load
def load_cache_game_ids() -> set[str]:
    """Return set of game_ids present in cache/games.csv."""
    path = CACHE / "games.csv"
    if not path.exists():
        return set()
    return {r["game_id"] for r in csv.DictReader(open(path, encoding="utf-8"))}


def load_games_csv():
    """Return dict game_id -> row from cache/games.csv."""
    path = CACHE / "games.csv"
    if not path.exists():
        return {}
    return {r["game_id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def load_player_roster_rows(player_id: str, valid_game_ids: set[str]) -> list[dict]:
    """Load rosters.csv rows for a player, filtered to valid game_ids.
    Returns list of dicts with game_id, game_number, team_id, team_name, side,
    character_name, date, event, series_id."""
    path = DATA_DIR / "meta" / "rosters.csv"
    if not path.exists():
        return []
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["title"] != "lol":
            continue
        if r["player_id"] != player_id:
            continue
        if r["game_id"] not in valid_game_ids:
            continue
        if r["participation_status"] != "active":
            continue
        rows.append(r)
    # Dedupe by (game_id, player_id) – keep first
    seen = set()
    deduped = []
    for r in rows:
        key = (r["game_id"], r["player_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def load_drafts_for_games(game_ids: set[str]) -> dict:
    """Load drafts.csv for the given game_ids.
    Returns {game_id: [action_rows_sorted_by_seq]}."""
    path = CACHE / "drafts.csv"
    if not path.exists():
        return {}
    actions = defaultdict(list)
    for a in csv.DictReader(open(path, encoding="utf-8")):
        if a["game_id"] in game_ids:
            actions[a["game_id"]].append(a)
    for gid in actions:
        actions[gid].sort(key=lambda a: int(a["seq"]))
    return dict(actions)


def find_player_by_name(name: str, valid_game_ids: set[str]) -> str | None:
    """Search rosters.csv for a player matching the given name (case-insensitive, stripped).
    Returns player_id if found, None otherwise."""
    path = DATA_DIR / "meta" / "rosters.csv"
    if not path.exists():
        return None
    target = name.strip().lower()
    found_ids = set()
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["title"] != "lol":
            continue
        if r["game_id"] not in valid_game_ids:
            continue
        if r["player_name"].strip().lower() == target:
            found_ids.add(r["player_id"])
    if len(found_ids) == 1:
        return found_ids.pop()
    if len(found_ids) > 1:
        # Multiple ids for same name – pick the one with most games
        counts = Counter()
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r["title"] == "lol" and r["player_id"] in found_ids and r["game_id"] in valid_game_ids:
                counts[r["player_id"]] += 1
        return counts.most_common(1)[0][0]
    return None


# ---------------------------------------------------------------- player pool builder
def build_player_pool(slot: dict, valid_game_ids: set[str], games_csv: dict, drafts_by_game: dict) -> dict:
    """Build a player pool from roster rows.
    Returns dict with player info, games, champions, etc."""
    role = slot["role"]
    name = slot["name"]
    player_id = slot.get("player_id")

    # If no player_id, try name lookup
    if not player_id:
        player_id = find_player_by_name(name, valid_game_ids)

    if not player_id:
        return {
            "player": name, "role": role, "player_id": None,
            "status": "no_data", "games": 0, "series": 0,
            "teams": [], "first_game": None, "last_game": None,
            "unique_champions": 0, "top": [], "g3plus_top": [],
            "champion_picks": [],  # list of (game_id, game_number, champion, team_id, won, bucket, date, event, series_id, burned_before)
        }

    rows = load_player_roster_rows(player_id, valid_game_ids)
    if not rows:
        return {
            "player": name, "role": role, "player_id": player_id,
            "status": "no_data", "games": 0, "series": 0,
            "teams": [], "first_game": None, "last_game": None,
            "unique_champions": 0, "top": [], "g3plus_top": [],
            "champion_picks": [],
        }

    # Build per-game records from player's team perspective
    champ_counter = Counter()
    champ_wins = Counter()
    g3_champs = Counter()
    dates = []
    series_set = set()
    team_names = set()
    champion_picks = []  # (game_id, game_number, champion, team_id, won, bucket, date, event, series_id, burned_before)

    for r in rows:
        gid = r["game_id"]
        g = games_csv.get(gid)
        if not g:
            continue
        gn = int(r["game_number"])
        b = bucket(gn)
        d = day(r.get("date", g.get("date", "")))
        if not d:
            d = day(g.get("date", ""))
        team_id = r["team_id"]
        team_name = r["team_name"]
        champion = r["character_name"]
        won = g["winner_id"] == team_id
        burned_before = set(split_pipe(g.get("burned_before", "")))

        champ_counter[champion] += 1
        champ_wins[champion] += won
        if b == "G3+":
            g3_champs[champion] += 1
        dates.append(d)
        series_set.add(r["series_id"])
        team_names.add(team_name)
        champion_picks.append({
            "game_id": gid, "game_number": gn, "champion": champion,
            "team_id": team_id, "won": won, "bucket": b,
            "date": d, "event": r.get("event", g.get("event", "")),
            "series_id": r["series_id"], "burned_before": burned_before,
        })

    games = len(rows)
    status = "thin" if games < THIN_THRESHOLD else "ok"
    dates.sort()

    top_list = []
    for c, cnt in champ_counter.most_common(TOP):
        top_list.append({
            "champion": c, "games": cnt,
            "record": record(champ_wins[c], cnt),
            "win_rate": wr(champ_wins[c], cnt),
        })

    g3_top = [{"champion": c, "games": cnt} for c, cnt in g3_champs.most_common(3)]

    return {
        "player": name, "role": role, "player_id": player_id,
        "status": status, "games": games, "series": len(series_set),
        "teams": sorted(team_names), "first_game": dates[0] if dates else None,
        "last_game": dates[-1] if dates else None,
        "unique_champions": len(champ_counter), "top": top_list,
        "g3plus_top": g3_top, "champion_picks": champion_picks,
    }


# ---------------------------------------------------------------- aggregate report
def build_roster_report(player_pools: list[dict]) -> dict:
    """Build the full c9-2027.json report from player pools."""
    # Collect all champion picks across players
    all_picks = []
    for pp in player_pools:
        all_picks.extend(pp["champion_picks"])

    # Dedupe games: a game appears once per player, but we need unique games
    # for sample stats. Each pick row is from the player's team perspective.
    # For sample stats, we use the union of all games.
    game_ids = set(p["game_id"] for p in all_picks)
    # Build game-level info: for each unique game, we need winner, bucket, etc.
    # Since picks are per-player, a game may have multiple entries (one per roster player on that team).
    # We dedupe by game_id for game-level stats.
    game_info = {}
    for p in all_picks:
        if p["game_id"] not in game_info:
            game_info[p["game_id"]] = {
                "game_number": p["game_number"], "bucket": p["bucket"],
                "won": p["won"], "date": p["date"], "event": p["event"],
                "series_id": p["series_id"], "team_id": p["team_id"],
            }

    # Sample stats from union of games
    G = len(game_info)
    W = sum(g["won"] for g in game_info.values())
    series_set = set(g["series_id"] for g in game_info.values())
    events_set = sorted(set(g["event"] for g in game_info.values()))
    dates_sorted = sorted(g["date"] for g in game_info.values() if g["date"])

    by_bucket = {}
    for b in BUCKETS:
        sub = [g for g in game_info.values() if g["bucket"] == b]
        by_bucket[b] = {
            "games": len(sub),
            "wins": sum(g["won"] for g in sub),
            "win_rate": wr(sum(g["won"] for g in sub), len(sub)),
        }

    # Per-player game counts for sample
    players_with_data = [pp for pp in player_pools if pp["status"] != "no_data"]
    max_player_games = max((pp["games"] for pp in players_with_data), default=0)

    # Build per-player game counts and bucket counts for denominators
    player_game_counts = {}
    player_bucket_counts = {}
    for pp in player_pools:
        pname = pp["player"]
        player_game_counts[pname] = pp["games"]
        player_bucket_counts[pname] = {b: 0 for b in BUCKETS}
        for cp in pp["champion_picks"]:
            player_bucket_counts[pname][cp["bucket"]] += 1

    # Build per_player dict for sample
    per_player = {}
    for pp in player_pools:
        pname = pp["player"]
        bp = {}
        for b in BUCKETS:
            bp[b] = sum(1 for cp in pp["champion_picks"] if cp["bucket"] == b)
        per_player[pname] = {"games": pp["games"], "by_bucket": bp}

    # Champion table: one entry per champion played by any roster player
    champ_data = defaultdict(lambda: {
        "picks": 0, "pick_wins": 0, "player": None, "role": None,
        "bucket": {b: {"picks": 0, "wins": 0} for b in BUCKETS},
        "player_picks": Counter(),
    })
    for p in all_picks:
        c = p["champion"]
        x = champ_data[c]
        x["picks"] += 1
        x["pick_wins"] += p["won"]
        x["bucket"][p["bucket"]]["picks"] += 1
        x["bucket"][p["bucket"]]["wins"] += p["won"]
        # Track which player picked this champion
        for pp in player_pools:
            if pp["player_id"] and any(cp["game_id"] == p["game_id"] and cp["champion"] == c for cp in pp["champion_picks"]):
                x["player_picks"][pp["player"]] += 1
                x["player"] = pp["player"]
                x["role"] = pp["role"]
                break

    champions = []
    for c, x in champ_data.items():
        # Find the player who plays this champion most
        top_player_name, top_player_cnt = x["player_picks"].most_common(1)[0] if x["player_picks"] else (None, 0)
        role = ""
        for pp in player_pools:
            if pp["player"] == top_player_name:
                role = pp["role"]
                break

        # Use the top player's game count as denominator
        denom = player_game_counts.get(top_player_name, G) if top_player_name else G

        champions.append({
            "champion": c,
            "player": top_player_name,
            "role": role,
            "picks": {**rate(x["picks"], denom), "wins": x["pick_wins"],
                      "win_rate": wr(x["pick_wins"], x["picks"]),
                      "record": record(x["pick_wins"], x["picks"])},
            "bans": rate(0, G),
            "banned_against": rate(0, G),
            "first_bans": rate(0, G),
            "by_bucket": {b: {"picks": rate(v["picks"], player_bucket_counts.get(top_player_name, {}).get(b, by_bucket[b]["games"]) if top_player_name else by_bucket[b]["games"]),
                              "win_rate": wr(v["wins"], v["picks"])}
                          for b, v in x["bucket"].items()},
        })
    champions.sort(key=lambda c: (-c["picks"]["n"], c["champion"]))

    # Top picks per bucket – use per-player denominators
    def top_picks_for_bucket(b, n=TOP):
        cnt = Counter()
        player_cnt = Counter()
        for p in all_picks:
            if p["bucket"] == b:
                cnt[p["champion"]] += 1
                # Find which player this pick belongs to
                for pp in player_pools:
                    if pp["player_id"] and any(cp["game_id"] == p["game_id"] and cp["champion"] == p["champion"] for cp in pp["champion_picks"]):
                        player_cnt[p["champion"]] = pp["player"]
                        break
        results = []
        for c, k in cnt.most_common(n):
            pname = player_cnt.get(c)
            denom = player_bucket_counts.get(pname, {}).get(b, by_bucket[b]["games"]) if pname else by_bucket[b]["games"]
            results.append({"champion": c, **rate(k, denom)})
        return results

    tops = {
        "picks": {b: top_picks_for_bucket(b) for b in BUCKETS},
        "bans": {b: [] for b in BUCKETS},
    }

    # Fearless: favorites (each player's most-played champion)
    favorites = []
    for pp in player_pools:
        if pp["status"] == "no_data" or not pp["top"]:
            continue
        fav_champ = pp["top"][0]["champion"]
        favorites.append({
            "champion": fav_champ,
            "player": pp["player"],
            "role": pp["role"],
        })

    # when_favorites_locked: for each favorite, what happens when it's burned
    when_favorites_locked = []
    for fav in favorites:
        pp = next(p for p in player_pools if p["player"] == fav["player"])
        if pp["status"] == "no_data":
            continue

        # G2+ games where favorite was burned or in opp bans
        later_picks = [p for p in pp["champion_picks"] if p["game_number"] >= 2]
        locked = [p for p in later_picks if fav["champion"] in p["burned_before"]]
        # Replacements: what the player picked when favorite was locked
        repl_counter = Counter()
        locked_wins = 0
        for p in locked:
            repl_counter[p["champion"]] += 1
            locked_wins += p["won"]

        replacements = [{"champion": c, **rate(k, len(locked))} for c, k in repl_counter.most_common(5)]

        # G1 picks of favorite
        g1_picks_of_fav = sum(1 for p in pp["champion_picks"] if p["bucket"] == "G1" and p["champion"] == fav["champion"])
        g1_total = sum(1 for p in pp["champion_picks"] if p["bucket"] == "G1")
        g1_wins_of_fav = sum(1 for p in pp["champion_picks"] if p["bucket"] == "G1" and p["champion"] == fav["champion"] and p["won"])

        when_favorites_locked.append({
            "champion": fav["champion"],
            "player": fav["player"],
            "role": fav["role"],
            "g1_picks": rate(g1_picks_of_fav, g1_total),
            "g1_win_rate": wr(g1_wins_of_fav, g1_picks_of_fav),
            "locked_games": len(locked),
            "burned_games": len(locked),
            "player_games_when_locked": len(locked),
            "win_rate_when_locked": wr(locked_wins, len(locked)),
            "replacements": replacements,
        })

    # by_bucket fearless shift
    g1_pool = set()
    for p in all_picks:
        if p["bucket"] == "G1":
            g1_pool.add(p["champion"])

    shift_by_bucket = {}
    for b in BUCKETS:
        sub_picks = [p for p in all_picks if p["bucket"] == b]
        picks_list = [p["champion"] for p in sub_picks]
        unique = len(set(picks_list))
        new_count = sum(1 for c in picks_list if c not in g1_pool) if b != "G1" else 0
        fav_names = {f["champion"] for f in favorites}
        fav_pick_count = sum(1 for c in picks_list if c in fav_names)
        shift_by_bucket[b] = {
            "games": by_bucket[b]["games"],
            "unique_champions": unique,
            "new_vs_g1_pool": rate(new_count, len(picks_list)),
            "favorite_picks": rate(fav_pick_count, len(picks_list)),
        }

    fearless = {
        "favorites": [f["champion"] for f in favorites],
        "by_bucket": shift_by_bucket,
        "when_favorites_locked": when_favorites_locked,
    }

    # Players section
    players_out = []
    for pp in player_pools:
        top5 = pp["top"][:5]
        players_out.append({
            "player": pp["player"],
            "role": pp["role"],
            "player_id": pp["player_id"],
            "status": pp["status"],
            "games": pp["games"],
            "series": pp["series"],
            "teams": pp["teams"],
            "first_game": pp["first_game"],
            "last_game": pp["last_game"],
            "unique_champions": pp["unique_champions"],
            "top": top5,
            "g3plus_top": pp["g3plus_top"],
        })

    # Caveats
    caveats = [
        "Bans/banned_against/first_bans are zero counts (bans are team-level, not attributable to individual players in a mixed roster).",
        "Sample stats computed over the union of all players' games from each player's team perspective.",
        "Win rates reflect each player's team result, not a unified Cloud9 2027 team.",
    ]

    # Insights
    insights_list = build_roster_insights(player_pools, all_picks, G)

    # Roster flags
    flags = []
    for pp in player_pools:
        if pp["status"] == "no_data":
            flags.append(f"{pp['player']}: no games in the GRID data; {pp['role']}-lane pool unknown")

    report = {
        "team": {
            "id": ROSTER_TEAM_ID,
            "name": "Cloud9 2027",
            "season": "2027 (reported)",
            "events": events_set,
            "reported": True,
            "note": ROSTER_NOTE,
        },
        "sample": {
            "series": len(series_set),
            "games": max_player_games,
            "sample_per_player": True,
            "per_player": per_player,
            "wins": W,
            "win_rate": wr(W, G),
            "first_game": dates_sorted[0] if dates_sorted else None,
            "last_game": dates_sorted[-1] if dates_sorted else None,
            "by_bucket": by_bucket,
            "by_side": {"blue": {"games": G, "wins": W, "win_rate": wr(W, G)},
                        "red": {"games": 0, "wins": 0, "win_rate": None}},
            "first_pick_rate": rate(G, G),
            "blue_side_rate": rate(G, G),
            "caveats": caveats,
        },
        "champions": champions,
        "top": tops,
        "fearless": fearless,
        "players": players_out,
        "roster": {
            "label": ROSTER_LABEL,
            "reported_date": ROSTER_REPORTED_DATE,
            "note": ROSTER_NOTE,
            "flags": flags,
        },
        "insights": insights_list,
    }
    return report


def build_roster_insights(player_pools: list[dict], all_picks: list[dict], G: int) -> list[dict]:
    """Generate 2-3 insights from player pools."""
    insights = []

    # Deepest pool
    players_with_data = [pp for pp in player_pools if pp["status"] != "no_data"]
    if players_with_data:
        deepest = max(players_with_data, key=lambda p: p["unique_champions"])
        insights.append({
            "score": 1.0,
            "question": "What pick/ban tendencies repeat most?",
            "id": "deepest_pool",
            "title": f"{deepest['player']} has the deepest pool",
            "text": f"{deepest['player']} ({deepest['role']}) has played {deepest['unique_champions']} unique champions across {deepest['games']} games.",
            "evidence": {"player": deepest["player"], "role": deepest["role"],
                         "unique_champions": deepest["unique_champions"], "games": deepest["games"]},
        })

    # Most played champion overall
    if all_picks:
        champ_counter = Counter(p["champion"] for p in all_picks)
        top_champ, top_count = champ_counter.most_common(1)[0]
        # Find who plays it
        for pp in player_pools:
            if any(cp["champion"] == top_champ for cp in pp["champion_picks"]):
                insights.append({
                    "score": 0.9,
                    "question": "What pick/ban tendencies repeat most?",
                    "id": "most_played",
                    "title": f"{top_champ} is the most-played champion",
                    "text": f"{top_champ} is picked {top_count} times across the roster, primarily by {pp['player']} ({pp['role']}).",
                    "evidence": {"champion": top_champ, "picks": top_count,
                                 "player": pp["player"], "role": pp["role"]},
                })
                break

    # G3+ depth
    g3_picks = [p for p in all_picks if p["bucket"] == "G3+"]
    if g3_picks:
        g3_unique = len(set(p["champion"] for p in g3_picks))
        g1_pool = set(p["champion"] for p in all_picks if p["bucket"] == "G1")
        new_in_g3 = sum(1 for p in g3_picks if p["champion"] not in g1_pool)
        insights.append({
            "score": 0.8,
            "question": "How does the draft shift in Fearless G2/G3+?",
            "id": "g3_depth",
            "title": "Roster digs deep in G3+",
            "text": f"In G3+ games the roster plays {g3_unique} unique champions, with {new_in_g3}/{len(g3_picks)} picks outside the G1 pool.",
            "evidence": {"g3_unique": g3_unique, "new_in_g3": new_in_g3, "g3_total": len(g3_picks)},
        })

    insights.sort(key=lambda i: -i["score"])
    return insights[:3]


# ---------------------------------------------------------------- index merge
def merge_index(report: dict) -> None:
    """Add or update the c9-2027 entry in index.json. Idempotent."""
    index_path = OUT / "index.json"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"generated_at": "", "source": "", "teams": [], "league": {}}

    teams = index.get("teams", [])
    # Remove existing c9-2027 entry
    teams = [t for t in teams if t.get("id") != ROSTER_TEAM_ID]

    # Count total games across players
    total_games = sum(p["games"] for p in report.get("players", []))

    entry = {
        "id": ROSTER_TEAM_ID,
        "name": "Cloud9 2027 (reported)",
        "season": "2027",
        "league": "LCS",
        "lcs_2026": False,
        "reported": True,
        "file": f"teams/{ROSTER_TEAM_ID}.json",
        "games": report["sample"]["games"],
        "headline": report["insights"][0]["text"] if report.get("insights") else "",
    }
    teams.append(entry)
    # Sort: LCS 2026 first, then by games desc
    teams.sort(key=lambda t: (not t.get("lcs_2026", False), t.get("reported", False), -t.get("games", 0)))
    index["teams"] = teams

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- main
def main():
    if not (CACHE / "games.csv").exists():
        sys.exit("cache/games.csv not found. Run pipeline/extract_drafts.py first.")

    valid_game_ids = load_cache_game_ids()
    games_csv = load_games_csv()

    # Load drafts for all valid games (needed for burned_before etc.)
    drafts_by_game = load_drafts_for_games(valid_game_ids)

    # Build player pools
    player_pools = []
    for slot in ROSTER:
        pool = build_player_pool(slot, valid_game_ids, games_csv, drafts_by_game)
        player_pools.append(pool)
        status_icon = "✓" if pool["status"] == "ok" else "⚠" if pool["status"] == "thin" else "✗"
        print(f"  {status_icon} {pool['player']} ({pool['role']}): {pool['status']} – {pool['games']} games, teams: {pool['teams']}")

    # Build report
    report = build_roster_report(player_pools)

    # Write team report
    (OUT / "teams").mkdir(parents=True, exist_ok=True)
    report_path = OUT / "teams" / f"{ROSTER_TEAM_ID}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\nWrote {report_path}")

    # Merge into index
    merge_index(report)
    print(f"Merged into {OUT / 'index.json'}")

    # Print summary
    print("\n--- Player Summary ---")
    for pp in player_pools:
        print(f"\n{pp['player']} ({pp['role']}): {pp['status']}")
        print(f"  Games: {pp['games']}, Teams: {pp['teams']}")
        if pp["top"]:
            print(f"  Top 5 champions:")
            for t in pp["top"][:5]:
                print(f"    {t['champion']}: {t['games']} games ({t['record']})")


if __name__ == "__main__":
    main()
