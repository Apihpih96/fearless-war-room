// Pure helpers for reported-roster reports (e.g. c9-2027).
// These work with the same report schema as build_scout.py output,
// plus the extra `roster`, `sample.caveats`, and `team.reported` fields.

/** Check if a report is a reported-roster report. */
export function isReportedRoster(report) {
  return !!(report?.team?.reported);
}

/** Get roster flags from a report. */
export function getRosterFlags(report) {
  return report?.roster?.flags || [];
}

/** Get roster label. */
export function getRosterLabel(report) {
  return report?.roster?.label || report?.team?.name || "";
}

/** Build a compact summary for each player in a roster report. */
export function rosterSummary(report) {
  if (!report?.players) return [];
  return report.players.map((p) => ({
    player: p.player,
    role: p.role || "",
    status: p.status || "ok",
    games: p.games || 0,
    teams: p.teams || [],
    uniqueChampions: p.unique_champions || 0,
    top: (p.top || []).slice(0, 3),
  }));
}

/** Check if a team id is the reported roster. */
export function isReportedTeamId(teamId) {
  return teamId === "c9-2027";
}

/** Get the fallback team id for Elo lookup when a reported roster has no Elo. */
export function getEloFallbackTeamId(teamId, model) {
  if (teamId === "c9-2027" && model?.teams?.["47351"]) {
    return "47351";
  }
  return teamId;
}

/** Check if a report has caveats. */
export function hasCaveats(report) {
  return !!(report?.sample?.caveats && report.sample.caveats.length > 0);
}

/** C9 team ids that should never be auto-selected as the default opponent. */
const C9_IDS = new Set(["c9-2027", "47351"]);

/**
 * Pick a sensible default opponent given the "us" team id and the index teams list.
 * Rules:
 *  - Never pick a C9 id (c9-2027 or 47351).
 *  - Prefer the first LCS 2026 team that isn't a C9 id.
 *  - Fall back to the first non‑C9 team overall.
 */
export function defaultOpponent(usId, teams) {
  if (!Array.isArray(teams)) return "";
  // Prefer LCS 2026
  const lcs2026 = teams.find((t) => t.lcs_2026 && !C9_IDS.has(t.id) && t.id !== usId);
  if (lcs2026) return lcs2026.id;
  // Fallback: any team
  const any = teams.find((t) => !C9_IDS.has(t.id) && t.id !== usId);
  return any?.id || "";
}
