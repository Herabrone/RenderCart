import { describe, expect, it } from "vitest";

import { convertCurrency, jsonToYaml, md5Hex, yamlToJson } from "@/lib/developer-tools";

describe("MD5 legacy checksums", () => {
  it.each([
    ["", "d41d8cd98f00b204e9800998ecf8427e"],
    ["a", "0cc175b9c0f1b6a831c399e269772661"],
    ["abc", "900150983cd24fb0d6963f7d28e17f72"],
    ["message digest", "f96b697d7cb7938d525a2f31aaf161d0"],
    ["你好🙂", "27892e6b4e92d146e6d547635dd6bf95"],
  ])("hashes %j as %s", (input, expected) => {
    expect(md5Hex(input)).toBe(expected);
  });

  it("limits browser memory use", () => {
    expect(() => md5Hex("x".repeat(1_000_001))).toThrow(/one megabyte/u);
  });
});

describe("JSON and YAML conversion", () => {
  it("round-trips nested JSON values and quoted strings", () => {
    const json = JSON.stringify({ app: "RenderCart", enabled: true, nested: [1, null, "yes"] });
    const yaml = jsonToYaml(json);

    expect(yaml).toContain("app: RenderCart");
    expect(JSON.parse(yamlToJson(yaml))).toEqual(JSON.parse(json));
  });

  it("rejects malformed YAML and oversized input", () => {
    expect(() => yamlToJson("items: [broken")).toThrow();
    expect(() => jsonToYaml(" ".repeat(1_000_001))).toThrow(/one megabyte/u);
  });
});

describe("currency conversion against EUR-based reference rates", () => {
  const rates = { EUR: 1, CAD: 1.6, USD: 1.2 };

  it("converts through the EUR base", () => {
    expect(convertCurrency(100, "CAD", "USD", rates)).toBeCloseTo(75);
    expect(convertCurrency(12.5, "EUR", "EUR", rates)).toBe(12.5);
  });

  it("rejects negative amounts and missing rates", () => {
    expect(() => convertCurrency(-1, "CAD", "USD", rates)).toThrow();
    expect(() => convertCurrency(1, "CAD", "GBP", rates)).toThrow();
  });
});
