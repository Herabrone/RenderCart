import { clientTools } from "./client-tools";
import type { CatalogTool } from "@/components/tool-catalog";
export async function getCatalog(): Promise<{
  tools: CatalogTool[];
  unavailable: boolean;
}> {
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/tools`,
      { cache: "no-store" },
    );
    if (response.ok) {
      const remote = (await response.json()) as CatalogTool[];
      return {
        tools: [
          ...new Map(
            [...remote, ...clientTools].map((t) => [t.slug, t]),
          ).values(),
        ],
        unavailable: false,
      };
    }
  } catch {
    /* The browser tools remain usable while the API is unavailable. */
  }
  return { tools: clientTools, unavailable: true };
}
