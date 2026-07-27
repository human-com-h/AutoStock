import { describe, expect, it } from "vitest";
import { extractTimestampMs, isValidUlid, newUlid } from "../src/ulid";

describe("ulid", () => {
  it("produces a 26-char crockford base32 string", () => {
    const value = newUlid();
    expect(value.length).toBe(26);
    expect(isValidUlid(value)).toBe(true);
  });

  it("is time ordered", () => {
    const a = newUlid(1_000_000);
    const b = newUlid(1_000_001);
    expect(a < b).toBe(true);
  });

  it("round trips timestamp", () => {
    const ts = 1_722_000_000_000;
    const value = newUlid(ts);
    expect(extractTimestampMs(value)).toBe(ts);
  });

  it("rejects invalid input", () => {
    expect(isValidUlid("too-short")).toBe(false);
    expect(isValidUlid(12345)).toBe(false);
  });
});
