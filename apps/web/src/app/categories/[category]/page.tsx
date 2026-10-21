import { notFound } from "next/navigation";
import { categories, ToolCatalog } from "@/components/tool-catalog";
import { getCatalog } from "@/lib/catalog";
export const dynamic = "force-dynamic";
export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  const selected = categories.find((c) => c.slug === category);
  return selected
    ? {
        title: `${selected.name} | RenderCart`,
        description: selected.description,
      }
    : { title: "Category not found | RenderCart" };
}
export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ category: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const [{ category }, { q = "" }, { tools, unavailable }] = await Promise.all([
    params,
    searchParams,
    getCatalog(),
  ]);
  if (!categories.some((c) => c.slug === category)) notFound();
  const query = q.trim();
  const result = tools.filter(
    (t) =>
      t.category === category &&
      (!query ||
        `${t.name} ${t.summary}`
          .toLocaleLowerCase()
          .includes(query.toLocaleLowerCase())),
  );
  return (
    <ToolCatalog
      tools={result}
      query={query}
      category={category}
      unavailable={unavailable}
    />
  );
}
