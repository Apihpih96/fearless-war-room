import { describe, expect, it } from "vitest";
import {
  ORDER, addGame, bansOf, burnedBefore, canSelect, newSeries, nextStep, picksOf, score,
  select, seriesWinner, setWinner, sideOf, teamAt, undo, unavailable, updateGame,
} from "./draft.js";
import { favoritesStatus, likelyBans, likelyPicks } from "./scout.js";

const champs = (p, n = 20) => Array.from({ length: n }, (_, i) => `${p}${i}`);
const fill = (s, names) => names.reduce((acc, c) => select(acc, c), s);

describe("draft order", () => {
  it("is 10 bans and 10 picks, 5 each per team", () => {
    expect(ORDER).toHaveLength(20);
    const g = newSeries().games[0];
    for (const who of ["us", "opp"]) {
      expect(ORDER.filter((s) => s.type === "pick" && teamAt(g, s.seq) === who)).toHaveLength(5);
      expect(ORDER.filter((s) => s.type === "ban" && teamAt(g, s.seq) === who)).toHaveLength(5);
    }
  });
  it("lets the red side pick first (2026 First Selection)", () => {
    let s = newSeries();
    s = updateGame(s, { firstPick: "us", usSide: "red" });
    const g = s.games[0];
    expect(teamAt(g, 7)).toBe("us");
    expect(sideOf(g, "us")).toBe("red");
    expect(sideOf(g, "opp")).toBe("blue");
  });
});

describe("fearless rules", () => {
  it("burns every pick from earlier games, but not bans", () => {
    let s = fill(newSeries({ format: 3 }), champs("a"));
    s = addGame(setWinner(s, "us"));
    const burned = burnedBefore(s);
    const g1 = s.games[0];
    expect(burned.size).toBe(10);
    picksOf(g1, "us").concat(picksOf(g1, "opp")).forEach((c) => expect(burned.has(c)).toBe(true));
    bansOf(g1, "us").forEach((c) => expect(burned.has(c)).toBe(false));
    expect(canSelect(s, picksOf(g1, "opp")[0])).toBe(false);
    expect(canSelect(s, bansOf(g1, "opp")[0])).toBe(true);
  });
  it("refuses a champion already used in this game", () => {
    const s = select(newSeries(), "Azir");
    expect(() => select(s, "Azir")).toThrow();
    expect(unavailable(s).has("Azir")).toBe(true);
  });
  it("hands first selection to the loser of the last game", () => {
    let s = fill(newSeries(), champs("a"));
    s = addGame(setWinner(s, "us"));
    expect(s.games[1].firstPick).toBe("opp");
    expect(s.current).toBe(1);
  });
  it("undo clears the last step and the result", () => {
    let s = setWinner(fill(newSeries(), champs("a")), "opp");
    s = undo(s);
    expect(nextStep(s.games[0])).toBe(19);
    expect(s.games[0].winner).toBe(null);
  });
});

describe("series", () => {
  it("ends a Bo3 at 2 wins and blocks a 4th game", () => {
    let s = newSeries({ format: 3 });
    for (let i = 0; i < 2; i++) {
      s = setWinner(fill(s, champs(`g${i}-`)), "us");
      if (i < 1) s = addGame(s);
    }
    expect(score(s)).toEqual({ us: 2, opp: 0 });
    expect(seriesWinner(s)).toBe("us");
    expect(addGame(s).games).toHaveLength(2);
  });
});

describe("scout suggestions", () => {
  const rep = {
    champions: [
      { champion: "Azir", picks: { n: 6, rate: 0.3, label: "6/20", record: "4-2" }, bans: { n: 0, rate: 0 },
        by_bucket: { G1: { picks: { n: 6, rate: 0.6, label: "6/10" }, bans: { n: 0, rate: 0, label: "0/10" } } } },
      { champion: "Ahri", picks: { n: 2, rate: 0.1, label: "2/20", record: "1-1" }, bans: { n: 3, rate: 0.15 },
        by_bucket: { G2: { picks: { n: 2, rate: 0.2, label: "2/10" }, bans: { n: 3, rate: 0.3, label: "3/10" } } } },
    ],
    fearless: { when_favorites_locked: [{ champion: "Azir", player: "Saint", replacements: [{ champion: "Ahri", rate: 0.4, label: "4/10" }] }] },
  };
  it("ranks G1 favorites and skips unavailable champions", () => {
    expect(likelyPicks(rep, "G1", new Set())[0].champion).toBe("Azir");
    expect(likelyPicks(rep, "G1", new Set(["Azir"])).map((p) => p.champion)).toEqual(["Ahri"]);
  });
  it("explains the replacement once a favorite is burned", () => {
    const [top] = likelyPicks(rep, "G2", new Set(["Azir"]));
    expect(top.champion).toBe("Ahri");
    expect(top.reason).toMatch(/Saint → Ahri when Azir is gone/);
  });
  it("ranks bans and marks favorite status", () => {
    expect(likelyBans(rep, "G2", new Set())[0].champion).toBe("Ahri");
    expect(favoritesStatus(rep, new Set(["Azir"]), new Set())[0].status).toBe("burned");
  });
});
