import { describe, expect, it } from "vitest";
import { winProbability, pickImpact } from "./model.js";

const mockModel = {
  coef: { elo: 1.2, draft: 0.8, blue: 0.3, first_pick: 0.15 },
  teams: {
    "1": { name: "Alpha", games: 20, rating: 1600 },
    "2": { name: "Bravo", games: 20, rating: 1400 },
  },
  champions: {
    "GodChamp": { games: 30, wins: 24, strength: 1.5 },
    "WeakChamp": { games: 30, wins: 10, strength: -1.2 },
    "NeutralChamp": { games: 30, wins: 15, strength: 0.0 },
  },
};

describe("winProbability", () => {
  it("returns probability between 0 and 1", () => {
    const { p } = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    expect(p).toBeGreaterThanOrEqual(0);
    expect(p).toBeLessThanOrEqual(1);
  });

  it("favors the higher-Elo team", () => {
    const high = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    const low = winProbability(mockModel, {
      blueTeamId: "2",
      redTeamId: "1",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    expect(high.p).toBeGreaterThan(low.p);
  });

  it("strong champion picks increase the picking team's probability", () => {
    const base = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    const withGod = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: ["GodChamp"],
      redPicks: [],
      blueFirstPick: true,
    });
    expect(withGod.p).toBeGreaterThan(base.p);
  });

  it("handles unknown teams with default rating 1500", () => {
    const { p } = winProbability(mockModel, {
      blueTeamId: "unknown",
      redTeamId: "unknown",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    });
    // With equal Elo (1500 each), the probability is driven by side + first_pick coefficients
    // so it won't be exactly 0.5, but should be > 0.5 (blue advantage + first pick)
    expect(p).toBeGreaterThan(0.5);
    expect(p).toBeLessThan(1);
  });

  it("handles unknown champions with strength 0", () => {
    const { p } = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: ["UnknownChamp"],
      redPicks: [],
      blueFirstPick: true,
    });
    expect(p).toBeGreaterThan(0);
    expect(p).toBeLessThan(1);
  });

  it("returns parts that sum to the log-odds", () => {
    const { p, parts } = winProbability(mockModel, {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: ["GodChamp"],
      redPicks: ["WeakChamp"],
      blueFirstPick: true,
    });
    const z = parts.elo + parts.draft + parts.side + parts.firstPick;
    const expectedP = 1 / (1 + Math.exp(-z));
    expect(p).toBeCloseTo(expectedP, 5);
  });
});

describe("pickImpact", () => {
  it("strong champion has positive impact for the picking team", () => {
    const state = {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    };
    const impact = pickImpact(mockModel, state, "GodChamp", "blue");
    expect(impact).toBeGreaterThan(0);
  });

  it("weak champion has negative impact for the picking team", () => {
    const state = {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    };
    const impact = pickImpact(mockModel, state, "WeakChamp", "blue");
    expect(impact).toBeLessThan(0);
  });

  it("red picking strong champ has positive impact for red", () => {
    const state = {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    };
    const impact = pickImpact(mockModel, state, "GodChamp", "red");
    expect(impact).toBeGreaterThan(0);
  });

  it("neutral champion has near-zero impact", () => {
    const state = {
      blueTeamId: "1",
      redTeamId: "2",
      bluePicks: [],
      redPicks: [],
      blueFirstPick: true,
    };
    const impact = pickImpact(mockModel, state, "NeutralChamp", "blue");
    expect(Math.abs(impact)).toBeLessThan(0.01);
  });
});
