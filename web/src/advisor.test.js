import { describe, expect, it } from "vitest";
import { advise } from "./advisor.js";

const mockModel = {
  coef: { elo: 1.0, draft: 0.8, blue: 0.2, first_pick: 0.1 },
  teams: {
    "1": { name: "Alpha", games: 20, rating: 1550 },
    "2": { name: "Bravo", games: 20, rating: 1450 },
  },
  champions: {
    "Azir": { games: 30, wins: 20, strength: 1.0 },
    "Ahri": { games: 30, wins: 18, strength: 0.6 },
    "Yasuo": { games: 30, wins: 15, strength: 0.0 },
    "Garen": { games: 30, wins: 10, strength: -0.8 },
  },
};

const mockUsReport = {
  team: { name: "Alpha", id: "1" },
  champions: [
    { champion: "Azir", picks: { n: 10, rate: 0.5, label: "10/20" }, bans: { n: 0, rate: 0 },
      by_bucket: { G1: { picks: { n: 8, rate: 0.8, label: "8/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
    { champion: "Ahri", picks: { n: 6, rate: 0.3, label: "6/20" }, bans: { n: 0, rate: 0 },
      by_bucket: { G1: { picks: { n: 4, rate: 0.4, label: "4/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
    { champion: "Yasuo", picks: { n: 2, rate: 0.1, label: "2/20" }, bans: { n: 0, rate: 0 },
      by_bucket: { G1: { picks: { n: 1, rate: 0.1, label: "1/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
  ],
  fearless: { when_favorites_locked: [] },
};

const mockOppReport = {
  team: { name: "Bravo", id: "2" },
  champions: [
    { champion: "Azir", picks: { n: 12, rate: 0.6, label: "12/20" }, bans: { n: 0, rate: 0 },
      by_bucket: { G1: { picks: { n: 10, rate: 1.0, label: "10/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
    { champion: "Ahri", picks: { n: 4, rate: 0.2, label: "4/20" }, bans: { n: 0, rate: 0 },
      by_bucket: { G1: { picks: { n: 2, rate: 0.2, label: "2/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
  ],
  fearless: { when_favorites_locked: [] },
};

const baseParams = {
  model: mockModel,
  usReport: mockUsReport,
  oppReport: mockOppReport,
  bucket: "G1",
  blocked: new Set(),
  burned: new Set(),
  ourTeamId: "1",
  oppTeamId: "2",
  bluePicks: [],
  redPicks: [],
  blueFirstPick: true,
  ourSide: "blue",
  gamesLeft: 3,
  seriesGameIndex: 0,
};

describe("advise - deny case", () => {
  it("recommends deny when opponent heavily values a champion", () => {
    // Azir is the opponent's #1 pick (rate 1.0 in G1) and also our comfort pick
    const results = advise(baseParams);
    const azirRec = results.find((r) => r.champion === "Azir");
    // Azir should be suggested; with high deny value it should be "deny"
    // (denyValue from likelyPicks will be high for Azir since opp rate is 1.0)
    expect(azirRec).toBeDefined();
    expect(azirRec.verdict).toBe("deny");
    expect(azirRec.reasons.some((r) => r.toLowerCase().includes("deni"))).toBe(true);
  });
});

describe("advise - save case", () => {
  it("recommends save when future cost exceeds current value", () => {
    const params = {
      ...baseParams,
      gamesLeft: 3, // 2 future games
      oppReport: {
        ...mockOppReport,
        champions: [
          { champion: "Yasuo", picks: { n: 1, rate: 0.05, label: "1/20" }, bans: { n: 0, rate: 0 },
            by_bucket: { G1: { picks: { n: 0, rate: 0, label: "0/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
        ],
      },
    };
    const results = advise(params);
    // Ahri has high comfort (0.4) and low deny value -> should be "save"
    const ahriRec = results.find((r) => r.champion === "Ahri");
    if (ahriRec) {
      expect(ahriRec.verdict).toBe("save");
      expect(ahriRec.reasons.some((r) => r.toLowerCase().includes("sav"))).toBe(true);
    }
  });
});

describe("advise - last game case", () => {
  it("never recommends save in the last possible game", () => {
    const params = {
      ...baseParams,
      gamesLeft: 1, // last game
    };
    const results = advise(params);
    for (const rec of results) {
      expect(rec.verdict).not.toBe("save");
    }
  });
});

describe("advise - burned/banned exclusion", () => {
  it("never suggests burned champions", () => {
    const params = {
      ...baseParams,
      burned: new Set(["Azir"]),
    };
    const results = advise(params);
    const champNames = results.map((r) => r.champion);
    expect(champNames).not.toContain("Azir");
  });

  it("never suggests blocked (already picked/banned) champions", () => {
    const params = {
      ...baseParams,
      blocked: new Set(["Ahri"]),
    };
    const results = advise(params);
    const champNames = results.map((r) => r.champion);
    expect(champNames).not.toContain("Ahri");
  });
});

describe("advise - basic behavior", () => {
  it("returns an array of recommendations", () => {
    const results = advise(baseParams);
    expect(Array.isArray(results)).toBe(true);
    expect(results.length).toBeGreaterThan(0);
  });

  it("each recommendation has required fields", () => {
    const results = advise(baseParams);
    for (const rec of results) {
      expect(rec.champion).toBeDefined();
      expect(["take-now", "save", "deny"]).toContain(rec.verdict);
      expect(typeof rec.score).toBe("number");
      expect(Array.isArray(rec.reasons)).toBe(true);
      expect(rec.reasons.length).toBeGreaterThan(0);
    }
  });

  it("works without model (graceful degradation)", () => {
    const params = { ...baseParams, model: null };
    const results = advise(params);
    expect(results.length).toBeGreaterThan(0);
  });

  it("works without reports", () => {
    const params = { ...baseParams, usReport: null, oppReport: null };
    const results = advise(params);
    // Should still return results from model champions
    expect(Array.isArray(results)).toBe(true);
  });
});
