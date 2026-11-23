import { describe, expect, it } from "vitest";
import {
  isReportedRoster, getRosterFlags, getRosterLabel, rosterSummary,
  isReportedTeamId, getEloFallbackTeamId, hasCaveats, defaultOpponent,
} from "./roster.js";

const reportedReport = {
  team: { id: "c9-2027", name: "Cloud9 2027", season: "2027 (reported)", reported: true, note: "Reported" },
  sample: { games: 142, caveats: ["Bans are zero"] },
  roster: {
    label: "Cloud9 2027 (reported roster)",
    reported_date: "2026-11-23",
    note: "Reported, not officially confirmed",
    flags: ["Frog: no games in the GRID data; top-lane pool unknown"],
  },
  players: [
    { player: "Frog", role: "top", status: "no_data", games: 0, teams: [], unique_champions: 0, top: [] },
    { player: "Blaber", role: "jungle", status: "ok", games: 142, teams: ["Cloud9 Kia"], unique_champions: 25,
      top: [
        { champion: "Vi", games: 18, record: "12-6" },
        { champion: "Wukong", games: 15, record: "10-5" },
        { champion: "Sejuani", games: 15, record: "9-6" },
        { champion: "Skarner", games: 13, record: "7-6" },
      ]},
  ],
};

const normalReport = {
  team: { id: "47351", name: "Cloud9 Kia", season: "2026" },
  sample: { games: 78 },
  players: [
    { player: "Vulcan", role: "", status: "ok", games: 78, teams: ["Cloud9 Kia"], unique_champions: 16,
      top: [{ champion: "Nautilus", games: 10, record: "5-5" }] },
  ],
};

describe("isReportedRoster", () => {
  it("returns true for reported roster", () => {
    expect(isReportedRoster(reportedReport)).toBe(true);
  });
  it("returns false for normal report", () => {
    expect(isReportedRoster(normalReport)).toBe(false);
  });
  it("returns false for null", () => {
    expect(isReportedRoster(null)).toBe(false);
  });
});

describe("getRosterFlags", () => {
  it("returns flags from reported roster", () => {
    const flags = getRosterFlags(reportedReport);
    expect(flags.length).toBe(1);
    expect(flags[0]).toContain("Frog");
  });
  it("returns empty array for normal report", () => {
    expect(getRosterFlags(normalReport)).toEqual([]);
  });
});

describe("getRosterLabel", () => {
  it("returns roster label", () => {
    expect(getRosterLabel(reportedReport)).toBe("Cloud9 2027 (reported roster)");
  });
  it("falls back to team name", () => {
    expect(getRosterLabel(normalReport)).toBe("Cloud9 Kia");
  });
});

describe("rosterSummary", () => {
  it("returns summary for each player", () => {
    const summary = rosterSummary(reportedReport);
    expect(summary.length).toBe(2);
    expect(summary[0].player).toBe("Frog");
    expect(summary[0].status).toBe("no_data");
    expect(summary[0].games).toBe(0);
    expect(summary[1].player).toBe("Blaber");
    expect(summary[1].top.length).toBe(3); // capped at 3
  });
  it("returns empty for null report", () => {
    expect(rosterSummary(null)).toEqual([]);
  });
});

describe("isReportedTeamId", () => {
  it("recognizes c9-2027", () => {
    expect(isReportedTeamId("c9-2027")).toBe(true);
  });
  it("returns false for normal ids", () => {
    expect(isReportedTeamId("47351")).toBe(false);
  });
});

describe("getEloFallbackTeamId", () => {
  it("falls back to 47351 for c9-2027 when 47351 exists in model", () => {
    const model = { teams: { "47351": { rating: 1600 } } };
    expect(getEloFallbackTeamId("c9-2027", model)).toBe("47351");
  });
  it("returns original id if no fallback available", () => {
    const model = { teams: {} };
    expect(getEloFallbackTeamId("c9-2027", model)).toBe("c9-2027");
  });
  it("returns original id for non-reported teams", () => {
    const model = { teams: { "47351": { rating: 1600 } } };
    expect(getEloFallbackTeamId("47351", model)).toBe("47351");
  });
  it("handles null model", () => {
    expect(getEloFallbackTeamId("c9-2027", null)).toBe("c9-2027");
  });
});

describe("hasCaveats", () => {
  it("returns true when caveats exist", () => {
    expect(hasCaveats(reportedReport)).toBe(true);
  });
  it("returns false when no caveats", () => {
    expect(hasCaveats(normalReport)).toBe(false);
  });
});

describe("defaultOpponent", () => {
  const teams = [
    { id: "47351", name: "Cloud9 Kia", lcs_2026: true },
    { id: "54198", name: "LYON", lcs_2026: true },
    { id: "47363", name: "Team Liquid Alienware", lcs_2026: true },
    { id: "c9-2027", name: "Cloud9 2027", lcs_2026: false, reported: true },
    { id: "48179", name: "Dplus KIA", lcs_2026: false },
  ];

  it("never returns c9-2027 as default opponent", () => {
    expect(defaultOpponent("c9-2027", teams)).not.toBe("c9-2027");
  });

  it("never returns 47351 (Cloud9 Kia) as default opponent", () => {
    expect(defaultOpponent("c9-2027", teams)).not.toBe("47351");
  });

  it("picks first non-C9 LCS 2026 team when us is c9-2027", () => {
    // LYON (54198) is the first LCS 2026 team after skipping 47351
    expect(defaultOpponent("c9-2027", teams)).toBe("54198");
  });

  it("picks first non-C9 LCS 2026 team when us is 47351", () => {
    expect(defaultOpponent("47351", teams)).toBe("54198");
  });

  it("excludes the us team from results", () => {
    expect(defaultOpponent("54198", teams)).not.toBe("54198");
    // Should pick Team Liquid (47363) since 47351 is excluded and 54198 is us
    expect(defaultOpponent("54198", teams)).toBe("47363");
  });

  it("falls back to non-LCS 2026 team when no LCS 2026 available", () => {
    const nonLcsTeams = [
      { id: "47351", name: "Cloud9 Kia", lcs_2026: false },
      { id: "c9-2027", name: "Cloud9 2027", lcs_2026: false },
      { id: "48179", name: "Dplus KIA", lcs_2026: false },
    ];
    expect(defaultOpponent("c9-2027", nonLcsTeams)).toBe("48179");
  });

  it("returns empty string for empty teams array", () => {
    expect(defaultOpponent("c9-2027", [])).toBe("");
  });

  it("returns empty string for null teams", () => {
    expect(defaultOpponent("c9-2027", null)).toBe("");
  });
});
