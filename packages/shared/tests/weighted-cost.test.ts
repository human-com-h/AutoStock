import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { weightedAverageCostAfterIn } from "../src/rules/weighted-cost";

const fixturesPath = fileURLToPath(new URL("./fixtures/weighted-cost-cases.json", import.meta.url));
const cases = JSON.parse(readFileSync(fixturesPath, "utf-8")) as Array<{
  name: string;
  currentQuantity: number;
  currentAvgCost: number;
  inQuantity: number;
  inUnitCost: number;
  expected: number;
}>;

describe("weightedAverageCostAfterIn (shared fixtures, must match Python side)", () => {
  for (const c of cases) {
    it(c.name, () => {
      const result = weightedAverageCostAfterIn({
        currentQuantity: c.currentQuantity,
        currentAvgCost: c.currentAvgCost,
        inQuantity: c.inQuantity,
        inUnitCost: c.inUnitCost,
      });
      expect(result).toBe(c.expected);
    });
  }

  it("rejects non-positive in quantity", () => {
    expect(() =>
      weightedAverageCostAfterIn({ currentQuantity: 10, currentAvgCost: 500, inQuantity: 0, inUnitCost: 500 })
    ).toThrow();
  });
});
