# Step 4 review fix 1 (found by reviewer in a browser screenshot)

1. Bug: `web/src/data.js` `loadModel()` never fetches model.json. `modelCache.current` starts as `null`, and the guard `modelCache.current !== undefined` is true for null, so it always resolves null and the WinBar and AdvisorPanel never render. Fix the cache (start undefined, or cache the promise) and add a vitest test in `web/src/data.test.js` that stubs `fetch` and proves loadModel fetches once and returns the parsed model, and returns null when fetch fails.
2. Footer in `web/src/App.jsx`: change "Built with PyCharm, WebStorm and Junie" to "Built with Junie, JetBrains' coding agent".
3. Check that WinBar and AdvisorPanel render correctly with a real model (read the components; make sure the AdvisorPanel shows for whichever team is on the clock and that clicking a row calls the existing select handler).
Run `cd web && npx vitest run` and `npx vite build`; both must pass. Do not commit.
