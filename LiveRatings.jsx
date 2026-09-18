/**
 * LiveRatings.jsx — the Madden 26 Live Ratings board as a React component.
 *
 * Drop-in for an existing app. Expects the payload emitted by build_site.py:
 *
 *     import payload from "./ratings.json";
 *     <LiveRatings data={payload} teamNames={teamNames} />
 *
 * Generate the JSON with:
 *     python -c "import json,build_site; \
 *       json.dump(build_site.build_payload(), open('ratings.json','w'))"
 *
 * The published page (out/index.html) is the same interface in plain HTML.
 * This file exists for embedding the board inside a larger React codebase.
 */

import React, { useMemo, useState } from "react";

const C = {
  ink: "#0C1D2E", panel: "#132A3F", line: "#22415C", detail: "#0F2437",
  chalk: "#EDF3F8", mute: "#8AA4BC", rise: "#35C289", fall: "#E4564A",
};

const display = '"Barlow Condensed", Impact, sans-serif';
const body = '"Archivo", "Helvetica Neue", Arial, sans-serif';

const fmt = (n) => n.toLocaleString();

/* ---------------------------------------------------------------- pieces */

function Tally({ up, down, held }) {
  const item = (value, label, colour) => (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <b style={{ fontFamily: display, fontSize: 52, fontWeight: 700,
                  lineHeight: 0.95, color: colour }}>{fmt(value)}</b>
      <span style={{ color: C.mute, fontSize: 13, marginTop: 4 }}>{label}</span>
    </div>
  );
  return (
    <div style={{ display: "flex", gap: 40, flexWrap: "wrap", margin: "26px 0 30px" }}>
      {item(up, "rose since launch", C.rise)}
      {item(down, "fell since launch", C.fall)}
      {item(held, "held at launch", C.mute)}
    </div>
  );
}

function HeadlineMover({ player, teamName }) {
  if (!player) return null;
  const d = player.o - player.l;
  const colour = d > 0 ? C.rise : C.fall;
  return (
    <div style={{ display: "flex", background: C.panel, borderRadius: 3,
                  overflow: "hidden", marginBottom: 34 }}>
      <div style={{ width: 8, flex: "0 0 8px", background: player.c }} />
      <div style={{ padding: "18px 22px", display: "flex", flex: 1, gap: 20,
                    justifyContent: "space-between", alignItems: "center",
                    flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: display, fontSize: 32, fontWeight: 700,
                        lineHeight: 1, letterSpacing: ".02em" }}>{player.n}</div>
          <div style={{ color: C.mute, fontSize: 13 }}>
            {player.p}&nbsp;&nbsp;{teamName}
          </div>
          <div style={{ color: C.mute, fontSize: 12, marginTop: 6 }}>
            Biggest move of the season so far
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontFamily: display, fontSize: 54, color: C.mute }}>{player.l}</span>
          <span style={{ color: C.mute, fontSize: 24 }}>&rarr;</span>
          <span style={{ fontFamily: display, fontSize: 54, color: colour }}>{player.o}</span>
          <span style={{ fontFamily: display, fontSize: 26, color: colour }}>
            {d > 0 ? "+" : ""}{d}
          </span>
        </div>
      </div>
    </div>
  );
}

function Detail({ player, attrs, weeks }) {
  const cell = { padding: "5px 0", borderBottom: `1px solid ${C.line}66`, fontSize: 13 };
  return (
    <div style={{ padding: "18px 14px 22px", display: "grid", gap: 20,
                  gridTemplateColumns: "minmax(0,1.35fr) minmax(0,.65fr)" }}>
      <div>
        <p style={{ fontSize: 12, color: C.mute, margin: "0 0 10px" }}>
          Attributes that moved off their launch value
        </p>
        {player.a.length === 0 ? (
          <p style={{ color: C.mute, fontSize: 13 }}>
            No attribute has moved a full point yet. Sub-point adjustments are still
            tracked underneath and will surface once they round.
          </p>
        ) : (
          <div style={{ display: "grid", gap: "2px 18px",
                        gridTemplateColumns: "repeat(auto-fill,minmax(210px,1fr))" }}>
            {player.a.map(([j, l, c]) => (
              <div key={j} style={{ ...cell, display: "flex",
                                    justifyContent: "space-between", alignItems: "baseline" }}>
                <span>{attrs[j]}</span>
                <span>
                  <span style={{ fontFamily: display, fontSize: 17, color: C.mute }}>{l}</span>
                  <span style={{ color: C.mute }}> &rarr; </span>
                  <span style={{ fontFamily: display, fontSize: 17,
                                 color: c > l ? C.rise : C.fall }}>{c}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <p style={{ fontSize: 12, color: C.mute, margin: "0 0 10px" }}>Rating history</p>
        <div style={{ ...cell, display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: C.mute }}>Launch</span>
          <b style={{ fontFamily: display, fontSize: 17 }}>{player.l}</b>
        </div>
        {player.h.map((v, i) => {
          const prev = i === 0 ? player.l : player.h[i - 1];
          const dd = v - prev;
          const colour = dd > 0 ? C.rise : dd < 0 ? C.fall : C.mute;
          return (
            <div key={i} style={{ ...cell, display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: C.mute }}>
                Week {weeks[i]}{player.g[i] ? "" : " (no stats)"}
              </span>
              <span>
                <b style={{ fontFamily: display, fontSize: 17, color: colour }}>{v}</b>
                {dd !== 0 && <span style={{ color: colour }}> {dd > 0 ? "+" : ""}{dd}</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ main */

const SORTS = {
  abs: { label: "Biggest change", fn: (a, b) => Math.abs(b.o - b.l) - Math.abs(a.o - a.l) || b.o - a.o },
  up: { label: "Risers first", fn: (a, b) => (b.o - b.l) - (a.o - a.l) || b.o - a.o },
  down: { label: "Fallers first", fn: (a, b) => (a.o - a.l) - (b.o - b.l) || b.o - a.o },
  ovr: { label: "Live overall", fn: (a, b) => b.o - a.o },
  launch: { label: "Launch overall", fn: (a, b) => b.l - a.l },
  name: { label: "Name", fn: (a, b) => a.n.localeCompare(b.n) },
};

export default function LiveRatings({ data, teamNames = {} }) {
  const [q, setQ] = useState("");
  const [pos, setPos] = useState("");
  const [team, setTeam] = useState("");
  const [sort, setSort] = useState("abs");
  const [open, setOpen] = useState(null);

  const players = data.players;
  const positions = useMemo(
    () => [...new Set(players.map((p) => p.p))].sort(), [players]);
  const teams = useMemo(
    () => [...new Set(players.map((p) => p.t))].sort(), [players]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return players
      .filter((p) =>
        (!needle || p.n.toLowerCase().includes(needle)) &&
        (!pos || p.p === pos) && (!team || p.t === team))
      .sort(SORTS[sort].fn);
  }, [players, q, pos, team, sort]);

  const headline = useMemo(
    () => players.filter((p) => p.o !== p.l).sort(SORTS.abs.fn)[0], [players]);

  const control = {
    fontFamily: body, fontSize: 14, color: C.chalk, background: C.panel,
    border: `1px solid ${C.line}`, borderRadius: 3, padding: "9px 11px",
  };
  const th = {
    textAlign: "left", fontSize: 12, fontWeight: 600, color: C.mute,
    padding: "8px 10px", borderBottom: `1px solid ${C.line}`, whiteSpace: "nowrap",
  };
  const td = { padding: "9px 10px", fontSize: 14 };
  const num = { ...td, textAlign: "right", fontFamily: display, fontSize: 20, fontWeight: 600 };

  const lastWeek = data.weeks[data.weeks.length - 1];

  return (
    <div style={{ background: C.ink, color: C.chalk, fontFamily: body,
                  fontVariantNumeric: "tabular-nums", minHeight: "100%" }}>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 20px 80px" }}>
        <header style={{ display: "flex", justifyContent: "space-between",
                         alignItems: "baseline", gap: 16, flexWrap: "wrap",
                         borderBottom: `2px solid ${C.line}`, paddingBottom: 14 }}>
          <h1 style={{ fontFamily: display, fontWeight: 700, fontSize: 40,
                       margin: 0, lineHeight: 1 }}>Madden 26 Live Ratings</h1>
          <div style={{ color: C.mute, fontSize: 14 }}>
            {data.season} season{lastWeek ? `, through week ${lastWeek}` : ""}
          </div>
        </header>

        <Tally up={data.up} down={data.down} held={data.held} />
        <HeadlineMover player={headline}
                       teamName={headline ? (teamNames[headline.t] || headline.t) : ""} />

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
          <input style={{ ...control, flex: 1, minWidth: 190 }} type="search"
                 placeholder="Search a player" aria-label="Search a player"
                 value={q} onChange={(e) => setQ(e.target.value)} />
          <select style={control} aria-label="Filter by position"
                  value={pos} onChange={(e) => setPos(e.target.value)}>
            <option value="">All positions</option>
            {positions.map((x) => <option key={x}>{x}</option>)}
          </select>
          <select style={control} aria-label="Filter by team"
                  value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="">All teams</option>
            {teams.map((x) => <option key={x} value={x}>{teamNames[x] || x}</option>)}
          </select>
          <select style={control} aria-label="Sort"
                  value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>

        <div style={{ color: C.mute, fontSize: 12.5, margin: "10px 0 4px" }}>
          {fmt(rows.length)} players
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 560 }}>
            <thead>
              <tr>
                <th style={th}>Player</th><th style={th}>Pos</th><th style={th}>Team</th>
                <th style={{ ...th, textAlign: "right" }}>Launch</th>
                <th style={{ ...th, textAlign: "right" }}>Live</th>
                <th style={{ ...th, textAlign: "right" }}>Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 300).map((p) => {
                const d = p.o - p.l;
                const colour = d > 0 ? C.rise : d < 0 ? C.fall : C.mute;
                const id = `${p.n}-${p.t}-${p.j}`;
                return (
                  <React.Fragment key={id}>
                    <tr onClick={() => setOpen(open === id ? null : id)}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setOpen(open === id ? null : id);
                          }
                        }}
                        style={{ borderBottom: `1px solid ${C.line}73`, cursor: "pointer" }}>
                      <td style={{ ...td, fontWeight: 500 }}>
                        <span style={{ color: C.mute, fontSize: 12, marginRight: 7 }}>
                          {p.j || ""}
                        </span>{p.n}
                      </td>
                      <td style={td}>{p.p}</td>
                      <td style={td}>
                        <span style={{ display: "inline-block", fontSize: 11,
                                       fontWeight: 600, color: "#FFF", padding: "2px 6px",
                                       borderRadius: 2, minWidth: 36, textAlign: "center",
                                       background: p.c,
                                       border: "1px solid rgba(255,255,255,.28)" }}>
                          {p.t}
                        </span>
                      </td>
                      <td style={{ ...num, color: C.mute }}>{p.l}</td>
                      <td style={{ ...num, color: colour }}>{p.o}</td>
                      <td style={{ ...td, textAlign: "right", fontWeight: 600, color: colour }}>
                        {d > 0 ? "+" : ""}{d || "—"}
                      </td>
                    </tr>
                    {open === id && (
                      <tr>
                        <td colSpan={6} style={{ padding: 0, background: C.detail }}>
                          <Detail player={p} attrs={data.attrs} weeks={data.weeks} />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        <p style={{ marginTop: 34, paddingTop: 16, borderTop: `1px solid ${C.line}`,
                    color: C.mute, fontSize: 12.5, maxWidth: "70ch" }}>
          Launch ratings are preserved permanently, so every number here is measured
          against the rating the player actually shipped with. Attribute changes are
          driven by how far a player beat or missed what someone of his calibre normally
          does, then capped both per week and across the season.
        </p>
      </div>
    </div>
  );
}
