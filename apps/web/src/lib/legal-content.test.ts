import { describe, expect, it } from "vitest";
import { legalDocuments, legalDocumentBySlug } from "./legal-content";

describe("RenderCart legal document templates", () => {
  it("covers the planned policy pages and refund policy", () => {
    expect(legalDocuments.map(({ slug }) => slug)).toEqual([
      "terms",
      "privacy",
      "acceptable-use",
      "dmca",
      "refunds",
    ]);
    expect(legalDocumentBySlug.get("privacy")?.title).toBe("Privacy Policy");
  });

  it("documents temporary files, AI fallback, and required owner review", () => {
    const privacy = legalDocumentBySlug.get("privacy");
    const text = privacy?.sections.flatMap(({ paragraphs }) => paragraphs).join(" ");
    expect(text).toContain("1 to 24 hours");
    expect(text).toContain("OpenRouter");
    expect(text).toContain("must be completed and reviewed");
  });

  it("keeps unresolved business details visibly marked for completion", () => {
    for (const document of legalDocuments) {
      const text = document.sections.flatMap(({ paragraphs }) => paragraphs).join(" ");
      expect(text).toMatch(/\[(?:LEGAL ENTITY NAME|CONTACT EMAIL|JURISDICTION|EFFECTIVE DATE)/);
    }
  });
});
