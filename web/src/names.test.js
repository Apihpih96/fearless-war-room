import { describe, expect, it } from "vitest";
import { shortName, needsShortening } from "./names.js";

describe("shortName", () => {
  it("returns the mapped short name for known teams", () => {
    expect(shortName("Cloud9 Kia")).toBe("C9 Kia");
    expect(shortName("Team Liquid Alienware")).toBe("TL");
    expect(shortName("Shopify Rebellion")).toBe("SR");
    expect(shortName("Maryville University")).toBe("MVU");
    expect(shortName("Cupid Esports")).toBe("CUP");
  });

  it("handles Cloud9 variants not in the map", () => {
    expect(shortName("Cloud9 2027 (reported)")).toBe("C9 2027");
    expect(shortName("Cloud9")).toBe("C9");
    expect(shortName("cloud9 test")).toBe("C9 test");
  });

  it("returns short input unchanged", () => {
    expect(shortName("LYON")).toBe("LYON");
    expect(shortName("FlyQuest")).toBe("FlyQuest");
    expect(shortName("Dignitas")).toBe("Dignitas");
    expect(shortName("Sentinels")).toBe("Sentinels");
  });

  it("truncates long names at word boundaries", () => {
    const result = shortName("Very Long Team Name Here");
    expect(result.length).toBeLessThanOrEqual(13);
    expect(result.endsWith(" ")).toBe(false);
  });

  it("handles edge cases", () => {
    expect(shortName("")).toBe("?");
    expect(shortName(null)).toBe("?");
    expect(shortName(undefined)).toBe("?");
    expect(shortName(123)).toBe("?");
  });
});

describe("needsShortening", () => {
  it("returns true when shortening is applied", () => {
    expect(needsShortening("Cloud9 Kia")).toBe(true);
    expect(needsShortening("Team Liquid Alienware")).toBe(true);
  });

  it("returns false when name is unchanged", () => {
    expect(needsShortening("LYON")).toBe(false);
    expect(needsShortening("FlyQuest")).toBe(false);
  });
});
