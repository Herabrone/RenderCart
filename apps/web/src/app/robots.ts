import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.APP_BASE_URL ?? "http://localhost";
  return { rules: { userAgent: "*", allow: "/", disallow: ["/account", "/jobs/", "/api/", "/vault", "/v/", "/p/"] }, sitemap: `${baseUrl}/sitemap.xml` };
}
