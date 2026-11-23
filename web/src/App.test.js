import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { resolveRenderPhase } from "./App.jsx";

describe("resolveRenderPhase", () => {
  it('returns "loading" when index is null', () => {
    expect(resolveRenderPhase({ index: null, effectiveSeries: null, error: null })).toBe("loading");
  });

  it('returns "loading" when effectiveSeries is null even if index exists', () => {
    expect(resolveRenderPhase({ index: { teams: [] }, effectiveSeries: null, error: null })).toBe("loading");
  });

  it('returns "loading" when both index and effectiveSeries are null', () => {
    expect(resolveRenderPhase({ index: null, effectiveSeries: null, error: null })).toBe("loading");
  });

  it('returns "error" when error is set', () => {
    expect(resolveRenderPhase({ index: null, effectiveSeries: null, error: "fail" })).toBe("error");
  });

  it('returns "ready" when both index and effectiveSeries are present', () => {
    const fakeSeries = { games: [{ actions: Array(20).fill(null) }], current: 0, us: "a", opp: "b", format: 3 };
    expect(resolveRenderPhase({ index: { teams: [] }, effectiveSeries: fakeSeries, error: null })).toBe("ready");
  });

  it('returns "error" even when data is present (error takes priority)', () => {
    const fakeSeries = { games: [{ actions: Array(20).fill(null) }], current: 0, us: "a", opp: "b", format: 3 };
    expect(resolveRenderPhase({ index: { teams: [] }, effectiveSeries: fakeSeries, error: "oops" })).toBe("error");
  });
});

describe("App first-render guard (regression)", () => {
  // The bug: on first render with empty localStorage, `index` is null (not yet
  // fetched) and `effectiveSeries` is null (series created by an effect).
  // The old guard only checked `!index`, so the render body tried to read
  // `effectiveSeries.games` → TypeError: Cannot read properties of null.
  //
  // This test verifies the pure guard logic catches the null-effectiveSeries case.

  it("does not reach the render body when effectiveSeries is null", () => {
    // Simulates the first render: index not loaded yet, series not created yet.
    const phase = resolveRenderPhase({ index: null, effectiveSeries: null, error: null });
    expect(phase).toBe("loading");
  });

  it("does not reach the render body when index loaded but series not yet created", () => {
    // Simulates the render after index loads but before the useEffect creates series.
    const phase = resolveRenderPhase({ index: { teams: [{ id: "1", name: "Team" }] }, effectiveSeries: null, error: null });
    expect(phase).toBe("loading");
  });
});
