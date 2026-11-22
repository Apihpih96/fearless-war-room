// Pure win-probability model functions.
// Reads the model.json produced by pipeline/build_model.py and computes
// the probability that the blue team wins given the current draft state.

function sigmoid(x) {
  if (x >= 0) return 1 / (1 + Math.exp(-x));
  const ex = Math.exp(x);
  return ex / (1 + ex);
}

/**
 * Compute win probability for the blue team.
 *
 * @param {object} model - model.json contents
 * @param {object} state
 * @param {string} state.blueTeamId
 * @param {string} state.redTeamId
 * @param {string[]} state.bluePicks - champion names picked by blue
 * @param {string[]} state.redPicks - champion names picked by red
 * @param {boolean} state.blueFirstPick - true if blue had first pick
 * @returns {{p: number, parts: {elo: number, draft: number, side: number, firstPick: number}}}
 */
export function winProbability(model, { blueTeamId, redTeamId, bluePicks, redPicks, blueFirstPick }) {
  const coef = model.coef || {};
  const teams = model.teams || {};
  const champs = model.champions || {};

  // Elo feature
  const blueRating = (teams[blueTeamId] || {}).rating ?? 1500;
  const redRating = (teams[redTeamId] || {}).rating ?? 1500;
  const eloFeat = (blueRating - redRating) / 400;

  // Draft feature: mean champion strength difference
  const blueMean = bluePicks.length
    ? bluePicks.reduce((s, c) => s + ((champs[c] || {}).strength ?? 0), 0) / bluePicks.length
    : 0;
  const redMean = redPicks.length
    ? redPicks.reduce((s, c) => s + ((champs[c] || {}).strength ?? 0), 0) / redPicks.length
    : 0;
  const draftFeat = blueMean - redMean;

  // Blue side intercept
  const blueFeat = 1;

  // First pick feature
  const fpFeat = blueFirstPick ? 1 : -1;

  // Linear combination
  const z = (coef.elo ?? 0) * eloFeat
          + (coef.draft ?? 0) * draftFeat
          + (coef.blue ?? 0) * blueFeat
          + (coef.first_pick ?? 0) * fpFeat;

  const p = sigmoid(z);

  return {
    p,
    parts: {
      elo: (coef.elo ?? 0) * eloFeat,
      draft: (coef.draft ?? 0) * draftFeat,
      side: (coef.blue ?? 0) * blueFeat,
      firstPick: (coef.first_pick ?? 0) * fpFeat,
    },
  };
}

/**
 * How much the win probability for `team` ("blue" or "red") changes
 * if they pick `champion` now.
 *
 * @param {object} model
 * @param {object} state - same shape as winProbability's state
 * @param {string} champion
 * @param {"blue"|"red"} team
 * @returns {number} delta in win probability for `team`
 */
export function pickImpact(model, state, champion, team) {
  const { blueTeamId, redTeamId, bluePicks, redPicks, blueFirstPick } = state;

  // Current probability for blue
  const before = winProbability(model, state);

  // Add champion to the appropriate team's picks
  const newBluePicks = team === "blue" ? [...bluePicks, champion] : [...bluePicks];
  const newRedPicks = team === "red" ? [...redPicks, champion] : [...redPicks];

  const after = winProbability(model, {
    blueTeamId,
    redTeamId,
    bluePicks: newBluePicks,
    redPicks: newRedPicks,
    blueFirstPick,
  });

  // Return impact for the specified team
  if (team === "blue") {
    return after.p - before.p;
  }
  // For red, impact is the negative of blue's change
  return -(after.p - before.p);
}
