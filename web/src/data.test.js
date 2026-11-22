import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// We need to reset the module state between tests. Since modelCache is a module-level
// variable, we spy on global fetch before the module runs.

describe("loadModel", async () => {
  const mockModel = { coef: { elo: 1.0, draft: 0.5, blue: 0.2, first_pick: 0.1 }, teams: {}, champions: {} };

  beforeEach(() => {
    // Reset global fetch mock before each test
    vi.restoreAllMocks();
  });

  it("fetches model.json and returns the parsed model on success", async () => {
    // Stub fetch to return a valid model.json
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockModel),
    }));

    // Dynamically import so we get a fresh module with our fetch stub in place
    const { loadModel } = await import("./data.js?" + Date.now());
    const result = await loadModel();

    expect(result).toEqual(mockModel);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("model.json"));
  });

  it("returns null when fetch fails", async () => {
    // Stub fetch to simulate a network error / 404
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }));

    const { loadModel } = await import("./data.js?" + Date.now());
    const result = await loadModel();

    expect(result).toBeNull();
  });

  it("caches the result so subsequent calls do not fetch again", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockModel),
    }));

    const { loadModel } = await import("./data.js?" + Date.now());

    const first = await loadModel();
    const second = await loadModel();

    expect(first).toEqual(mockModel);
    expect(second).toEqual(mockModel);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
