import { ORDER, teamAt } from "../draft.js";
import { isReportedTeamId } from "../roster.js";
import Portrait from "./Portrait.jsx";

/** One side of the draft: 5 ban slots and 5 pick slots, highlighting the active step. */
export default function TeamColumn({ side, who, name, shortName: sn, game, step, teamId }) {
  const slots = (type) => ORDER.map((s, i) => ({ ...s, i })).filter((s) => s.type === type && teamAt(game, s.seq) === who);
  const firstPick = game.firstPick === who;
  const isReported = teamId ? isReportedTeamId(teamId) : false;
  const displayName = sn || name;
  return (
    <section className={`team ${side}`}>
      <h2 title={name}>
        {displayName}
        {isReported && <span className="badge" style={{fontSize:"10px",marginLeft:"6px"}}>reported 2027 roster</span>}
        <small>{side} side{firstPick ? " · first pick" : ""}{game.winner === who ? " · won" : ""}</small>
      </h2>
      <div className="bans">
        {slots("ban").map((s) => (
          <div key={s.seq} className={`ban-slot ${s.i === step ? "active" : ""}`} title={`Ban ${s.seq}`}>
            {game.actions[s.i] ? <Portrait name={game.actions[s.i]} small banned /> : <span>B</span>}
          </div>
        ))}
      </div>
      <ol className="picks">
        {slots("pick").map((s) => (
          <li key={s.seq} className={`pick-slot ${s.i === step ? "active" : ""}`}>
            {game.actions[s.i] ? (
              <>
                <Portrait name={game.actions[s.i]} />
                <span className="pick-name">{game.actions[s.i]}</span>
              </>
            ) : (
              <span className="pick-empty">{s.i === step ? "Picking…" : `Pick ${s.seq}`}</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
