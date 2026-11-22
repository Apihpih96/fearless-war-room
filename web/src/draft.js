// Fearless draft rules, kept free of React so they are easy to test.
//
// Hard Fearless (LCS/LCK/LEC 2025-26): a champion PICKED by either team in an
// earlier game of the series cannot be picked by anyone for the rest of it.
// Bans do not carry over.
//
// 2026 First Selection: the team with first selection takes either first pick
// or side, so "who picks first" and "who is blue" are set independently.

/** Tournament draft order. `fp` = the first-pick team, `sp` = the other team. */
export const ORDER = [
  ["fp", "ban"], ["sp", "ban"], ["fp", "ban"], ["sp", "ban"], ["fp", "ban"], ["sp", "ban"],
  ["fp", "pick"], ["sp", "pick"], ["sp", "pick"], ["fp", "pick"], ["fp", "pick"], ["sp", "pick"],
  ["sp", "ban"], ["fp", "ban"], ["sp", "ban"], ["fp", "ban"],
  ["sp", "pick"], ["fp", "pick"], ["fp", "pick"], ["sp", "pick"],
].map(([slot, type], i) => ({ seq: i + 1, slot, type, phase: i < 6 ? "Ban 1" : i < 12 ? "Pick 1" : i < 16 ? "Ban 2" : "Pick 2" }));

export function newGame(firstPick = "us", usSide = "blue") {
  return { firstPick, usSide, actions: Array(ORDER.length).fill(null), winner: null };
}

export function newSeries({ us, opp, format = 3 } = {}) {
  return { us, opp, format, games: [newGame()], current: 0 };
}

/** "us" | "opp" for a draft step of a game. */
export function teamAt(game, seq) {
  const slot = ORDER[seq - 1].slot;
  const other = game.firstPick === "us" ? "opp" : "us";
  return slot === "fp" ? game.firstPick : other;
}

export function sideOf(game, who) {
  if (who === "us") return game.usSide;
  return game.usSide === "blue" ? "red" : "blue";
}

/** Index of the next empty step, or -1 when the draft is complete. */
export function nextStep(game) {
  return game.actions.findIndex((a) => a === null);
}

export function picksOf(game, who) {
  return ORDER.flatMap((s, i) => (s.type === "pick" && teamAt(game, s.seq) === who && game.actions[i] ? [game.actions[i]] : []));
}

export function bansOf(game, who) {
  return ORDER.flatMap((s, i) => (s.type === "ban" && teamAt(game, s.seq) === who && game.actions[i] ? [game.actions[i]] : []));
}

/** Champions burned by Fearless before game `idx`: every pick of every earlier game. */
export function burnedBefore(series, idx = series.current) {
  const out = new Set();
  series.games.slice(0, idx).forEach((g) => {
    ORDER.forEach((s, i) => s.type === "pick" && g.actions[i] && out.add(g.actions[i]));
  });
  return out;
}

/** Everything that cannot be selected right now in game `idx`. */
export function unavailable(series, idx = series.current) {
  const out = burnedBefore(series, idx);
  series.games[idx].actions.forEach((c) => c && out.add(c));
  return out;
}

export function canSelect(series, champion, idx = series.current) {
  const g = series.games[idx];
  return nextStep(g) !== -1 && !unavailable(series, idx).has(champion);
}

const clone = (s) => ({ ...s, games: s.games.map((g) => ({ ...g, actions: [...g.actions] })) });

/** Fill the next step of the current game. Throws on a Fearless or duplicate violation. */
export function select(series, champion) {
  if (!canSelect(series, champion)) throw new Error(`${champion} is not available`);
  const s = clone(series);
  const g = s.games[s.current];
  g.actions[nextStep(g)] = champion;
  return s;
}

export function undo(series) {
  const s = clone(series);
  const g = s.games[s.current];
  const n = nextStep(g);
  const last = n === -1 ? g.actions.length - 1 : n - 1;
  if (last >= 0) g.actions[last] = null;
  g.winner = null;
  return s;
}

export function score(series) {
  return series.games.reduce((acc, g) => (g.winner ? { ...acc, [g.winner]: acc[g.winner] + 1 } : acc), { us: 0, opp: 0 });
}

export function seriesWinner(series) {
  const need = Math.ceil(series.format / 2);
  const sc = score(series);
  return sc.us >= need ? "us" : sc.opp >= need ? "opp" : null;
}

export function setWinner(series, who) {
  const s = clone(series);
  s.games[s.current].winner = who;
  return s;
}

/** Start the next game. Default First Selection goes to the loser of the last game. */
export function addGame(series) {
  if (seriesWinner(series) || series.games.length >= series.format) return series;
  const last = series.games[series.games.length - 1];
  const loser = last.winner === "us" ? "opp" : "us";
  const s = clone(series);
  s.games.push(newGame(loser === "us" ? "us" : "opp", last.usSide));
  s.current = s.games.length - 1;
  return s;
}

export function updateGame(series, patch, idx = series.current) {
  const s = clone(series);
  s.games[idx] = { ...s.games[idx], ...patch };
  return s;
}

/** Fearless game bucket used by the scout data: "G1" | "G2" | "G3+". */
export const bucketOf = (gameIndex) => (gameIndex === 0 ? "G1" : gameIndex === 1 ? "G2" : "G3+");
