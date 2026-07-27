import { describe, expect, it } from "vitest";
import { centsToYuan, formatYuan, yuanToCents } from "../src/rules/money";

describe("money conversion", () => {
  it("centsToYuan converts integer cents to yuan", () => {
    expect(centsToYuan(4500)).toBe(45);
    expect(centsToYuan(1)).toBe(0.01);
    expect(centsToYuan(0)).toBe(0);
  });

  it("yuanToCents converts yuan back to integer cents", () => {
    expect(yuanToCents(45)).toBe(4500);
    expect(yuanToCents(0.01)).toBe(1);
  });

  it("formatYuan produces 2-decimal string", () => {
    expect(formatYuan(4500)).toBe("45.00");
    expect(formatYuan(1)).toBe("0.01");
  });
});
