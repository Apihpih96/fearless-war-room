"""
Fearless War Room - Step 4: win-probability model.

Reads cache/drafts.csv + cache/games.csv and writes aggregate model JSON:

    web/public/data/model.json

Contains ONLY aggregates (champion strengths, team Elo ratings, logistic
regression coefficients, cross-validation metrics).  No per-game rows are
written, so the output is safe to commit under the GRID license.

Usage:
    python pipeline/build_model.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import pathlib
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path(os.environ.get("FWR_CACHE_DIR", ROOT / "cache"))
OUT = pathlib.Path(os.environ.get("FWR_OUT_DIR", ROOT / "web" / "public" / "data"))


# ---------------------------------------------------------------- helpers
def split(s: str) -> list[str]:
    return [x for x in s.split("|") if x]


def day(s: str) -> str:
    """Extract YYYY-MM-DD from a date string."""
    for i in range(len(s) - 9):
        sub = s[i:i+10]
        if len(sub) == 10 and sub[4] == '-' and sub[7] == '-':
            return sub
    return ""


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        return ex / (1.0 + ex)


def logit(p: float, eps: float = 1e-7) -> float:
    p = max(eps, min(1 - eps, p))
    return math.log(p / (1 - p))


# ---------------------------------------------------------------- load
def load_games():
    """Return list of game dicts from games.csv, sorted by date."""
    if not (CACHE / "games.csv").exists():
        sys.exit(f"cache/games.csv not found. Run pipeline/extract_drafts.py first.")
    rows = list(csv.DictReader(open(CACHE / "games.csv", encoding="utf-8")))
    rows.sort(key=lambda r: day(r.get("date", "")))
    return rows


def load_draft_actions():
    """Return dict game_id -> list of action dicts from drafts.csv."""
    if not (CACHE / "drafts.csv").exists():
        sys.exit(f"cache/drafts.csv not found. Run pipeline/extract_drafts.py first.")
    actions = defaultdict(list)
    for a in csv.DictReader(open(CACHE / "drafts.csv", encoding="utf-8")):
        actions[a["game_id"]].append(a)
    return actions


# ---------------------------------------------------------------- champion strength
def compute_champion_strengths(games: list[dict]) -> dict:
    """
    For each champion: games played, wins, and Bayesian-shrunk strength.
    strength = logit((wins + 10*0.5) / (games + 10))
    """
    champ_wins = Counter()
    champ_games = Counter()
    for g in games:
        winner = g["winner_id"]
        for champ in split(g.get("blue_picks", "")) + split(g.get("red_picks", "")):
            champ_games[champ] += 1
        # Determine which champs won
        blue_picks = set(split(g.get("blue_picks", "")))
        red_picks = set(split(g.get("red_picks", "")))
        winning_picks = blue_picks if g.get("blue_id") == winner else red_picks
        for champ in winning_picks:
            champ_wins[champ] += 1

    result = {}
    for champ in champ_games:
        g = champ_games[champ]
        w = champ_wins[champ]
        shrunk = (w + 10 * 0.5) / (g + 10)
        result[champ] = {
            "games": g,
            "wins": w,
            "strength": round(logit(shrunk), 6),
        }
    return result


# ---------------------------------------------------------------- team Elo
def compute_team_elo(games: list[dict]) -> dict:
    """
    Run Elo (K=24, start 1500) over games in date order.
    Return {team_id: {name, games, rating}}.
    """
    K = 24
    ratings = {}  # team_id -> current rating

    def ensure(tid, name):
        if tid not in ratings:
            ratings[tid] = {"name": name, "games": 0, "rating": 1500.0}

    for g in games:
        blue = g["blue_id"]
        red = g["red_id"]
        winner = g["winner_id"]
        ensure(blue, g["blue_name"])
        ensure(red, g["red_name"])

        r_blue = ratings[blue]["rating"]
        r_red = ratings[red]["rating"]

        expected_blue = 1.0 / (1.0 + math.exp(-(r_blue - r_red) / 400))
        expected_red = 1.0 - expected_blue

        actual_blue = 1.0 if winner == blue else 0.0
        actual_red = 1.0 if winner == red else 0.0

        ratings[blue]["rating"] += K * (actual_blue - expected_blue)
        ratings[red]["rating"] += K * (actual_red - expected_red)
        ratings[blue]["games"] += 1
        ratings[red]["games"] += 1

    # Round ratings
    for tid in ratings:
        ratings[tid]["rating"] = round(ratings[tid]["rating"], 2)
    return ratings


# ---------------------------------------------------------------- feature extraction
def extract_features(g, champ_strengths, team_ratings, all_games):
    """
    Extract features for a single game from blue team's perspective.
    Uses leave-one-game-out champion stats (subtract this game's result).
    Returns (features, label) where label = 1 if blue won.
    """
    blue = g["blue_id"]
    red = g["red_id"]
    winner = g["winner_id"]
    label = 1.0 if winner == blue else 0.0

    # Elo feature: ratings BEFORE this game
    blue_rating = team_ratings.get(blue, {}).get("rating", 1500.0)
    red_rating = team_ratings.get(red, {}).get("rating", 1500.0)
    elo_feat = (blue_rating - red_rating) / 400.0

    # Draft feature: mean champion strength difference (leave-one-game-out)
    blue_picks = split(g.get("blue_picks", ""))
    red_picks = split(g.get("red_picks", ""))

    # Compute leave-one-game-out strengths
    def loo_strength(champ):
        cs = champ_strengths.get(champ, {})
        cg = cs.get("games", 0)
        cw = cs.get("wins", 0)
        if cg == 0:
            return 0.0
        # Subtract this game's contribution
        if champ in blue_picks:
            cw_loo = cw - (1 if winner == blue else 0)
        elif champ in red_picks:
            cw_loo = cw - (1 if winner == red else 0)
        else:
            cw_loo = cw
        cg_loo = cg - 1
        if cg_loo <= 0:
            return 0.0
        shrunk = (cw_loo + 10 * 0.5) / (cg_loo + 10)
        return logit(shrunk)

    blue_mean = sum(loo_strength(c) for c in blue_picks) / max(len(blue_picks), 1)
    red_mean = sum(loo_strength(c) for c in red_picks) / max(len(red_picks), 1)
    draft_feat = blue_mean - red_mean

    # Blue side intercept
    blue_feat = 1.0

    # First pick feature: determine from draft actions
    first_pick = g.get("_first_pick_blue", "0")
    first_pick_feat = 1.0 if first_pick == "1" else -1.0

    return [elo_feat, draft_feat, blue_feat, first_pick_feat], label


# ---------------------------------------------------------------- logistic regression
def fit_logistic(X, y, lr=0.1, iters=2000, l2=1e-3):
    """Plain gradient descent logistic regression with L2 regularization."""
    n_features = len(X[0])
    w = [0.0] * n_features

    for _ in range(iters):
        n = len(X)
        grad = [0.0] * n_features
        for i in range(n):
            z = sum(w[j] * X[i][j] for j in range(n_features))
            pred = sigmoid(z)
            err = pred - y[i]
            for j in range(n_features):
                grad[j] += err * X[i][j]
        # Average gradient + L2
        for j in range(n_features):
            w[j] -= lr * (grad[j] / n + l2 * w[j])

    return w


def cross_validate(games, champ_strengths, team_ratings, n_folds=5, seed=7):
    """
    5-fold CV grouped by series_id.
    Returns {games, log_loss, accuracy, baseline_log_loss}.
    """
    random.seed(seed)

    # Group by series
    series_groups = defaultdict(list)
    for g in games:
        series_groups[g["series_id"]].append(g)

    series_ids = list(series_groups.keys())
    random.shuffle(series_ids)

    # Split series into folds
    folds = [[] for _ in range(n_folds)]
    for i, sid in enumerate(series_ids):
        folds[i % n_folds].append(sid)

    total_ll = 0.0
    total_bll = 0.0
    total_correct = 0
    total_games = 0

    for fold_idx in range(n_folds):
        val_series = set(folds[fold_idx])
        train_games = [g for g in games if g["series_id"] not in val_series]
        val_games = [g for g in games if g["series_id"] in val_series]

        if not train_games or not val_games:
            continue

        # Compute champion strengths and Elo from training data
        train_champ = compute_champion_strengths(train_games)
        train_elo = compute_team_elo(train_games)

        # Build feature matrix
        X_train = []
        y_train = []
        for g in train_games:
            feat, lab = extract_features(g, train_champ, train_elo, train_games)
            X_train.append(feat)
            y_train.append(lab)

        # Fit model
        w = fit_logistic(X_train, y_train)

        # Evaluate on validation
        for g in val_games:
            feat, lab = extract_features(g, train_champ, train_elo, train_games)
            z = sum(w[j] * feat[j] for j in range(len(w)))
            pred = sigmoid(z)
            pred = max(1e-7, min(1 - 1e-7, pred))

            ll = -(lab * math.log(pred) + (1 - lab) * math.log(1 - pred))
            total_ll += ll

            # Baseline: always predict 0.5
            bll = -(lab * math.log(0.5) + (1 - lab) * math.log(0.5))
            total_bll += bll

            if (pred >= 0.5 and lab == 1) or (pred < 0.5 and lab == 0):
                total_correct += 1
            total_games += 1

    return {
        "games": total_games,
        "log_loss": round(total_ll / max(total_games, 1), 6),
        "accuracy": round(total_correct / max(total_games, 1), 4),
        "baseline_log_loss": round(total_bll / max(total_games, 1), 6),
    }


# ---------------------------------------------------------------- first pick detection
def detect_first_picks(draft_actions):
    """
    For each game, determine if blue had first pick.
    First pick = team with the lowest-seq pick action.
    Returns dict game_id -> bool (True if blue had first pick).
    """
    result = {}
    for gid, acts in draft_actions.items():
        picks = [a for a in acts if a["action"] == "pick"]
        if not picks:
            continue
        picks.sort(key=lambda a: int(a["seq"]))
        first_picker = picks[0]["team_id"]
        # Find the game to know which side is blue
        result[gid] = first_picker  # store team_id of first picker
    return result


# ---------------------------------------------------------------- main
def main():
    games = load_games()
    draft_actions = load_draft_actions()

    # Detect first pick per game
    first_pick_map = detect_first_picks(draft_actions)

    # Annotate games with first pick info
    for g in games:
        gid = g["game_id"]
        fp_team = first_pick_map.get(gid, "")
        g["_first_pick_blue"] = "1" if fp_team == g["blue_id"] else "0"

    # Champion strengths
    champ_strengths = compute_champion_strengths(games)

    # Team Elo
    team_ratings = compute_team_elo(games)

    # Full-dataset logistic regression coefficients
    X_all = []
    y_all = []
    for g in games:
        feat, lab = extract_features(g, champ_strengths, team_ratings, games)
        X_all.append(feat)
        y_all.append(lab)

    coef = fit_logistic(X_all, y_all)
    coef_names = ["elo", "draft", "blue", "first_pick"]

    # Cross-validation metrics
    metrics = cross_validate(games, champ_strengths, team_ratings)

    # Collect patches and events
    patches = sorted(set(g.get("patch", "") for g in games))
    events = len(set(g.get("event", "") for g in games))

    model = {
        "champions": champ_strengths,
        "teams": team_ratings,
        "coef": {name: round(w, 6) for name, w in zip(coef_names, coef)},
        "metrics": metrics,
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "patches": patches,
            "events": events,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "model.json", "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    print(f"model.json written: {len(champ_strengths)} champions, {len(team_ratings)} teams, "
          f"CV log_loss={metrics['log_loss']:.4f}, accuracy={metrics['accuracy']:.4f}")


if __name__ == "__main__":
    main()
