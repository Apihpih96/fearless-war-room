// Data loading: our committed scout aggregates plus the champion roster that
// pipeline/build_scout.py snapshots from Riot Data Dragon (portraits + roles).
// Portraits load as plain <img> tags from the Data Dragon CDN; with no network
// the tiles fall back to initials.

const DD = "https://ddragon.leagueoflegends.com";
const local = (p) => fetch(`${import.meta.env.BASE_URL}data/${p}`).then((r) => {
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  return r.json();
});

export const loadIndex = () => local("index.json");

/** Load the win-probability model. Returns null if model.json is missing. */
const modelCache = { current: undefined };
export const loadModel = () => {
  if (modelCache.current !== undefined) return Promise.resolve(modelCache.current);
  return local("model.json")
    .then((m) => { modelCache.current = m; return m; })
    .catch(() => { modelCache.current = null; return null; });
};

const teamCache = new Map();
export function loadTeam(file) {
  if (!teamCache.has(file)) teamCache.set(file, local(file));
  return teamCache.get(file);
}

/** [{ name, img|null, tags: [] }] sorted by name. */
export async function loadChampions() {
  const roster = await local("champions.json").catch(() => ({ version: null, champions: [] }));
  const list = Array.isArray(roster) ? roster.map((name) => ({ name })) : roster.champions;
  return list
    .map((c) => ({
      name: c.name,
      tags: c.tags || [],
      img: roster.version && c.image ? `${DD}/cdn/${roster.version}/img/champion/${c.image}` : null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}
