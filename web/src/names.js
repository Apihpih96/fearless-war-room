// Pure helpers for displaying short team names in narrow UI spaces.
// Used by WinBar, TeamColumn headers, and step line at phone widths.

/**
 * Known short name mappings for common team names.
 */
const SHORT_NAMES = {
  "Cloud9 Kia": "C9 Kia",
  "Cloud9 2027 (reported)": "C9 2027",
  "Team Liquid Alienware": "TL",
  "Shopify Rebellion": "SR",
  "Maryville University": "MVU",
  "Cupid Esports": "CUP",
};

/**
 * Return a short version of a team name suitable for narrow displays.
 * Rules:
 *  - If the name is in SHORT_NAMES, use that.
 *  - If the name contains "Cloud9" or "cloud9", return "C9" + the rest (trimmed).
 *  - Otherwise truncate to ~12 chars, preserving word boundaries.
 *
 * @param {string} name - Full team name
 * @returns {string} Short name
 */
export function shortName(name) {
  if (!name || typeof name !== "string") return "?";

  // Exact match first
  if (SHORT_NAMES[name]) return SHORT_NAMES[name];

  // Cloud9 variants
  if (/cloud9/i.test(name)) {
    const rest = name.replace(/cloud9/gi, "").trim();
    return rest ? `C9 ${rest}` : "C9";
  }

  // Truncate to ~12 chars at a word boundary
  if (name.length <= 12) return name;
  const truncated = name.slice(0, 13);
  const lastSpace = truncated.lastIndexOf(" ");
  return lastSpace > 3 ? truncated.slice(0, lastSpace) : truncated;
}

/**
 * Check if a short name differs from the full name (i.e., shortening was applied).
 */
export function needsShortening(name) {
  return shortName(name) !== name;
}
