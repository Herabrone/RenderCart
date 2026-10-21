"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Brand } from "./brand";

export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menu, setMenu] = useState(false);
  const [dark, setDark] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const auth =
    ["/login", "/signup", "/password-reset"].includes(pathname) ||
    pathname.startsWith("/auth/");
  useEffect(() => {
    const saved = localStorage.getItem("rendercart-theme");
    const enabled =
      saved === "dark" ||
      (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", enabled);
    setDark(enabled);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/auth/me", {
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => setSignedIn(response.ok))
      .catch(() => {});
    return () => controller.abort();
  }, []);
  function toggleTheme() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("rendercart-theme", next ? "dark" : "light");
    setDark(next);
  }
  return (
    <div className="app-frame">
      <a className="skip-link" href="#page-content">
        Skip to content
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Brand />
          <nav className="desktop-nav" aria-label="Main navigation">
            {[
              ["/tools", "All tools"],
              ["/pricing", "Pricing"],
              ["/developers", "For developers"],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={
                  pathname.startsWith(href) ||
                  (href === "/tools" && pathname.startsWith("/categories/"))
                    ? "page"
                    : undefined
                }
              >
                {label}
              </Link>
            ))}
          </nav>
          <div className="header-actions">
            <button
              className="icon-button"
              type="button"
              onClick={toggleTheme}
              aria-label={dark ? "Use light theme" : "Use dark theme"}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <Link
              className="sign-in-link"
              href={signedIn ? "/account" : "/login"}
            >
              {signedIn ? "My workspace" : "Sign in"} <ArrowUpRight size={15} />
            </Link>
            <button
              className="icon-button mobile-menu-button"
              type="button"
              aria-expanded={menu}
              aria-controls="mobile-nav"
              aria-label={menu ? "Close navigation" : "Open navigation"}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={21} /> : <Menu size={21} />}
            </button>
          </div>
        </div>
        {menu && (
          <nav
            id="mobile-nav"
            className="mobile-nav"
            aria-label="Mobile navigation"
          >
            {[
              ["/tools", "All tools"],
              ["/pricing", "Pricing"],
              ["/developers", "For developers"],
              [
                signedIn ? "/account" : "/login",
                signedIn ? "My workspace" : "Sign in",
              ],
            ].map(([href, label]) => (
              <Link key={href} href={href} onClick={() => setMenu(false)}>
                {label}
                <ArrowUpRight size={16} />
              </Link>
            ))}
          </nav>
        )}
      </header>
      <div
        id="page-content"
        tabIndex={-1}
        className={auth ? "auth-layout" : "page-content"}
      >
        {auth && (
          <aside className="auth-aside">
            <span className="eyebrow">A good day to get things done</span>
            <h2>
              One workspace.
              <br />
              <em>So many possibilities.</em>
            </h2>
            <p>
              Everyday tools for the files, ideas, and little tasks on your
              list.
            </p>
            <div
              className="auth-art"
              role="img"
              aria-label="Illustration of files being transformed into finished work"
            />
            <Link className="text-link" href="/tools">
              Explore the tools <ArrowUpRight size={17} />
            </Link>
          </aside>
        )}
        {children}
      </div>
      <footer className="site-footer">
        <div>
          <Brand />
          <p>© {new Date().getFullYear()} RenderCart</p>
        </div>
        <nav aria-label="Legal">
          {[
            ["terms", "Terms"],
            ["privacy", "Privacy"],
            ["acceptable-use", "Acceptable use"],
            ["dmca", "Copyright"],
            ["refunds", "Refunds"],
          ].map(([slug, label]) => (
            <Link key={slug} href={`/legal/${slug}`}>
              {label}
            </Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}
