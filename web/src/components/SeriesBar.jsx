import { burnedBefore, nextStep } from "../draft.js";

/** Game tabs for the series, the score, and the Fearless burn count going into each game. */
export default function SeriesBar({ series, name, score, winner, onSelectGame, onAddGame, onReset }) {
  const last = series.games[series.games.length - 1];
  const canAdd = !winner && last.winner && series.games.length < series.format;
  return (
    <nav className="series">
      <div className="score">
        <b>{name("us")}</b> {score.us} – {score.opp} <b>{name("opp")}</b>
        {winner && <span className="done"> · {name(winner)} win the series</span>}
      </div>
      <div className="tabs">
        {series.games.map((g, i) => (
          <button key={i} className={i === series.current ? "on" : ""} onClick={() => onSelectGame(i)}>
            G{i + 1}
            <small>
              {g.winner ? `W: ${name(g.winner)}` : nextStep(g) === -1 ? "drafted" : `${g.actions.filter(Boolean).length}/20`}
              {i > 0 && ` · 🔥${burnedBefore(series, i).size}`}
            </small>
          </button>
        ))}
        {canAdd && <button className="add" onClick={onAddGame}>+ Game {series.games.length + 1}</button>}
      </div>
      <button className="ghost" onClick={() => confirm("Start a new series?") && onReset()}>New series</button>
    </nav>
  );
}
