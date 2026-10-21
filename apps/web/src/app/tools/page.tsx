import { ToolCatalog } from "@/components/tool-catalog";
import { getCatalog } from "@/lib/catalog";
export const metadata = {
  title: "All Tools | RenderCart",
  description:
    "Find tools for PDFs, images, writing, media, business, development, and everyday calculations.",
};
export const dynamic = "force-dynamic";
export default async function ToolsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const [{ q = "" }, { tools, unavailable }] = await Promise.all([
    searchParams,
    getCatalog(),
  ]);
  const query = q.trim();
  const result = query
    ? tools.filter((t) =>
        `${t.name} ${t.summary} ${t.category}`
          .toLocaleLowerCase()
          .includes(query.toLocaleLowerCase()),
      )
    : tools;
  return <ToolCatalog tools={result} query={query} unavailable={unavailable} />;
}
