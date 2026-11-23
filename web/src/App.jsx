import { useEffect, useMemo, useState, useCallback } from "react";
import {
  ORDER, addGame, bucketOf, burnedBefore, canSelect, newSeries, nextStep, score, select,
  seriesWinner, setWinner, sideOf, teamAt, undo, unavailable, updateGame,
} from "./draft.js";
import { loadChampions, loadIndex, loadModel, loadTeam } from "./data.js";
import { isReportedTeamId, getEloFallbackTeamId, defaultOpponent } from "./roster.js";
import { shortName } from "./names.js";
import {
  buildSeriesAtStep, getCaption, totalDemoSteps, isGameTransition,
} from "./demo.js";
import TeamColumn from "./components/TeamColumn.jsx";
import ChampionGrid from "./components/ChampionGrid.jsx";
import ScoutPanel from "./components/ScoutPanel.jsx";
import SeriesBar from "./components/SeriesBar.jsx";
import WinBar from "./components/WinBar.jsx";
import AdvisorPanel from "./components/AdvisorPanel.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import { PortraitContext } from "./components/Portrait.jsx";

const SAVE_KEY = "fwr.series.v1";
const C9_2027 = "c9-2027";
const C9_2026 = "47351";

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
  const [model, setModel] = useState(null);
  const [series, setSeries] = usePersistentSeries();
  const [reports, setReports] = useState({});
  const [reportErrors, setReportErrors] = useState({});
  const [modelError, setModelError] = useState(null);
  const [error, setError] = useState(null);

  // Demo mode state
  const [demoMode, setDemoMode] = useState(false);
  const [demoStep, setDemoStep] = useState(0);
  const [demoPaused, setDemoPaused] = useState(false);

  useEffect(() => {
    loadIndex().then(setIndex).catch((e) => setError(String(e)));
    loadChampions().then(setChampions);
    loadModel().then(setModel).catch((e) => {
      setModelError(String(e));
    }); // null is fine — app still works
  }, []);

  // default matchup: Cloud9 2027 reported roster vs first non-C9 LCS 2026 opponent
  useEffect(() => {
    if (index && !series && !demoMode) setSeries(newSeries({ us: C9_2027, opp: defaultOpponent(C9_2027, index.teams), format: 3 }));
  }, [index, series, setSeries, demoMode]);

  const images = useMemo(() => Object.fromEntries(champions.filter((c) => c.img).map((c) => [c.name, c.img])), [champions]);
  const teamsById = useMemo(() => Object.fromEntries((index?.teams || []).map((t) => [t.id, t])), [index]);

  useEffect(() => {
    if (!series) return;
    for (const id of [series.us, series.opp]) {
      const t = teamsById[id];
      if (t && !reports[id] && !reportErrors[id]) {
        loadTeam(t.file)
          .then((r) => setReports((prev) => ({ ...prev, [id]: r })))
          .catch((e) => setReportErrors((prev) => ({ ...prev, [id]: String(e) })));
      }
    }
  }, [series, teamsById, reports, reportErrors]);

  // Demo auto-play timer
  useEffect(() => {
    if (!demoMode || demoPaused) return;
    const total = totalDemoSteps();
    if (demoStep >= total) {
      setDemoPaused(true);
      return;
    }
    const timer = setTimeout(() => {
      setDemoStep((s) => Math.min(s + 1, total));
    }, 1600);
    return () => clearTimeout(timer);
  }, [demoMode, demoPaused, demoStep]);

  // Demo controls
  const startDemo = useCallback(() => {
    setDemoMode(true);
    setDemoStep(0);
    setDemoPaused(false);
    setSeries(buildSeriesAtStep(0));
  }, [setSeries]);

  const exitDemo = useCallback(() => {
    setDemoMode(false);
    setDemoStep(0);
    setDemoPaused(false);
    // Restore a normal series
    if (index) {
      setSeries(newSeries({ us: C9_2027, opp: defaultOpponent(C9_2027, index.teams), format: 3 }));
    }
  }, [index, setSeries]);

  const demoNext = useCallback(() => {
    setDemoStep((s) => Math.min(s + 1, totalDemoSteps()));
  }, []);

  // In demo mode, derive series from demo step
  const effectiveSeries = demoMode ? buildSeriesAtStep(demoStep) : series;
  const demoCaption = demoMode ? getCaption(demoStep) : null;
  const demoIsTransition = demoMode && isGameTransition(demoStep);

  if (error) return <div className="splash">Could not load scouting data: {error}. Run <code>python pipeline/build_scout.py</code>.</div>;
  if (!index || !effectiveSeries) return <div className="splash">Loading war room…</div>;

  // Pure helper: determines which render phase the app is in.
  // Exported for testing so we can verify the guard without effects.
  const renderPhase = resolveRenderPhase({ index, effectiveSeries, error });

  const game = effectiveSeries.games[effectiveSeries.current];
  const step = nextStep(game);
  const burned = burnedBefore(effectiveSeries);
  const blocked = unavailable(effectiveSeries);
  const bucket = bucketOf(effectiveSeries.current);
  const name = (who) => teamsById[who === "us" ? effectiveSeries.us : effectiveSeries.opp]?.name || "?";
  const sn = (who) => shortName(name(who));
  const winner = seriesWinner(effectiveSeries);
  const sc = score(effectiveSeries);
  const blueWho = game.usSide === "blue" ? "us" : "opp";
  const redWho = blueWho === "us" ? "opp" : "us";
  const turn = step === -1 ? null : { who: teamAt(game, step + 1), ...ORDER[step] };

  const pick = (champ) => {
    if (demoMode) return;
    canSelect(effectiveSeries, champ) && setSeries(select(effectiveSeries, champ));
  };
  const restart = (patch = {}) => {
    if (demoMode) return;
    setSeries(newSeries({ us: effectiveSeries.us, opp: effectiveSeries.opp, format: effectiveSeries.format, ...patch }));
  };
  const handleUndo = () => {
    if (demoMode) return;
    const s = effectiveSeries;
    const g = s.games[s.current];
    // If undoing back across the start of a game, just stop
    if (!g.actions.some(Boolean) && s.current > 0) return;
    setSeries(undo(s));
  };

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
          {!demoMode ? (
            <>
              <TeamSelect label="Us" value={series.us} teams={index.teams} onChange={(us) => restart({ us })} />
              {isReportedTeamId(series.us) && (
                <span className="roster-toggle" title="Switch between 2027 reported roster and 2026 Cloud9 Kia">
                  <button className={series.us === C9_2027 ? "active" : ""} onClick={() => restart({ us: C9_2027 })}>2027 reported</button>
                  <button className={series.us === C9_2026 ? "active" : ""} onClick={() => restart({ us: C9_2026 })}>2026 Kia</button>
                </span>
              )}
              <span className="vs">vs</span>
              <TeamSelect label="Opponent" value={series.opp} teams={index.teams} onChange={(opp) => restart({ opp })} />
              {isReportedTeamId(series.opp) && (
                <span className="roster-toggle" title="Switch between 2027 reported roster and 2026 Cloud9 Kia">
                  <button className={series.opp === C9_2027 ? "active" : ""} onClick={() => restart({ opp: C9_2027 })}>2027 reported</button>
                  <button className={series.opp === C9_2026 ? "active" : ""} onClick={() => restart({ opp: C9_2026 })}>2026 Kia</button>
                </span>
              )}
              <select aria-label="Format" value={series.format} onChange={(e) => restart({ format: Number(e.target.value) })}>
                <option value={3}>Bo3</option>
                <option value={5}>Bo5</option>
              </select>
            </>
          ) : (
            <span className="demo-matchup-label">
              {name("us")} vs {name("opp")} · Illustrative demo draft
            </span>
          )}
          {!demoMode ? (
            <button className="demo-btn" aria-label="Demo" onClick={startDemo} title="Start guided demo">▶ Demo</button>
          ) : (
            <div className="demo-controls">
              {!demoPaused ? (
                <button onClick={() => setDemoPaused(true)}>⏸ Pause</button>
              ) : (
                <button onClick={() => setDemoPaused(false)}>▶ Resume</button>
              )}
              <button onClick={demoNext} disabled={demoStep >= totalDemoSteps()}>Next ▸</button>
              <button className="ghost" onClick={exitDemo}>Exit demo</button>
            </div>
          )}
        </div>
      </header>

      {/* Demo caption banner */}
      {demoMode && demoCaption && (
        <div className="demo-banner" title="Illustrative demo draft – not from a real game">
          <span className="demo-banner-label">Illustrative demo draft</span>
          <span>{demoCaption}</span>
          <span className="demo-step-count">Step {demoStep + 1}/{totalDemoSteps()}</span>
        </div>
      )}

      <SeriesBar
        series={effectiveSeries}
        name={name}
        score={sc}
        winner={winner}
        onSelectGame={(i) => { if (!demoMode) setSeries({ ...effectiveSeries, current: i }); }}
        onAddGame={() => { if (!demoMode) setSeries(addGame(effectiveSeries)); }}
        onReset={() => restart()}
        shortName={sn}
      />

      <WinBar model={model} series={effectiveSeries} game={game} name={name} shortName={sn} eloFallback={getEloFallbackTeamId} />
      {modelError && <div className="muted" style={{fontSize:"11px",padding:"2px 0"}}>⚠ Win probability model not available</div>}

      <ErrorBoundary>
      <div className="game-controls">
        {!demoMode && (
          <>
            <label>
              First pick
              <select value={game.firstPick} onChange={(e) => setSeries(updateGame(effectiveSeries, { firstPick: e.target.value }))} disabled={game.actions.some(Boolean)}>
                <option value="us">{name("us")}</option>
                <option value="opp">{name("opp")}</option>
              </select>
            </label>
            <label>
              <span title={name("us")}>{sn("us")}</span> side
              <select value={game.usSide} onChange={(e) => setSeries(updateGame(effectiveSeries, { usSide: e.target.value }))}>
                <option value="blue">Blue</option>
                <option value="red">Red</option>
              </select>
            </label>
          </>
        )}
        <span className="turn">
          {turn ? (
            <>Step {turn.seq}/20 · {turn.phase} · <b className={sideOf(game, turn.who)} title={name(turn.who)}>{sn(turn.who)}</b> {turn.type}s</>
          ) : game.winner ? (
            <>Game {effectiveSeries.current + 1} to <b>{name(game.winner)}</b></>
          ) : (
            <>Draft complete · who won?{" "}
              {!demoMode && (
                <>
                  <button onClick={() => setSeries(setWinner(effectiveSeries, "us"))}>{name("us")}</button>
                  <button onClick={() => setSeries(setWinner(effectiveSeries, "opp"))}>{name("opp")}</button>
                </>
              )}
            </>
          )}
        </span>
        {!demoMode && (
          <button className="ghost" onClick={handleUndo} disabled={!game.actions.some(Boolean)}>Undo</button>
        )}
      </div>

      <main className="board">
        <TeamColumn side="blue" who={blueWho} name={name(blueWho)} shortName={sn(blueWho)} game={game} step={step} teamId={blueWho === "us" ? effectiveSeries.us : effectiveSeries.opp} />
        <ChampionGrid champions={champions} blocked={blocked} burned={burned} onPick={pick} disabled={step === -1 || demoMode} turn={turn} />
        <TeamColumn side="red" who={redWho} name={name(redWho)} shortName={sn(redWho)} game={game} step={step} teamId={redWho === "us" ? effectiveSeries.us : effectiveSeries.opp} />
      </main>
      </ErrorBoundary>

      {reportErrors[effectiveSeries.opp] ? (
        <section className="scout"><p className="muted">Scouting report not available: {reportErrors[effectiveSeries.opp]}</p></section>
      ) : !reports[effectiveSeries.opp] ? (
        <section className="scout"><p className="muted">Loading scouting report…</p></section>
      ) : (
        <ScoutPanel
          bucket={bucket}
          gameNumber={effectiveSeries.current + 1}
          opp={reports[effectiveSeries.opp]}
          us={reports[effectiveSeries.us]}
          usTeamId={effectiveSeries.us}
          oppTeamId={effectiveSeries.opp}
          blocked={blocked}
          burned={burned}
          bannedNow={new Set(game.actions.filter((c, i) => c && ORDER[i].type === "ban"))}
          onPick={pick}
          turn={turn}
        />
      )}

      {reportErrors[effectiveSeries.us] || reportErrors[effectiveSeries.opp] ? (
        <section className="advisor"><p className="muted">Advisor not available – report data missing.</p></section>
      ) : (
        <AdvisorPanel
          model={model}
          series={effectiveSeries}
          game={game}
          usReport={reports[effectiveSeries.us]}
          oppReport={reports[effectiveSeries.opp]}
          bucket={bucket}
          blocked={blocked}
          burned={burned}
          onPick={pick}
          turn={turn}
          name={name}
        />
      )}

      <footer className="foot">
        Built with Junie, JetBrains' coding agent for the Cloud9 x JetBrains Sky's The Limit Hackathon. Champion art © Riot Games via Data Dragon. Stats are aggregates of GRID esports data.
      </footer>
    </div>
    </PortraitContext.Provider>
  );
}

/**
 * Pure helper: determines which render phase the app is in.
 * Returns "error", "loading", or "ready".
 * Exported for testing so the guard logic can be verified without React effects.
 */
export function resolveRenderPhase({ index, effectiveSeries, error }) {
  if (error) return "error";
  if (!index || !effectiveSeries) return "loading";
  return "ready";
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
