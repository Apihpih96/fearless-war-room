import { useMemo, useState } from "react";
import Portrait from "./Portrait.jsx";

const ROLES = ["All", "Fighter", "Tank", "Mage", "Assassin", "Marksman", "Support"];

/** Searchable champion pool. Burned (Fearless) and used champions are locked. */
export default function ChampionGrid({ champions, blocked, burned, onPick, disabled, turn }) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("All");
  const [hideLocked, setHideLocked] = useState(false);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    // exact name first, then names starting with the search, then the rest ("vi" -> Vi, Viego, Viktor, Anivia)
    const rank = (n) => (!needle ? 0 : n === needle ? 0 : n.startsWith(needle) ? 1 : 2);
    return champions
      .filter(
        (c) =>
          (!needle || c.name.toLowerCase().includes(needle)) &&
          (role === "All" || c.tags.includes(role)) &&
          (!hideLocked || !blocked.has(c.name)),
      )
      .sort((a, b) => rank(a.name.toLowerCase()) - rank(b.name.toLowerCase()) || a.name.localeCompare(b.name));
  }, [champions, q, role, hideLocked, blocked]);

  const onKey = (e) => {
    if (e.key === "Enter") {
      const first = shown.find((c) => !blocked.has(c.name));
      if (first) {
        onPick(first.name);
        setQ("");
      }
    }
  };

  return (
    <section className="pool">
      <div className="pool-tools">
        <input
          placeholder={turn ? `Search, Enter to ${turn.type}` : "Draft complete"}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          disabled={disabled}
          aria-label="Search champions"
        />
        <div className="roles">
          {ROLES.map((r) => (
            <button key={r} className={r === role ? "on" : ""} onClick={() => setRole(r)}>{r}</button>
          ))}
        </div>
        <label className="check">
          <input type="checkbox" checked={hideLocked} onChange={(e) => setHideLocked(e.target.checked)} /> Hide locked
        </label>
        <span className="burn-count" title="Champions picked in earlier games of this series">🔥 {burned.size} burned</span>
      </div>
      <div className="grid">
        {shown.map((c) => {
          const isBurned = burned.has(c.name);
          const locked = blocked.has(c.name);
          return (
            <button
              key={c.name}
              className={`champ ${locked ? "locked" : ""} ${isBurned ? "is-burned" : ""}`}
              onClick={() => onPick(c.name)}
              disabled={disabled || locked}
              title={isBurned ? `${c.name}: burned by Fearless` : locked ? `${c.name}: used this game` : c.name}
            >
              <Portrait name={c.name} burned={isBurned} />
              <span>{c.name}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
