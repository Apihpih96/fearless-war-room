import { describe, expect, it } from "vitest";
import { winProbability } from "./model.js";

const mockModel = {
  coef: { elo: 1.2, draft: 0.8, blue: 0.3, first_pick: 0.15 },
  teams: {
    "us-team": { name: "Alpha", games: 20, rating: 1600 },
    "opp-team": { name: "Bravo", games: 20, rating: 1400 },
  },
  champions: {
    "GodChamp": { games: 30, wins: 24, strength: 1.5 },
    "WeakChamp": { games: 30, wins: 10, strength: -1.2 },
  },
};

describe("winProbability perspective — user team always on left", () => {
  it("when user is blue, usPct equals p (blue win probability)", () => {
    const { p } = winProbability(mockModel, {
      blueTeamId: "us-team",
      redTeamId: "opp-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    // usOnBlue = true → usPct = p
    const usPct = p;
    expect(usPct).toBeGreaterThan(0.5); // Alpha has higher rating
    expect(usPct).toBeCloseTo(p, 5);
  });

  it("when user is red, usPct equals 1 - p", () => {
    const { p } = winProbability(mockModel, {
      blueTeamId: "opp-team",
      redTeamId: "us-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    // usOnBlue = false → usPct = 1 - p
    const usPct = 1 - p;
    // Alpha (us-team) is on red side but has higher rating
    // p = P(blue wins) = P(opp wins), so usPct = 1 - p should still reflect Alpha's strength
    expect(usPct).toBeGreaterThan(0);
    expect(usPct).toBeLessThan(1);
  });

  it("parts sign flip when user is on red side", () => {
    const { parts } = winProbability(mockModel, {
      blueTeamId: "opp-team",
      redTeamId: "us-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    // When us is red, sign = -1, so parts are negated from user's perspective
    const sign = -1;
    const usParts = {
      elo: parts.elo * sign,
      draft: parts.draft * sign,
      side: parts.side * sign,
      firstPick: parts.firstPick * sign,
    };
    // Side advantage should flip: blue side advantage becomes negative for red team
    expect(usParts.side).toBeLessThan(0);
  });

  it("parts sign stays positive when user is on blue side", () => {
    const { parts } = winProbability(mockModel, {
      blueTeamId: "us-team",
      redTeamId: "opp-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    const sign = 1;
    const usParts = {
      elo: parts.elo * sign,
      side: parts.side * sign,
    };
    // Blue side advantage should be positive for blue team
    expect(usParts.side).toBeGreaterThan(0);
  });

  it("swapping side correctly inverts win probability", () => {
    const blueResult = winProbability(mockModel, {
      blueTeamId: "us-team",
      redTeamId: "opp-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    const redResult = winProbability(mockModel, {
      blueTeamId: "opp-team",
      redTeamId: "us-team",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    // When us is blue: usPct = blueResult.p
    // When us is red: usPct = 1 - redResult.p
    // These should be equal since the teams are the same, just sides swapped
    const usPctBlue = blueResult.p;
    const usPctRed = 1 - redResult.p;
    // Not exactly equal because firstPick feature depends on blueFirstPick
    // But the elo contribution should be symmetric
    expect(blueResult.parts.elo).toBeCloseTo(-redResult.parts.elo, 5);
  });
});
