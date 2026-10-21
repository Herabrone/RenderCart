import Link from "next/link";
import {
  ArrowUpRight,
  Braces,
  Calculator,
  FileText,
  Image,
  LayoutGrid,
  Music2,
  PenLine,
  BriefcaseBusiness,
  Search,
  X,
} from "lucide-react";
export const categories = [
  {
    slug: "pdf",
    name: "PDF & documents",
    short: "PDF",
    description: "Get your documents in order.",
    icon: FileText,
    tone: "terracotta",
  },
  {
    slug: "image",
    name: "Images & design",
    short: "Images",
    description: "A fresh look for every image.",
    icon: Image,
    tone: "sage",
  },
  {
    slug: "audio-video",
    name: "Audio & video",
    short: "Media",
    description: "Make every frame and sound count.",
    icon: Music2,
    tone: "sky",
  },
  {
    slug: "writing",
    name: "Text & writing",
    short: "Writing",
    description: "Find the right words, faster.",
    icon: PenLine,
    tone: "butter",
  },
  {
    slug: "business",
    name: "Business essentials",
    short: "Business",
    description: "The small things that mean business.",
    icon: BriefcaseBusiness,
    tone: "sage",
  },
  {
    slug: "developer",
    name: "Developer tools",
    short: "Developer",
    description: "Less setup. More shipping.",
    icon: Braces,
    tone: "sky",
  },
  {
    slug: "calculators",
    name: "Everyday calculators",
    short: "Calculators",
    description: "Take the guesswork out of your day.",
    icon: Calculator,
    tone: "butter",
  },
];
export type CatalogTool = {
  slug: string;
  name: string;
  category: string;
  summary: string;
  runtime?: string;
};
export function ToolCard({ tool }: { tool: CatalogTool }) {
  const category = categories.find((c) => c.slug === tool.category);
  const Icon = category?.icon ?? LayoutGrid;
  return (
    <Link className="tool-card" href={`/tools/${tool.slug}`}>
      <div className="tool-card-top">
        <span className={`tool-icon tone-${category?.tone ?? "sage"}`}>
          <Icon size={23} strokeWidth={1.6} />
        </span>
        <ArrowUpRight size={19} className="card-arrow" />
      </div>
      <h2>{tool.name}</h2>
      <p>{tool.summary}</p>
      <span className="tool-card-meta">
        {category?.short ?? tool.category}
        {tool.runtime === "client" && (
          <>
            <span aria-hidden="true">·</span>In your browser
          </>
        )}
      </span>
    </Link>
  );
}
export function ToolCatalog({
  tools,
  query = "",
  category = "",
  unavailable = false,
}: {
  tools: CatalogTool[];
  query?: string;
  category?: string;
  unavailable?: boolean;
}) {
  const selected = categories.find((c) => c.slug === category);
  return (
    <main className="library-page page-width">
      <div className="library-heading">
        <div>
          <span className="eyebrow">The tool library</span>
          <h1>{selected?.name ?? "Find your next done."}</h1>
          <p>
            {selected?.description ??
              "Big tasks. Small fixes. A tool for whatever’s next."}
          </p>
        </div>
        <span className="library-label">YOUR EVERYDAY WORKBENCH</span>
      </div>
      <div className="library-layout">
        <aside className="category-nav">
          <p className="nav-label">Browse by category</p>
          <Link
            className={!category ? "selected" : ""}
            href={query ? `/tools?q=${encodeURIComponent(query)}` : "/tools"}
            aria-current={!category ? "page" : undefined}
          >
            <LayoutGrid size={18} />
            All tools
          </Link>
          {categories.map(({ slug, name, icon: Icon }) => (
            <Link
              key={slug}
              href={`/categories/${slug}${query ? `?q=${encodeURIComponent(query)}` : ""}`}
              className={slug === category ? "selected" : ""}
              aria-current={slug === category ? "page" : undefined}
            >
              <Icon size={18} />
              {name}
            </Link>
          ))}
          <div className="library-note">
            <span className="small-mark">↗</span>
            <strong>A little more room?</strong>
            <p>Higher limits and more possibilities with Pro.</p>
            <Link href="/pricing">
              Explore plans <ArrowUpRight size={14} />
            </Link>
          </div>
        </aside>
        <section
          className="catalog-results"
          aria-label={selected?.name ?? "All tools"}
        >
          <form
            className="search-field library-search"
            action={category ? `/categories/${category}` : "/tools"}
          >
            <Search size={20} aria-hidden="true" />
            <input
              name="q"
              aria-label="Search tools"
              defaultValue={query}
              placeholder="Search for a tool or a task…"
            />
            <button type="submit" className="button button-primary">
              Search
            </button>
          </form>
          <div className="results-heading">
            <p>
              {query
                ? `${tools.length} result${tools.length === 1 ? "" : "s"} for “${query}”`
                : `${tools.length} tools to get you moving`}
            </p>
            {query && (
              <Link
                className="text-link"
                href={category ? `/categories/${category}` : "/tools"}
              >
                <X size={14} />
                Clear search
              </Link>
            )}
          </div>
          {unavailable && (
            <p className="service-notice" role="status">
              File processing tools are temporarily unavailable. Browser tools
              are ready to use.
            </p>
          )}
          {tools.length ? (
            <div className="tool-grid">
              {tools.map((tool) => (
                <ToolCard key={tool.slug} tool={tool} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <Search size={34} />
              <h2>{query ? "No tools found" : "Nothing here just yet"}</h2>
              <p>
                {query
                  ? "Try a task like convert, resize, or count. You can also browse another category."
                  : "This category’s tools are unavailable right now. Try the full library."}
              </p>
              <Link className="button button-secondary" href="/tools">
                Browse all tools
              </Link>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
