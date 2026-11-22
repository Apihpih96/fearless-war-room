// Turns a team's scouting report (pipeline/build_scout.py output) into live,
// availability-aware suggestions for the current game of a Fearless series.

const byName = (report) => Object.fromEntries((report?.champions || []).map((c) => [c.champion, c]));

/**
 * Likely picks for `report`'s team in this game, skipping anything unavailable.
 * Score = this game-number's pick rate (weighted) + season pick rate, plus a boost
 * for the champion their player goes to when a G1 favorite is burned.
 */
export function likelyPicks(report, bucket, blocked, n = 8) {
  if (!report) return [];
  const champs = byName(report);
  const scores = new Map();
  const why = new Map();
  const add = (c, s, reason, override = false) => {
    if (blocked.has(c)) return;
    scores.set(c, (scores.get(c) || 0) + s);
    if (reason && (override || !why.has(c))) why.set(c, reason);
  };
  for (const c of report.champions) {
    const b = c.by_bucket[bucket]?.picks;
    if (b?.n) add(c.champion, 2 * b.rate, `${b.label} ${bucket}s`);
    if (c.picks.n) add(c.champion, c.picks.rate, `${c.picks.label} games`);
  }
  for (const fav of report.fearless?.when_favorites_locked || []) {
    if (!blocked.has(fav.champion)) continue; // favorite still open: no replacement needed
    for (const r of fav.replacements.slice(0, 3)) {
      add(r.champion, 1.5 * r.rate, `${fav.player || "they"} → ${r.champion} when ${fav.champion} is gone (${r.label})`, true);
    }
  }
  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([champion, s]) => ({ champion, score: s, reason: why.get(champion), record: champs[champion]?.picks.record }));
}

/** Likely bans by `report`'s team in this game. */
export function likelyBans(report, bucket, blocked, n = 6) {
  if (!report) return [];
  return report.champions
    .filter((c) => !blocked.has(c.champion))
    .map((c) => {
      const b = c.by_bucket[bucket]?.bans || { n: 0, rate: 0, label: "0/0" };
      return { champion: c.champion, score: 2 * b.rate + c.bans.rate, reason: `${b.label} ${bucket}s` };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, n);
}

/** The team's G1 favorites with their Fearless status. */
export function favoritesStatus(report, burned, bannedNow) {
  return (report?.fearless?.when_favorites_locked || []).map((f) => ({
    ...f,
    status: burned.has(f.champion) ? "burned" : bannedNow.has(f.champion) ? "banned" : "open",
  }));
}

/**
 * Contested champions: high on both teams' likely-pick lists. These are the
 * "take it or ban it before they do" calls (the save/burn advisor in step 4 goes deeper).
 */
export function contested(usPicks, oppPicks) {
  const opp = new Map(oppPicks.map((p) => [p.champion, p]));
  return usPicks.filter((p) => opp.has(p.champion)).map((p) => ({ champion: p.champion, us: p, opp: opp.get(p.champion) }));
}
