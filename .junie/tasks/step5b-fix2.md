# Step 5b review fix 2: horizontal overflow on phones

Read `.junie/guidelines.md`. Do not commit. Do not run `npm install`.

Reviewer measured the production build in headless Chromium: `document.documentElement.scrollWidth` is 504 at a 360 px viewport and 534 at 412 px (it must equal the viewport width). Elements whose right edge passes the viewport: `header.top` / `div.brand` (the header row is wider than the screen; the subtitle paragraph does not wrap), `span.roster-toggle`, `span.vs`, the Bo3/Bo5 `select`, `button.demo-btn`, `button.ghost` ("New series"), `div.win-bar`. Something in the header forces a min-width (likely a flex child without `min-width: 0`, a `white-space: nowrap`, or a fixed width) and every full-width child inherits the too-wide box.

Fix in `web/src/styles.css` (and JSX only if needed):
- At ≤ 600 px the header stacks: brand row (logo + title, subtitle wraps or is hidden at ≤ 412 px), then team controls at 100% width, with `min-width: 0` / `max-width: 100%` / `box-sizing: border-box` where needed.
- Add `html, body { overflow-x: clip }` ONLY as a last-resort safety net; the real overflow must be fixed (the reviewer checks scrollWidth with that rule removed mentally: no element's right edge may exceed the viewport).
- Also check the demo banner and demo controls at 360 px.

`scripts/overflow_check.py` (playwright) is the reviewer's check; you don't need to run it. Verify with `cd web && npx vitest run` and `cd web && npx vite build --outDir /tmp/wb/dist`, then `rm -rf web/dist`. Report what caused the overflow.
