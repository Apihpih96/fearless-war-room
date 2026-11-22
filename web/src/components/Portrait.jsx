import { createContext, useContext, useState } from "react";

/** name -> image url, provided once by ChampionGrid's roster. */
export const PortraitContext = createContext({});

export default function Portrait({ name, small = false, banned = false, burned = false }) {
  const images = useContext(PortraitContext);
  const [failed, setFailed] = useState(false);
  const src = images[name];
  const cls = `portrait ${small ? "small" : ""} ${banned ? "banned" : ""} ${burned ? "burned" : ""}`;
  if (!src || failed) {
    const initials = name.replace(/[^A-Za-z ]/g, "").split(" ").map((w) => w[0]).join("").slice(0, 2);
    return <span className={`${cls} initials`} title={name}>{initials}</span>;
  }
  return <img className={cls} src={src} alt={name} title={name} loading="lazy" onError={() => setFailed(true)} />;
}
