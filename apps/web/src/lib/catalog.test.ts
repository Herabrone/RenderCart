import { afterEach, describe, expect, it, vi } from "vitest";
import { getCatalog } from "./catalog";
import { clientTools } from "./client-tools";
afterEach(() => vi.unstubAllGlobals());
describe("public tool catalog", () => {
  it("keeps browser tools available when processing services are offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const result = await getCatalog();
    expect(result.unavailable).toBe(true);
    expect(result.tools).toEqual(clientTools);
  });
  it("merges remote and browser tools by stable slug without duplicate destinations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          { ...clientTools[0], name: "duplicate remote entry" },
          {
            slug: "merge-pdf",
            name: "Merge PDF",
            category: "pdf",
            summary: "Combine documents.",
          },
        ],
      }),
    );
    const result = await getCatalog();
    expect(result.unavailable).toBe(false);
    expect(result.tools.filter((t) => t.slug === clientTools[0].slug)).toEqual([
      clientTools[0],
    ]);
    expect(result.tools.some((t) => t.slug === "merge-pdf")).toBe(true);
    expect(result.tools).toHaveLength(clientTools.length + 1);
  });
  it("reports degraded availability on a non-successful API response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );
    expect(await getCatalog()).toEqual({
      tools: clientTools,
      unavailable: true,
    });
  });
});
