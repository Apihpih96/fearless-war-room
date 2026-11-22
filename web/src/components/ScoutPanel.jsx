import { contested, favoritesStatus, likelyBans, likelyPicks } from "../scout.js";
import Portrait from "./Portrait.jsx";

/** Live scouting for the current game: what the opponent is likely to do next. */
export default function ScoutPanel({ bucket, gameNumber, opp, us, blocked, burned, bannedNow, onPick, turn }) {
  if (!opp) return <section className="scout">Loading scouting report…</section>;
  const oppPicks = likelyPicks(opp, bucket, blocked, 8);
  const oppBans = likelyBans(opp, bucket, blocked, 6);
  const usPicks = likelyPicks(us, bucket, blocked, 10);
  const hot = contested(usPicks, oppPicks);
  const favs = favoritesStatus(opp, burned, bannedNow);
  const s = opp.sample;
  const g = s.by_bucket[bucket];
  const shift = opp.fearless.by_bucket[bucket];

  return (
    <section className="scout">
      <header>
        <h2>Scouting {opp.team.name} · Game {gameNumber}</h2>
        <p>
          {s.series} series, {s.games} games in {opp.team.season} ({s.wins}-{s.games - s.wins}). In {bucket}:{" "}
          {g.wins}-{g.games - g.wins}
          {bucket !== "G1" && `, ${shift.new_vs_g1_pool.label} picks were champions they never played in a G1`}.
        </p>
      </header>

      <div className="scout-cols">
        <Card title={`Likely ${opp.team.name} picks`} hint="This game number, minus everything locked">
          <ChampList items={oppPicks} onPick={onPick} turn={turn} />
        </Card>
        <Card title={`Likely ${opp.team.name} bans`} hint={`Their ${bucket} ban pattern`}>
          <ChampList items={oppBans} onPick={onPick} turn={turn} />
        </Card>
        <Card title="Their G1 favorites" hint="Where the player goes once each one is gone">
          <ul className="favs">
            {favs.map((f) => (
              <li key={f.champion} className={f.status}>
                <Portrait name={f.champion} small burned={f.status !== "open"} />
                <div>
                  <span className="fav-head"><b>{f.champion}</b> <em>{f.status}</em></span>
                  <small>
                    {f.g1_picks.label} G1s{f.player ? ` · ${f.player}` : ""}
                    {f.replacements.length > 0 && ` → ${f.replacements.slice(0, 2).map((r) => `${r.champion} ${r.label}`).join(", ")}`}
                  </small>
                </div>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Contested" hint={`High on both lists: take it or ban it`}>
          {hot.length ? (
            <ChampList items={hot.map((h) => ({ champion: h.champion, reason: `${us?.team.name}: ${h.us.reason} · them: ${h.opp.reason}` }))} onPick={onPick} turn={turn} />
          ) : (
            <p className="muted">No overlap left in the top picks.</p>
          )}
        </Card>
      </div>

      <div className="insights">
        <h3>What to expect from {opp.team.name}</h3>
        <ul>
          {opp.insights.map((i) => (
            <li key={i.id}>
              <b>{i.title}.</b> {i.text}
              <span className="q">{i.question}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Card({ title, hint, children }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="muted">{hint}</p>
      {children}
    </div>
  );
}

function ChampList({ items, onPick, turn }) {
  return (
    <ul className="champ-list">
      {items.map((p) => (
        <li key={p.champion}>
          <button onClick={() => onPick(p.champion)} disabled={!turn} title={turn ? `${turn.type} ${p.champion}` : ""}>
            <Portrait name={p.champion} small />
            <span>
              <b>{p.champion}</b>
              <small>{p.reason}{p.record ? ` · ${p.record}` : ""}</small>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
