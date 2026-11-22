import { useEffect, useMemo, useState } from "react";
import {
  ORDER, addGame, bucketOf, burnedBefore, canSelect, newSeries, nextStep, score, select,
  seriesWinner, setWinner, sideOf, teamAt, undo, unavailable, updateGame,
} from "./draft.js";
import { loadChampions, loadIndex, loadTeam } from "./data.js";
import TeamColumn from "./components/TeamColumn.jsx";
import ChampionGrid from "./components/ChampionGrid.jsx";
import ScoutPanel from "./components/ScoutPanel.jsx";
import SeriesBar from "./components/SeriesBar.jsx";
import { PortraitContext } from "./components/Portrait.jsx";

const SAVE_KEY = "fwr.series.v1";
const C9 = "47351";

function usePersistentSeries() {
  const [series, setSeries] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(SAVE_KEY)) || null;
    } catch {
      return null;
    }
  });
  useEffect(() => {
    if (series) localStorage.setItem(SAVE_KEY, JSON.stringify(series));
  }, [series]);
  return [series, setSeries];
}

export default function App() {
  const [index, setIndex] = useState(null);
  const [champions, setChampions] = useState([]);
  const [series, setSeries] = usePersistentSeries();
  const [reports, setReports] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    loadIndex().then(setIndex).catch((e) => setError(String(e)));
    loadChampions().then(setChampions);
  }, []);

  // default matchup: Cloud9 Kia vs their most frequent LCS 2026 opponent
  useEffect(() => {
    if (index && !series) setSeries(newSeries({ us: C9, opp: index.teams.find((t) => t.lcs_2026 && t.id !== C9)?.id, format: 3 }));
  }, [index, series, setSeries]);

  const images = useMemo(() => Object.fromEntries(champions.filter((c) => c.img).map((c) => [c.name, c.img])), [champions]);
  const teamsById = useMemo(() => Object.fromEntries((index?.teams || []).map((t) => [t.id, t])), [index]);

  useEffect(() => {
    if (!series) return;
    for (const id of [series.us, series.opp]) {
      const t = teamsById[id];
      if (t && !reports[id]) loadTeam(t.file).then((r) => setReports((prev) => ({ ...prev, [id]: r })));
    }
  }, [series, teamsById, reports]);

  if (error) return <div className="splash">Could not load scouting data: {error}. Run <code>python pipeline/build_scout.py</code>.</div>;
  if (!index || !series) return <div className="splash">Loading war room…</div>;

  const game = series.games[series.current];
  const step = nextStep(game);
  const burned = burnedBefore(series);
  const blocked = unavailable(series);
  const bucket = bucketOf(series.current);
  const name = (who) => teamsById[who === "us" ? series.us : series.opp]?.name || "?";
  const winner = seriesWinner(series);
  const sc = score(series);
  const blueWho = game.usSide === "blue" ? "us" : "opp";
  const redWho = blueWho === "us" ? "opp" : "us";
  const turn = step === -1 ? null : { who: teamAt(game, step + 1), ...ORDER[step] };

  const pick = (champ) => canSelect(series, champ) && setSeries(select(series, champ));
  const restart = (patch = {}) => setSeries(newSeries({ us: series.us, opp: series.opp, format: series.format, ...patch }));

  return (
    <PortraitContext.Provider value={images}>
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo">FWR</span>
          <div>
            <h1>Fearless War Room</h1>
            <p>Fearless draft prep · scouting from {index.teams.length} teams, aggregates of GRID data</p>
          </div>
        </div>
        <div className="matchup">
          <TeamSelect label="Us" value={series.us} teams={index.teams} onChange={(us) => restart({ us })} />
          <span className="vs">vs</span>
          <TeamSelect label="Opponent" value={series.opp} teams={index.teams} onChange={(opp) => restart({ opp })} />
          <select aria-label="Format" value={series.format} onChange={(e) => restart({ format: Number(e.target.value) })}>
            <option value={3}>Bo3</option>
            <option value={5}>Bo5</option>
          </select>
        </div>
      </header>

      <SeriesBar
        series={series}
        name={name}
        score={sc}
        winner={winner}
        onSelectGame={(i) => setSeries({ ...series, current: i })}
        onAddGame={() => setSeries(addGame(series))}
        onReset={() => restart()}
      />

      <div className="game-controls">
        <label>
          First pick
          <select value={game.firstPick} onChange={(e) => setSeries(updateGame(series, { firstPick: e.target.value }))} disabled={game.actions.some(Boolean)}>
            <option value="us">{name("us")}</option>
            <option value="opp">{name("opp")}</option>
          </select>
        </label>
        <label>
          {name("us")} side
          <select value={game.usSide} onChange={(e) => setSeries(updateGame(series, { usSide: e.target.value }))}>
            <option value="blue">Blue</option>
            <option value="red">Red</option>
          </select>
        </label>
        <span className="turn">
          {turn ? (
            <>Step {turn.seq}/20 · {turn.phase} · <b className={sideOf(game, turn.who)}>{name(turn.who)}</b> {turn.type}s</>
          ) : game.winner ? (
            <>Game {series.current + 1} to <b>{name(game.winner)}</b></>
          ) : (
            <>Draft complete · who won?{" "}
              <button onClick={() => setSeries(setWinner(series, "us"))}>{name("us")}</button>
              <button onClick={() => setSeries(setWinner(series, "opp"))}>{name("opp")}</button>
            </>
          )}
        </span>
        <button className="ghost" onClick={() => setSeries(undo(series))} disabled={!game.actions.some(Boolean)}>Undo</button>
      </div>

      <main className="board">
        <TeamColumn side="blue" who={blueWho} name={name(blueWho)} game={game} step={step} />
        <ChampionGrid champions={champions} blocked={blocked} burned={burned} onPick={pick} disabled={step === -1} turn={turn} />
        <TeamColumn side="red" who={redWho} name={name(redWho)} game={game} step={step} />
      </main>

      <ScoutPanel
        bucket={bucket}
        gameNumber={series.current + 1}
        opp={reports[series.opp]}
        us={reports[series.us]}
        blocked={blocked}
        burned={burned}
        bannedNow={new Set(game.actions.filter((c, i) => c && ORDER[i].type === "ban"))}
        onPick={pick}
        turn={turn}
      />

      <footer className="foot">
        Built with PyCharm, WebStorm and Junie for the Cloud9 x JetBrains Sky's The Limit Hackathon. Champion art © Riot Games via Data Dragon. Stats are aggregates of GRID esports data.
      </footer>
    </div>
    </PortraitContext.Provider>
  );
}

function TeamSelect({ label, value, teams, onChange }) {
  const groups = teams.reduce((acc, t) => {
    const g = t.lcs_2026 ? "LCS 2026" : `${t.league} ${t.season}`;
    (acc[g] ||= []).push(t);
    return acc;
  }, {});
  return (
    <select aria-label={label} value={value || ""} onChange={(e) => onChange(e.target.value)}>
      {Object.entries(groups).map(([g, ts]) => (
        <optgroup key={g} label={g}>
          {ts.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
