// demo.js – pure logic for the guided demo mode.
//
// Contains:
//  1. A hard-coded illustrative Fearless draft script (NOT from any real game).
//  2. Validation that replays the script and checks every action is legal.
//  3. Step/advance helpers used by the React demo player.

import {
  ORDER, newSeries, select, setWinner, addGame, nextStep,
  burnedBefore, seriesWinner, teamAt,
} from "./draft.js";

// ---------------------------------------------------------------------------
// Script definition
// ---------------------------------------------------------------------------
// Each action: { type: "pick" | "ban", champion: string, team: "us" | "opp" }
// The script is designed to be plausible and to demonstrate Fearless burns.
//
// G1: full 20-step draft (10 bans + 10 picks)
// G2: partial draft showing burned champions from G1

const DEMO_SCRIPT = {
  us: "c9-2027",
  opp: "54198", // LYON
  format: 3,
  games: [
    // G1 – full draft
    {
      firstPick: "us",
      usSide: "blue",
      winner: "us",
      actions: [
        // Ban phase 1 (seq 1-6)
        { seq: 1, type: "ban", team: "us",  champion: "Aatrox" },
        { seq: 2, type: "ban", team: "opp", champion: "K'Sante" },
        { seq: 3, type: "ban", team: "us",  champion: "Maokai" },
        { seq: 4, type: "ban", team: "opp", champion: "Renata" },
        { seq: 5, type: "ban", team: "us",  champion: "Xin Zhao" },
        { seq: 6, type: "ban", team: "opp", champion: "Briar" },
        // Pick phase 1 (seq 7-12)
        { seq: 7,  type: "pick", team: "us",  champion: "Azir" },
        { seq: 8,  type: "pick", team: "opp", champion: "Jax" },
        { seq: 9,  type: "pick", team: "opp", champion: "Graves" },
        { seq: 10, type: "pick", team: "us",  champion: "Viego" },
        { seq: 11, type: "pick", team: "us",  champion: "Orianna" },
        { seq: 12, type: "pick", team: "opp", champion: "Jinx" },
        // Ban phase 2 (seq 13-16)
        { seq: 13, type: "ban", team: "opp", champion: "Rell" },
        { seq: 14, type: "ban", team: "us",  champion: "Nautilus" },
        { seq: 15, type: "ban", team: "opp", champion: "Thresh" },
        { seq: 16, type: "ban", team: "us",  champion: "Leona" },
        // Pick phase 2 (seq 17-20)
        { seq: 17, type: "pick", team: "opp", champion: "Rakan" },
        { seq: 18, type: "pick", team: "us",  champion: "Bard" },
        { seq: 19, type: "pick", team: "us",  champion: "Kalista" },
        { seq: 20, type: "pick", team: "opp", champion: "Senna" },
      ],
    },
    // G2 – partial draft (8 steps), demonstrating burned champions
    {
      firstPick: "opp", // loser of G1 gets first selection
      usSide: "red",
      winner: null,
      actions: [
        // Ban phase 1 (seq 1-6) – bans reset each game
        { seq: 1, type: "ban", team: "opp", champion: "Aatrox" },
        { seq: 2, type: "ban", team: "us",  champion: "K'Sante" },
        { seq: 3, type: "ban", team: "opp", champion: "Maokai" },
        { seq: 4, type: "ban", team: "us",  champion: "Renata" },
        { seq: 5, type: "ban", team: "opp", champion: "Briar" },
        { seq: 6, type: "ban", team: "us",  champion: "Xin Zhao" },
        // Pick phase 1 starts (seq 7-8)
        { seq: 7, type: "pick", team: "opp", champion: "Fiora" },
        { seq: 8, type: "pick", team: "us",  champion: "Irelia" },
      ],
    },
  ],
};

// ---------------------------------------------------------------------------
// Captions for each step (indexed by flat step index across all games)
// ---------------------------------------------------------------------------
const CAPTIONS = [
  // G1 bans
  "G1: Cloud9 2027 bans Aatrox",
  "LYON bans K'Sante",
  "Cloud9 2027 bans Maokai",
  "LYON bans Renata",
  "Cloud9 2027 bans Xin Zhao",
  "LYON bans Briar",
  // G1 picks
  "G1: Cloud9 2027 first picks Azir",
  "LYON picks Jax top",
  "LYON picks Graves jungle",
  "Cloud9 2027 picks Viego jungle",
  "Cloud9 2027 picks Orianna mid",
  "LYON picks Jinx bot",
  // G1 bans 2
  "LYON bans Rell",
  "Cloud9 2027 bans Nautilus",
  "LYON bans Thresh",
  "Cloud9 2027 bans Leona",
  // G1 picks 2
  "LYON picks Rakan support",
  "Cloud9 2027 picks Bard support",
  "Cloud9 2027 picks Kalista bot",
  "LYON picks Senna bot",
  // Between games
  "G1 complete – Cloud9 2027 wins. All 10 picks are now burned for G2.",
  // G2
  "G2: everything picked in G1 is burned for both teams",
  "G2: LYON has first selection, bans Aatrox (bans reset each game)",
  "Cloud9 2027 bans K'Sante",
  "LYON bans Maokai",
  "Cloud9 2027 bans Renata",
  "LYON bans Briar",
  "Cloud9 2027 bans Xin Zhao",
  "G2: LYON first picks Fiora (Azir is burned)",
  "Advisor: Deny Xin Zhao, LYON's top pick",
  "Cloud9 2027 picks Irelia – Win probability moves with each pick",
];

// ---------------------------------------------------------------------------
// Validation: replay the script and verify every action is legal
// ---------------------------------------------------------------------------

/**
 * Build a series by replaying the demo script. Throws on any illegal action.
 * Returns the final series state.
 */
export function validateScript() {
  let series = newSeries({
    us: DEMO_SCRIPT.us,
    opp: DEMO_SCRIPT.opp,
    format: DEMO_SCRIPT.format,
  });

  for (let gi = 0; gi < DEMO_SCRIPT.games.length; gi++) {
    const gDef = DEMO_SCRIPT.games[gi];

    // Set firstPick and side
    series = { ...series, games: series.games.map((g, i) => {
      if (i !== series.current) return g;
      return { ...g, firstPick: gDef.firstPick, usSide: gDef.usSide };
    })};

    // Apply actions in order
    for (const act of gDef.actions) {
      const step = nextStep(series.games[series.current]);
      if (step === -1) {
        throw new Error(`Game ${gi + 1}: draft already complete at action seq ${act.seq}`);
      }
      // Verify the action matches the expected step
      const orderEntry = ORDER[step];
      if (orderEntry.type !== act.type) {
        throw new Error(
          `Game ${gi + 1}, step ${step + 1}: expected ${orderEntry.type} but script has ${act.type}`
        );
      }
      const expectedTeam = teamAt(series.games[series.current], step + 1);
      if (expectedTeam !== act.team) {
        throw new Error(
          `Game ${gi + 1}, step ${step + 1}: expected team ${expectedTeam} but script has ${act.team}`
        );
      }
      series = select(series, act.champion);
    }

    // If there's a next game, set winner and add it
    if (gi < DEMO_SCRIPT.games.length - 1) {
      series = setWinner(series, gDef.winner);
      series = addGame(series);
    } else if (gDef.winner) {
      series = setWinner(series, gDef.winner);
    }
  }

  return series;
}

/**
 * Return the flat list of all actions across all games in the script.
 * Each entry: { gameIndex, seq, type, team, champion, caption }
 */
export function getDemoSteps() {
  const steps = [];
  let captionIdx = 0;

  for (let gi = 0; gi < DEMO_SCRIPT.games.length; gi++) {
    const gDef = DEMO_SCRIPT.games[gi];
    for (const act of gDef.actions) {
      steps.push({
        gameIndex: gi,
        seq: act.seq,
        type: act.type,
        team: act.team,
        champion: act.champion,
        caption: CAPTIONS[captionIdx] || "",
      });
      captionIdx++;
    }
    // Add the inter-game caption if there is one
    if (gi < DEMO_SCRIPT.games.length - 1 && captionIdx < CAPTIONS.length) {
      steps.push({
        gameIndex: gi,
        seq: -1, // inter-game marker
        type: "game-end",
        team: null,
        champion: null,
        caption: CAPTIONS[captionIdx],
      });
      captionIdx++;
    }
  }

  return steps;
}

/**
 * Build the series state after applying the first `n` demo steps.
 * Used by the demo player to render the board at any point.
 */
export function buildSeriesAtStep(n) {
  let series = newSeries({
    us: DEMO_SCRIPT.us,
    opp: DEMO_SCRIPT.opp,
    format: DEMO_SCRIPT.format,
  });

  const steps = getDemoSteps();
  let stepIdx = 0;

  for (let gi = 0; gi < DEMO_SCRIPT.games.length && stepIdx < n; gi++) {
    const gDef = DEMO_SCRIPT.games[gi];

    // Set firstPick and side
    series = { ...series, games: series.games.map((g, i) => {
      if (i !== series.current) return g;
      return { ...g, firstPick: gDef.firstPick, usSide: gDef.usSide };
    })};

    for (const act of gDef.actions) {
      if (stepIdx >= n) break;
      // Skip inter-game markers
      const currentStep = steps[stepIdx];
      if (currentStep && currentStep.type === "game-end") {
        stepIdx++;
        continue;
      }
      series = select(series, act.champion);
      stepIdx++;
    }

    // Handle game-end transition
    if (stepIdx < n && gi < DEMO_SCRIPT.games.length - 1) {
      const nextStepEntry = steps[stepIdx];
      if (nextStepEntry && nextStepEntry.type === "game-end") {
        series = setWinner(series, gDef.winner);
        series = addGame(series);
        stepIdx++;
      }
    }
  }

  return series;
}

/**
 * Total number of demo steps (including inter-game markers).
 */
export function totalDemoSteps() {
  return getDemoSteps().length;
}

/**
 * Get the caption for a given step index.
 */
export function getCaption(stepIndex) {
  const steps = getDemoSteps();
  if (stepIndex < 0 || stepIndex >= steps.length) return "";
  return steps[stepIndex].caption;
}

/**
 * Check if a step is an inter-game transition.
 */
export function isGameTransition(stepIndex) {
  const steps = getDemoSteps();
  if (stepIndex < 0 || stepIndex >= steps.length) return false;
  return steps[stepIndex].type === "game-end";
}
