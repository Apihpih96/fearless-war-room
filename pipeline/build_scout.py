"""
Fearless War Room - Step 2: opponent scout.

Reads cache/drafts.csv + cache/games.csv (from extract_drafts.py) and the GRID
roster metadata, and writes AGGREGATE scouting JSON for every team:

    web/public/data/index.json              list of teams + league baselines
    web/public/data/teams/<team_id>.json    one scouting report per team

Only counts, rates and short plain-English insights are written, never
per-game rows, so the output is safe to commit (GRID license rule).

Each report covers the team's most recent season (2026 for LCS teams) and answers:
  * What pick/ban tendencies repeat most for this opponent?
  * How does the opponent's draft shift in Fearless G2 / G3+?

Note on sides: from 2026 Riot's "First Selection" lets a team take first pick
OR side, so first pick is computed from draft order, not from blue side.

Usage:
    python pipeline/build_scout.py
    python pipeline/build_scout.py --season 2026 --min-games 6
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = pathlib.Path(os.environ.get("STL_DATA_DIR", ROOT.parent / "stl-hackathon-2026-grid-starter"))
CACHE = pathlib.Path(os.environ.get("FWR_CACHE_DIR", ROOT / "cache"))
OUT = pathlib.Path(os.environ.get("FWR_OUT_DIR", ROOT / "web" / "public" / "data"))

BUCKETS = ("G1", "G2", "G3+")
FAVORITES = 5          # a team's top-N G1 picks are its "favorites"
TOP = 8                # rows kept in short top-lists


# ---------------------------------------------------------------- helpers
def bucket(game_number: int) -> str:
    return "G1" if game_number == 1 else "G2" if game_number == 2 else "G3+"


def rate(n: int, of: int) -> dict:
    """A count with its denominator, e.g. {'n': 7, 'of': 10, 'rate': 0.7, 'label': '7/10'}."""
    return {"n": n, "of": of, "rate": round(n / of, 3) if of else None, "label": f"{n}/{of}"}


def wr(wins: int, games: int) -> float | None:
    return round(wins / games, 3) if games else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(100 * x)}%"


def day(s: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else ""


def split(s: str) -> list[str]:
    return [x for x in s.split("|") if x]


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def record(w: int, g: int) -> str:
    return f"{w}-{g - w}"


# ---------------------------------------------------------------- load
def load_team_games():
    """One record per (team, game): what that team did in the draft."""
    if not (CACHE / "drafts.csv").exists():
        sys.exit("cache/drafts.csv not found. Run pipeline/extract_drafts.py first.")
    games = {g["game_id"]: g for g in csv.DictReader(open(CACHE / "games.csv", encoding="utf-8"))}
    actions = defaultdict(list)
    champ_ids = {}
    for a in csv.DictReader(open(CACHE / "drafts.csv", encoding="utf-8")):
        actions[a["game_id"]].append(a)
        champ_ids[a["champion"]] = a["champion_id"]

    rows = []
    for gid, acts in actions.items():
        g = games.get(gid)
        if not g:
            continue
        acts.sort(key=lambda a: int(a["seq"]))
        first_picker = next((a["team_id"] for a in acts if a["action"] == "pick"), None)
        burned = set(split(g["burned_before"]))
        all_bans = [a["champion"] for a in acts if a["action"] == "ban"]
        teams = {a["team_id"]: a for a in acts}
        for tid, a0 in teams.items():
            mine = [a for a in acts if a["team_id"] == tid]
            picks = [a["champion"] for a in mine if a["action"] == "pick"]
            bans = [a["champion"] for a in mine if a["action"] == "ban"]
            opp_bans = [a["champion"] for a in acts if a["team_id"] != tid and a["action"] == "ban"]
            n = int(g["game_number"])
            rows.append({
                "team_id": tid, "team_name": a0["team_name"],
                "opp_id": a0["opponent_id"], "opp_name": a0["opponent_name"],
                "series_id": g["series_id"], "game_id": gid, "game_number": n, "bucket": bucket(n),
                "event": g["event"], "date": day(g["date"]), "season": day(g["date"])[:4],
                "patch": g["patch"], "format": g["format"],
                "side": a0["side"], "first_pick": tid == first_picker,
                "won": a0["won_game"] == "1",
                "picks": picks, "bans": bans, "opp_bans": opp_bans,
                "first_pick_champ": picks[0] if picks else None,
                "first_ban": bans[0] if bans else None,
                "burned": burned, "all_bans": set(all_bans),
            })
    return rows, champ_ids


def load_player_picks(game_ids: set[str]):
    """(game_id, team_id) -> [(player, champion)] from GRID rosters (active players only)."""
    out = defaultdict(list)
    path = DATA_DIR / "meta" / "rosters.csv"
    if not path.exists():
        return out
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["title"] == "lol" and r["game_id"] in game_ids and r["participation_status"] == "active":
            out[(r["game_id"], r["team_id"])].append((r["player_name"], r["character_name"]))
    return out


# ---------------------------------------------------------------- league baselines
def league_baseline(rows):
    """Per season: champion pick rate / presence across all games, and the
    league-wide share of G3+ picks on champions a team never played in a G1."""
    base = {}
    for season in {r["season"] for r in rows}:
        rs = [r for r in rows if r["season"] == season]
        n_games = len({r["game_id"] for r in rs})
        picks, presence = Counter(), Counter()
        seen = defaultdict(set)
        for r in rs:
            for c in r["picks"]:
                picks[c] += 1
            seen[r["game_id"]].update(r["picks"], r["bans"])
        for s in seen.values():
            presence.update(s)
        # deep-pool share, team by team
        new, total = 0, 0
        g1_pool = defaultdict(set)
        for r in rs:
            if r["bucket"] == "G1":
                g1_pool[r["team_id"]].update(r["picks"])
        for r in rs:
            if r["bucket"] == "G3+":
                total += len(r["picks"])
                new += sum(c not in g1_pool[r["team_id"]] for c in r["picks"])
        base[season] = {
            "games": n_games,
            "pick_rate": {c: v / n_games for c, v in picks.items()},
            "presence": {c: v / n_games for c, v in presence.items()},
            "g3_new_share": new / total if total else None,
        }
    return base


# ---------------------------------------------------------------- team report
def team_report(tid, rows, champ_ids, league, player_picks):
    season = max(r["season"] for r in rows)
    rs = sorted((r for r in rows if r["season"] == season), key=lambda r: (r["date"], r["game_number"]))
    name = rs[-1]["team_name"]
    lg = league[season]
    G = len(rs)
    W = sum(r["won"] for r in rs)

    def split_record(key, values):
        out = {}
        for v in values:
            sub = [r for r in rs if r[key] == v]
            out[str(v)] = {"games": len(sub), "wins": sum(r["won"] for r in sub),
                           "win_rate": wr(sum(r["won"] for r in sub), len(sub))}
        return out

    by_bucket = split_record("bucket", BUCKETS)
    by_side = split_record("side", ("blue", "red"))
    fp = split_record("first_pick", (True, False))
    by_fp = {"first": fp["True"], "second": fp["False"]}
    fp_games = by_fp["first"]["games"]

    # ---- champion table
    C = defaultdict(lambda: {
        "picks": 0, "pick_wins": 0, "bans": 0, "banned_against": 0, "first_picks": 0, "first_bans": 0,
        "bucket": {b: {"picks": 0, "wins": 0, "bans": 0} for b in BUCKETS},
        "side": {s: {"picks": 0, "wins": 0, "bans": 0} for s in ("blue", "red")},
    })
    for r in rs:
        for c in r["picks"]:
            x = C[c]
            x["picks"] += 1
            x["pick_wins"] += r["won"]
            x["bucket"][r["bucket"]]["picks"] += 1
            x["bucket"][r["bucket"]]["wins"] += r["won"]
            if r["side"] in x["side"]:
                x["side"][r["side"]]["picks"] += 1
                x["side"][r["side"]]["wins"] += r["won"]
        for c in r["bans"]:
            C[c]["bans"] += 1
            C[c]["bucket"][r["bucket"]]["bans"] += 1
            if r["side"] in C[c]["side"]:
                C[c]["side"][r["side"]]["bans"] += 1
        for c in r["opp_bans"]:
            C[c]["banned_against"] += 1
        if r["first_pick"] and r["first_pick_champ"]:
            C[r["first_pick_champ"]]["first_picks"] += 1
        if r["first_ban"]:
            C[r["first_ban"]]["first_bans"] += 1

    champions = []
    for c, x in C.items():
        presence = sum(1 for r in rs if c in r["picks"] or c in r["bans"])
        lpr = lg["pick_rate"].get(c, 0)
        champions.append({
            "champion": c, "champion_id": champ_ids.get(c, ""),
            "presence": rate(presence, G),
            "picks": {**rate(x["picks"], G), "wins": x["pick_wins"], "win_rate": wr(x["pick_wins"], x["picks"]),
                      "record": record(x["pick_wins"], x["picks"])},
            "bans": rate(x["bans"], G),
            "banned_against": rate(x["banned_against"], G),
            "first_picks": rate(x["first_picks"], fp_games),
            "first_bans": rate(x["first_bans"], G),
            "by_bucket": {b: {"picks": rate(v["picks"], by_bucket[b]["games"]),
                              "bans": rate(v["bans"], by_bucket[b]["games"]),
                              "win_rate": wr(v["wins"], v["picks"])}
                          for b, v in x["bucket"].items()},
            "by_side": {s: {"picks": rate(v["picks"], by_side[s]["games"]),
                            "bans": rate(v["bans"], by_side[s]["games"]),
                            "win_rate": wr(v["wins"], v["picks"])}
                        for s, v in x["side"].items()},
            "league_pick_rate": round(lpr, 3),
            "pick_lift": round((x["picks"] / G) / lpr, 2) if lpr else None,
        })
    champions.sort(key=lambda c: (-c["presence"]["n"], -c["picks"]["n"], c["champion"]))

    def top(key, sub_rows, n=TOP, field="picks"):
        cnt = Counter()
        for r in sub_rows:
            v = r[field]
            cnt.update(v if isinstance(v, list) else [v] if v else [])
        return [{"champion": c, **rate(k, len(sub_rows))} for c, k in cnt.most_common(n)]

    tops = {
        "picks": {b: top(b, [r for r in rs if r["bucket"] == b]) for b in BUCKETS},
        "bans": {b: top(b, [r for r in rs if r["bucket"] == b], field="bans") for b in BUCKETS},
        "first_picks": {b: top(b, [r for r in rs if r["bucket"] == b and r["first_pick"]], 5, "first_pick_champ")
                        for b in BUCKETS},
        "first_bans": top("all", rs, 5, "first_ban"),
        "banned_against": top("all", rs, 5, "opp_bans"),
        "picks_by_side": {s: top(s, [r for r in rs if r["side"] == s]) for s in ("blue", "red")},
        "bans_by_side": {s: top(s, [r for r in rs if r["side"] == s], field="bans") for s in ("blue", "red")},
    }

    # ---- Fearless shift
    g1 = [r for r in rs if r["bucket"] == "G1"]
    g1_pool = set(c for r in g1 for c in r["picks"])
    g1_counts = Counter(c for r in g1 for c in r["picks"])
    favorites = [c for c, _ in g1_counts.most_common(FAVORITES)]
    later = [r for r in rs if r["game_number"] >= 2]

    shift_by_bucket = {}
    for b in BUCKETS:
        sub = [r for r in rs if r["bucket"] == b]
        picks = [c for r in sub for c in r["picks"]]
        new = sum(c not in g1_pool for c in picks)
        shift_by_bucket[b] = {
            "games": len(sub),
            "unique_champions": len(set(picks)),
            "new_vs_g1_pool": rate(new, len(picks)),
            "favorite_picks": rate(sum(c in favorites for c in picks), len(picks)),
        }

    # who plays each champion for this team (GRID rosters), so a burned favorite
    # is replaced by what THAT player picks instead: role-correct without role data
    played_by = defaultdict(Counter)
    for r in rs:
        for p, c in player_picks.get((r["game_id"], r["team_id"]), []):
            played_by[c][p] += 1

    fav_rows = []
    for f in favorites:
        locked = [r for r in later if f in r["burned"] or f in r["opp_bans"]]
        burned_only = [r for r in later if f in r["burned"]]
        player = played_by[f].most_common(1)[0][0] if played_by[f] else None
        repl, seen = Counter(), 0
        for r in locked:
            pp = player_picks.get((r["game_id"], r["team_id"]), [])
            mine = [c for p, c in pp if p == player]
            if player and mine:
                repl.update(mine)
                seen += 1
        if not seen:  # no roster info: fall back to every pick the team made
            repl = Counter(c for r in locked for c in r["picks"])
            seen = len(locked)
        replacements = [{"champion": c, **rate(k, seen)} for c, k in repl.most_common(5)]
        avail = [r for r in later if r not in locked]
        fav_rows.append({
            "champion": f, "player": player, "g1_picks": rate(g1_counts[f], len(g1)),
            "g1_win_rate": wr(sum(r["won"] for r in g1 if f in r["picks"]), g1_counts[f]),
            "locked_games": len(locked), "burned_games": len(burned_only), "player_games_when_locked": seen,
            "picked_when_available_g2plus": rate(sum(f in r["picks"] for r in avail), len(avail)),
            "win_rate_when_locked": wr(sum(r["won"] for r in locked), len(locked)),
            "replacements": replacements,
        })

    # picks once 3+ favorites are already burned (the deep end of a series)
    deep = [r for r in later if sum(f in r["burned"] for f in favorites) >= 3]
    fearless = {
        "favorites": favorites,
        "by_bucket": shift_by_bucket,
        "league_g3_new_share": round(lg["g3_new_share"], 3) if lg["g3_new_share"] is not None else None,
        "when_favorites_locked": fav_rows,
        "deep_series": {"games": len(deep), "wins": sum(r["won"] for r in deep),
                        "top_picks": top("deep", deep, 6)},
    }

    # ---- players
    pc = defaultdict(lambda: {"games": 0, "champs": Counter(), "wins": Counter(), "g3": Counter()})
    for r in rs:
        for p, c in player_picks.get((r["game_id"], r["team_id"]), []):
            x = pc[p]
            x["games"] += 1
            x["champs"][c] += 1
            x["wins"][c] += r["won"]
            if r["bucket"] == "G3+":
                x["g3"][c] += 1
    players = []
    for p, x in sorted(pc.items(), key=lambda kv: -kv[1]["games"]):
        if x["games"] < max(3, G // 10):
            continue
        players.append({
            "player": p, "games": x["games"], "unique_champions": len(x["champs"]),
            "top": [{"champion": c, "games": k, "record": record(x["wins"][c], k)} for c, k in x["champs"].most_common(5)],
            "g3plus_top": [{"champion": c, "games": k} for c, k in x["g3"].most_common(3)],
        })

    series = {r["series_id"] for r in rs}
    report = {
        "team": {"id": tid, "name": name, "season": season,
                 "events": sorted({r["event"] for r in rs})},
        "sample": {
            "series": len(series), "games": G, "wins": W, "win_rate": wr(W, G),
            "first_game": rs[0]["date"], "last_game": rs[-1]["date"],
            "patches": sorted({r["patch"] for r in rs}, key=lambda p: [int(x) for x in re.findall(r"\d+", p)]),
            "by_bucket": by_bucket, "by_side": by_side, "by_first_pick": by_fp,
            "first_pick_rate": rate(fp_games, G),
            "blue_side_rate": rate(by_side["blue"]["games"], G),
        },
        "champions": champions,
        "top": tops,
        "fearless": fearless,
        "players": players,
    }
    report["insights"] = insights(report, lg)
    return report


# ---------------------------------------------------------------- insights
def insights(rep, lg, k=5):
    """Plain-English, evidence-backed findings, scored and capped at k.
    Each answers one of the two judge questions."""
    Q1 = "What pick/ban tendencies repeat most?"
    Q2 = "How does the draft shift in Fearless G2/G3+?"
    S = rep["sample"]
    G = S["games"]
    champs = {c["champion"]: c for c in rep["champions"]}
    cand = []

    def add(score, q, id_, title, text, evidence):
        cand.append({"score": score, "question": q, "id": id_, "title": title, "text": text, "evidence": evidence})

    # 1. most repeated champion (picked or banned by them)
    if rep["champions"]:
        c = rep["champions"][0]
        p, b = c["picks"], c["bans"]
        add(c["presence"]["rate"] * math.log(G + 1), Q1, "most_contested",
            f"{c['champion']} is always on their mind",
            f"They pick or ban {c['champion']} in {c['presence']['label']} games ({pct(c['presence']['rate'])}): "
            f"{plural(p['n'], 'pick')} ({p['record']}) and {plural(b['n'], 'ban')}.",
            {"champion": c["champion"], "presence": c["presence"], "picks": p["label"], "record": p["record"],
             "bans": b["label"]})

    # 2. first-ban fixation
    fb = rep["top"]["first_bans"]
    if fb and fb[0]["n"] >= 3 and fb[0]["rate"] >= 0.25:
        x = fb[0]
        add(x["rate"] * math.log(x["n"] + 1) * 1.6, Q1, "first_ban",
            f"They open bans on {x['champion']}",
            f"{x['champion']} is their first ban in {x['label']} games ({pct(x['rate'])}). Expect it gone before your first pick.",
            {"champion": x["champion"], "first_bans": x["label"]})

    # 3. G1 first-pick comfort
    fpg1 = rep["top"]["first_picks"]["G1"]
    if fpg1 and fpg1[0]["n"] >= 3 and fpg1[0]["rate"] >= 0.3:
        x = fpg1[0]
        rec = champs[x["champion"]]["picks"]["record"]
        add(x["rate"] * math.log(x["n"] + 1) * 1.8, Q1, "g1_first_pick",
            f"G1 first pick: {x['champion']}",
            f"With first pick in Game 1 they took {x['champion']} {x['label']} times ({pct(x['rate'])}). "
            f"Overall {rec} on it. Ban it or be ready to answer it in G1.",
            {"champion": x["champion"], "g1_first_picks": x["label"], "record": rec})

    # 4. signature pick vs the league
    sig = [c for c in rep["champions"] if c["picks"]["n"] >= 4 and c["pick_lift"] and c["pick_lift"] >= 2
           and c["picks"]["rate"] >= 0.2]
    if sig:
        c = max(sig, key=lambda c: c["pick_lift"] * c["picks"]["n"])
        add(min(c["pick_lift"], 5) * c["picks"]["rate"] * math.log(c["picks"]["n"] + 1) * 0.8, Q1, "signature",
            f"Signature pick: {c['champion']}",
            f"They pick {c['champion']} in {c['picks']['label']} games ({pct(c['picks']['rate'])}), "
            f"{c['pick_lift']}x the league rate of {pct(c['league_pick_rate'])}. Record {c['picks']['record']}.",
            {"champion": c["champion"], "picks": c["picks"]["label"], "lift": c["pick_lift"],
             "league_pick_rate": c["league_pick_rate"]})

    # 5. respect bans against them
    ba = rep["top"]["banned_against"]
    if ba and ba[0]["rate"] >= 0.4 and ba[0]["n"] >= 4:
        x = ba[0]
        add(x["rate"] * math.log(x["n"] + 1) * 0.9, Q1, "respect_ban",
            f"Teams respect-ban {x['champion']} against them",
            f"Opponents banned {x['champion']} against them in {x['label']} games ({pct(x['rate'])}).",
            {"champion": x["champion"], "banned_against": x["label"]})

    F = rep["fearless"]
    bb = F["by_bucket"]
    # 6. deep pool in G3+
    g3 = bb["G3+"]
    if g3["games"] >= 3 and F["league_g3_new_share"] is not None and g3["new_vs_g1_pool"]["of"]:
        share, base = g3["new_vs_g1_pool"]["rate"], F["league_g3_new_share"]
        diff = share - base
        word = "dig deeper than most" if diff > 0.05 else "stay closer to their core than most" if diff < -0.05 else "go about as deep as the league"
        add(abs(diff) * 6 + 0.8, Q2, "g3_pool",
            f"In G3+ they {word}",
            f"In {g3['games']} G3+ games, {g3['new_vs_g1_pool']['label']} picks ({pct(share)}) were champions they "
            f"never played in any G1 (league {pct(base)}). Pool: {bb['G1']['unique_champions']} champs in G1s, "
            f"{g3['unique_champions']} in G3+.",
            {"g3_games": g3["games"], "new_share": g3["new_vs_g1_pool"]["label"], "league_share": base,
             "unique_g1": bb["G1"]["unique_champions"], "unique_g3": g3["unique_champions"]})

    # 7. where they go when a favorite is gone
    for fav in F["when_favorites_locked"][:3]:
        if fav["locked_games"] >= 3 and fav["replacements"]:
            r = [x for x in fav["replacements"] if x["champion"] != fav["champion"]][:2]
            if not r or r[0]["n"] < 2:
                continue
            alt = " and ".join(f"{x['champion']} ({x['label']})" for x in r)
            add(0.9 + fav["g1_picks"]["rate"] + r[0]["rate"], Q2, f"locked_{fav['champion']}",
                f"No {fav['champion']}? They go {r[0]['champion']}",
                f"{fav['champion']} is a G1 favorite ({fav['g1_picks']['label']} G1s"
                + (f", played by {fav['player']}" if fav["player"] else "") + f"). In the {r[0]['of']} later games where "
                f"it was burned or banned, {fav['player'] or 'they'} went to {alt}.",
                {"favorite": fav["champion"], "g1_picks": fav["g1_picks"]["label"], "locked_games": fav["locked_games"],
                 "replacements": r, "win_rate_when_locked": fav["win_rate_when_locked"]})
            break

    # 8. win rate across the series
    a, z = S["by_bucket"]["G1"], S["by_bucket"]["G3+"]
    if a["games"] >= 5 and z["games"] >= 4 and abs(a["win_rate"] - z["win_rate"]) >= 0.15:
        better = z["win_rate"] > a["win_rate"]
        add(abs(a["win_rate"] - z["win_rate"]) * 4, Q2, "series_depth",
            "They get stronger as the series goes deep" if better else "They fade once their pool is burned",
            f"G1 record {record(a['wins'], a['games'])} ({pct(a['win_rate'])}) vs G3+ record "
            f"{record(z['wins'], z['games'])} ({pct(z['win_rate'])}).",
            {"g1": a, "g3plus": z})

    # 9. First Selection: first pick vs side
    f1, f2 = S["by_first_pick"]["first"], S["by_first_pick"]["second"]
    if f1["games"] >= 4 and f2["games"] >= 4 and abs((f1["win_rate"] or 0) - (f2["win_rate"] or 0)) >= 0.2:
        add(abs(f1["win_rate"] - f2["win_rate"]) * 3, Q1, "first_pick_split",
            "Draft order matters to them",
            f"With first pick: {record(f1['wins'], f1['games'])} ({pct(f1['win_rate'])}). Without: "
            f"{record(f2['wins'], f2['games'])} ({pct(f2['win_rate'])}).",
            {"first_pick": f1, "second_pick": f2})

    cand.sort(key=lambda c: -c["score"])
    chosen = []
    for q in (Q1, Q2):  # guarantee both judge questions are answered
        best = next((c for c in cand if c["question"] == q), None)
        if best:
            chosen.append(best)
    for c in cand:
        if len(chosen) >= k:
            break
        if c not in chosen:
            chosen.append(c)
    chosen.sort(key=lambda c: -c["score"])
    for c in chosen:
        c["score"] = round(c["score"], 3)
    return chosen


# ---------------------------------------------------------------- roster
def champion_roster(seen):
    """Full champion roster for the web app: Riot Data Dragon (public) for image
    keys and roles, plus any drafted champion Data Dragon does not know yet.
    Works offline too: then it is just the names seen in drafts."""
    import urllib.request
    dd = "https://ddragon.leagueoflegends.com"
    try:
        with urllib.request.urlopen(f"{dd}/api/versions.json", timeout=10) as r:
            version = json.load(r)[0]
        with urllib.request.urlopen(f"{dd}/cdn/{version}/data/en_US/champion.json", timeout=20) as r:
            data = json.load(r)["data"]
        champs = [{"name": c["name"], "image": c["image"]["full"], "tags": c["tags"]} for c in data.values()]
    except Exception as e:  # offline: names only, the app shows initials
        print(f"Data Dragon unavailable ({e}); roster = drafted champions only", file=sys.stderr)
        version, champs = None, []
    known = {c["name"] for c in champs}
    champs += [{"name": n, "image": None, "tags": []} for n in seen if n not in known]
    return {"version": version, "champions": sorted(champs, key=lambda c: c["name"])}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-games", type=int, default=6, help="skip teams with fewer games in their latest season")
    ap.add_argument("--season", help="only teams whose latest season is this year, e.g. 2026")
    args = ap.parse_args()

    rows, champ_ids = load_team_games()
    league = league_baseline(rows)
    player_picks = load_player_picks({r["game_id"] for r in rows})

    by_team = defaultdict(list)
    for r in rows:
        by_team[r["team_id"]].append(r)
    lcs26 = {r["team_id"] for r in rows if r["event"].startswith("LCS") and r["season"] == "2026"}

    (OUT / "teams").mkdir(parents=True, exist_ok=True)
    index = []
    for tid, trs in by_team.items():
        season = max(r["season"] for r in trs)
        if args.season and season != args.season:
            continue
        n = sum(r["season"] == season for r in trs)
        if n < args.min_games and tid not in lcs26:
            continue
        rep = team_report(tid, trs, champ_ids, league, player_picks)
        with open(OUT / "teams" / f"{tid}.json", "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, separators=(",", ":"))
        league_name = rep["team"]["events"][-1].split(" - ")[0]
        index.append({
            "id": tid, "name": rep["team"]["name"], "season": season, "league": league_name,
            "lcs_2026": tid in lcs26, "series": rep["sample"]["series"], "games": rep["sample"]["games"],
            "win_rate": rep["sample"]["win_rate"], "file": f"teams/{tid}.json",
            "headline": rep["insights"][0]["text"] if rep["insights"] else "",
        })
    index.sort(key=lambda t: (not t["lcs_2026"], t["name"] != "Cloud9 Kia", -t["games"]))

    seasons = {}
    for s, b in league.items():
        top = sorted(b["presence"].items(), key=lambda kv: -kv[1])[:15]
        seasons[s] = {"games": b["games"], "g3_new_share": round(b["g3_new_share"], 3) if b["g3_new_share"] else None,
                      "top_presence": [{"champion": c, "rate": round(v, 3)} for c, v in top]}
    with open(OUT / "index.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "source": "GRID esports data (Sky's The Limit 2026 starter); aggregates only",
                   "teams": index, "league": seasons}, f, ensure_ascii=False, indent=1)
    with open(OUT / "champions.json", "w", encoding="utf-8") as f:
        json.dump(champion_roster(champ_ids), f, ensure_ascii=False)
    print(f"{len(index)} team reports ({sum(t['lcs_2026'] for t in index)} LCS 2026) -> {OUT}")


if __name__ == "__main__":
    main()
