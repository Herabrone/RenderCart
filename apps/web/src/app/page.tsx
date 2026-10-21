import {
  ArrowRight,
  ArrowUpRight,
  Search,
  ShieldCheck,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { categories, ToolCard } from "@/components/tool-catalog";
import { getCatalog } from "@/lib/catalog";

export default async function Home() {
  const { tools } = await getCatalog();
  const picks = [
    "merge-pdf",
    "image-converter",
    "word-counter",
    "json-formatter",
    "qr-static",
    "image-resize",
  ]
    .map((slug) => tools.find((t) => t.slug === slug))
    .filter((t): t is NonNullable<typeof t> => !!t)
    .slice(0, 4);
  return (
    <main className="home-page page-width">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">Your everyday workbench</span>
          <h1>
            Less busywork.
            <br />
            <em>More done.</em>
          </h1>
          <p>
            Convert a file. Tidy a document. Bring an idea to life. The tools
            you need, all within reach.
          </p>
          <form className="search-field hero-search" action="/tools">
            <Search size={20} aria-hidden="true" />
            <input
              name="q"
              aria-label="Search tools"
              placeholder="What’s on your to-do list?"
            />
            <button type="submit" className="button button-primary">
              Find a tool <ArrowRight size={16} />
            </button>
          </form>
          <div className="hero-popular">
            <span>TRY THIS</span>
            <Link href="/tools?q=PDF">Merge a PDF</Link>
            <Link href="/categories/image">Resize an image</Link>
            <Link href="/tools/qr-static">Make a QR code</Link>
          </div>
        </div>
        <div
          className="hero-art"
          role="img"
          aria-label="A photo, a document, and a completed task arranged on a workbench"
        >
          <span className="hero-caption">SMALL TOOLS. A LITTLE MOMENTUM.</span>
        </div>
      </section>
      <section className="home-section" aria-labelledby="quick-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">A few good starting points</span>
            <h2 id="quick-title">Make light work of it.</h2>
          </div>
          <Link className="text-link" href="/tools">
            All tools <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="quick-tools">
          {picks.map((tool) => (
            <ToolCard key={tool.slug} tool={tool} />
          ))}
        </div>
      </section>
      <section className="home-section" aria-labelledby="categories-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">A place for every task</span>
            <h2 id="categories-title">What are you working on?</h2>
          </div>
        </div>
        <div className="category-grid">
          {categories.map(({ slug, name, description, icon: Icon }) => (
            <Link
              className="category-tile"
              key={slug}
              href={`/categories/${slug}`}
            >
              <Icon size={24} strokeWidth={1.5} />
              <h3>
                {name}
                <ArrowUpRight size={16} />
              </h3>
              <p>{description}</p>
            </Link>
          ))}
          <Link className="category-tile category-tile-last" href="/tools">
            <ArrowUpRight size={26} />
            <h3>Your next task, sorted.</h3>
            <p>Explore the full tool library.</p>
          </Link>
        </div>
      </section>
      <section className="home-bottom" aria-label="How RenderCart works">
        <div>
          <Zap size={21} />
          <section>
            <h3>Start with what you need.</h3>
            <p>
              Browser tools are free to use. File tools have a free daily
              allowance, with more room when you need it.
            </p>
          </section>
        </div>
        <div>
          <ShieldCheck size={21} />
          <section>
            <h3>Your files have a short stay.</h3>
            <p>
              Uploaded job files expire automatically. Browser tools keep their
              work on your device.
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}
