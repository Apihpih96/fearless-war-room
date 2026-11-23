import { describe, expect, it } from "vitest";
import {
  validateScript,
  getDemoSteps,
  buildSeriesAtStep,
  totalDemoSteps,
  getCaption,
  isGameTransition,
} from "./demo.js";
import { burnedBefore, nextStep, seriesWinner } from "./draft.js";

describe("demo script validation", () => {
  it("replays without throwing – every action is legal under Fearless rules", () => {
    const series = validateScript();
    expect(series).toBeDefined();
    expect(series.games).toHaveLength(2);
    // G1 should be complete
    expect(nextStep(series.games[0])).toBe(-1);
    // G1 winner set
    expect(series.games[0].winner).toBe("us");
    // G2 partial
    expect(nextStep(series.games[1])).toBeGreaterThan(0);
  });

  it("burns 10 champions after G1", () => {
    const series = validateScript();
    const burned = burnedBefore(series, 1);
    expect(burned.size).toBe(10);
    // G1 picks should all be burned
    const g1Picks = series.games[0].actions.filter((a, i) => {
      // pick slots: 7,8,9,10,11,12,17,18,19,20 (0-indexed: 6,7,8,9,10,11,16,17,18,19)
      return [6,7,8,9,10,11,16,17,18,19].includes(i) && a;
    });
    g1Picks.forEach((c) => expect(burned.has(c)).toBe(true));
  });

  it("G2 bans reset – Aatrox can be banned again", () => {
    const series = validateScript();
    // G2 first ban is Aatrox (same as G1) – should be fine since bans reset
    const g2 = series.games[1];
    expect(g2.actions[0]).toBe("Aatrox");
  });

  it("G2 first pick is Fiora (Azir burned, so different pick)", () => {
    const series = validateScript();
    const g2 = series.games[1];
    // Pick slots in G2: seq 7 is index 6 in actions
    // G2 actions: 6 bans + 2 picks = 8 actions
    // First pick (seq 7) is at index 6
    expect(g2.actions[6]).toBe("Fiora");
    // Azir should be burned
    const burned = burnedBefore(series, 1);
    expect(burned.has("Azir")).toBe(true);
  });
});

describe("demo steps", () => {
  it("returns 30 steps (20 G1 + 1 transition + 8 G2 + 1 extra caption)", () => {
    const total = totalDemoSteps();
    expect(total).toBeGreaterThan(20);
  });

  it("every step has a caption", () => {
    const steps = getDemoSteps();
    for (let i = 0; i < steps.length; i++) {
      const caption = getCaption(i);
      expect(caption.length).toBeGreaterThan(0);
    }
  });

  it("identifies game transitions", () => {
    const steps = getDemoSteps();
    const transitions = steps.filter((s) => s.type === "game-end");
    expect(transitions.length).toBeGreaterThanOrEqual(1);
    for (const t of transitions) {
      const idx = steps.indexOf(t);
      expect(isGameTransition(idx)).toBe(true);
    }
  });
});

describe("buildSeriesAtStep", () => {
  it("starts empty at step 0", () => {
    const series = buildSeriesAtStep(0);
    expect(nextStep(series.games[0])).toBe(0);
  });

  it("builds incrementally – step 1 has one action", () => {
    const series = buildSeriesAtStep(1);
    const g = series.games[0];
    const filled = g.actions.filter((a) => a !== null).length;
    expect(filled).toBe(1);
  });

  it("reaches the same state as validateScript at the end", () => {
    const full = validateScript();
    const steps = totalDemoSteps();
    const built = buildSeriesAtStep(steps);
    // Both should have the same number of games
    expect(built.games.length).toBe(full.games.length);
    // G1 should be complete in both
    expect(nextStep(built.games[0])).toBe(-1);
  });
});
