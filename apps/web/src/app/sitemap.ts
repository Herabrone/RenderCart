import type { MetadataRoute } from "next";
import { clientTools } from "@/lib/client-tools";
import { legalDocuments } from "@/lib/legal-content";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = process.env.APP_BASE_URL ?? "http://localhost";
  let serverSlugs: string[] = [];
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/tools`, { cache: "no-store" });
    if (response.ok) serverSlugs = ((await response.json()) as Array<{ slug: string }>).map((tool) => tool.slug);
  } catch { /* The client-side tools below still get indexed if the API is offline. */ }
  return [
    { url: baseUrl, changeFrequency: "weekly", priority: 1 },
    { url: `${baseUrl}/tools`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${baseUrl}/pricing`, changeFrequency: "monthly", priority: 0.6 },
    ...legalDocuments.map(({ slug }) => ({
      url: `${baseUrl}/legal/${slug}`,
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
    ...["pdf", "image", "audio-video", "writing", "business", "developer"].map((category) => ({
      url: `${baseUrl}/categories/${category}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...[...serverSlugs, ...clientTools.map((tool) => tool.slug)].map((slug) => ({
      url: `${baseUrl}/tools/${slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
