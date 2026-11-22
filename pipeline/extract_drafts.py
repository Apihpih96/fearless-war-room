"""
Fearless War Room - Step 1: draft extractor.

Reads every League of Legends GRID series feed and writes one row per
draft action (pick or ban) to cache/drafts.csv, plus cache/games.csv with
one row per game (winner, sides, patch, game number, Fearless context).

The output is DERIVED from licensed GRID data, so it goes to cache/,
which is gitignored. Never commit it.

Usage:
    pip install -r requirements.txt
    python pipeline/extract_drafts.py                 # all LoL series
    python pipeline/extract_drafts.py --team "Cloud9 Kia"
Env:
    STL_DATA_DIR  path to stl-hackathon-2026-grid-starter (default ../stl-hackathon-2026-grid-starter)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    from compression import zstd  # Python 3.14+
except ImportError:  # Python <= 3.13
    import zstandard as zstd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = pathlib.Path(os.environ.get("STL_DATA_DIR", ROOT.parent / "stl-hackathon-2026-grid-starter"))
OUT_DIR = ROOT / "cache"

DRAFT_FIELDS = [
    "series_id", "game_id", "game_number", "patch", "event", "stage", "date",
    "seq", "action", "team_id", "team_name", "side", "opponent_id", "opponent_name",
    "champion", "champion_id", "won_game",
]
GAME_FIELDS = [
    "series_id", "game_id", "game_number", "patch", "event", "stage", "date", "format",
    "blue_id", "blue_name", "red_id", "red_name", "winner_id",
    "blue_picks", "red_picks", "blue_bans", "red_bans",
    "burned_before",  # champions already picked earlier in this series (Fearless locks)
]


def read_jsonl_zst(path: pathlib.Path):
    with zstd.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def load_meta():
    """games.csv gives game_number, patch, winner per game_id (valid sessions only)."""
    games = {}
    with open(DATA_DIR / "meta" / "games.csv", encoding="utf-8") as f:
        for g in csv.DictReader(f):
            if g["title"] != "lol" or g["session_valid"] != "True" or g["finished"] != "True":
                continue
            games[g["game_id"]] = g
    series = {}
    with open(DATA_DIR / "lol" / "series.csv", encoding="utf-8") as f:
        for s in csv.DictReader(f):
            series[s["series_id"]] = s
    return games, series


def final_states(path: pathlib.Path):
    """Last full seriesState of each feed session (some files hold two sessions)."""
    states, last = [], None
    for env in read_jsonl_zst(path):
        for e in env["events"]:
            if e["type"] == "grid-started-feed" and last is not None:
                states.append(last)
                last = None
            if e.get("includesFullState") and e.get("seriesState"):
                last = e["seriesState"]
    if last is not None:
        states.append(last)
    return states


def process_series(series_id: str, file_rel: str, meta_games: dict, srow: dict):
    path = DATA_DIR / file_rel
    if not path.exists():
        return [], [], f"missing {file_rel}"
    draft_rows, game_rows = [], []
    seen_games = set()
    for state in final_states(path):
        fmt = state.get("format") or ""
        played = []
        for g in state.get("games", []):
            gid = g.get("id")
            m = meta_games.get(gid)
            if not m or gid in seen_games or not g.get("draftActions"):
                continue  # rolled back, invalid, or no draft recorded
            seen_games.add(gid)
            played.append((int(m["game_number"]), g, m))
        burned: list[str] = []  # Fearless: champions picked in earlier games of the series
        for game_number, g, m in sorted(played, key=lambda x: x[0]):
            teams = {t["id"]: t for t in g.get("teams", [])}
            side_of = {tid: t.get("side") for tid, t in teams.items()}
            name_of = {tid: t.get("name") for tid, t in teams.items()}
            winner = m["winner_team_id"]
            picks = {"blue": [], "red": []}
            bans = {"blue": [], "red": []}
            for a in sorted(g["draftActions"], key=lambda a: a["sequenceNumber"]):
                tid = a["drafter"]["id"]
                opp = next((t for t in teams if t != tid), "")
                side = side_of.get(tid, "")
                champ = a["draftable"]["name"]
                (picks if a["type"] == "pick" else bans).setdefault(side, []).append(champ)
                draft_rows.append({
                    "series_id": series_id, "game_id": g["id"], "game_number": game_number,
                    "patch": m["patch"], "event": srow.get("event", ""), "stage": srow.get("stage", ""),
                    "date": m["started_at"], "seq": a["sequenceNumber"], "action": a["type"],
                    "team_id": tid, "team_name": name_of.get(tid, ""), "side": side,
                    "opponent_id": opp, "opponent_name": name_of.get(opp, ""),
                    "champion": champ, "champion_id": a["draftable"]["id"],
                    "won_game": int(tid == winner),
                })
            blue = next((t for t, s in side_of.items() if s == "blue"), "")
            red = next((t for t, s in side_of.items() if s == "red"), "")
            game_rows.append({
                "series_id": series_id, "game_id": g["id"], "game_number": game_number,
                "patch": m["patch"], "event": srow.get("event", ""), "stage": srow.get("stage", ""),
                "date": m["started_at"], "format": fmt if isinstance(fmt, str) else fmt.get("id", ""),
                "blue_id": blue, "blue_name": name_of.get(blue, ""),
                "red_id": red, "red_name": name_of.get(red, ""), "winner_id": winner,
                "blue_picks": "|".join(picks["blue"]), "red_picks": "|".join(picks["red"]),
                "blue_bans": "|".join(bans["blue"]), "red_bans": "|".join(bans["red"]),
                "burned_before": "|".join(burned),
            })
            burned += picks["blue"] + picks["red"]
    return draft_rows, game_rows, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", help="only series whose teams contain this name, e.g. 'Cloud9 Kia'")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    if not (DATA_DIR / "meta" / "games.csv").exists():
        sys.exit(f"GRID data not found at {DATA_DIR}. Clone it next to this repo or set STL_DATA_DIR.")

    meta_games, series = load_meta()
    todo = [(sid, s) for sid, s in series.items()
            if not args.team or args.team.lower() in s["teams"].lower()]
    OUT_DIR.mkdir(exist_ok=True)

    drafts, games, problems = [], [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process_series, sid, s["file"], meta_games, s): sid for sid, s in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            d, g, err = fut.result()
            drafts += d
            games += g
            if err:
                problems.append(err)
            print(f"\r{i}/{len(todo)} series", end="", file=sys.stderr)
    print(file=sys.stderr)

    drafts.sort(key=lambda r: (r["date"], r["series_id"], r["game_number"], r["seq"]))
    games.sort(key=lambda r: (r["date"], r["series_id"], r["game_number"]))
    for name, rows, fields in (("drafts.csv", drafts, DRAFT_FIELDS), ("games.csv", games, GAME_FIELDS)):
        with open(OUT_DIR / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print(f"{len(games)} games, {len(drafts)} draft actions -> {OUT_DIR}")
    if problems:
        print(f"{len(problems)} skipped: " + "; ".join(problems[:5]) + (" ..." if len(problems) > 5 else ""))


if __name__ == "__main__":
    main()
