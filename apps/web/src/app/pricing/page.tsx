import Link from "next/link";
import { ArrowUpRight, Check } from "lucide-react";
export const metadata = {
  title: "Pricing | RenderCart",
  description:
    "Start free, get a day pass, or make room for more with RenderCart Pro.",
};
const plans = [
  {
    name: "Free",
    note: "For the everyday things",
    price: "$0",
    cadence: "always",
    copy: "A useful place to start. No card required.",
    cta: "Explore free tools",
    href: "/tools",
    features: [
      "Free browser tools",
      "Daily allowance on file tools",
      "Starter upload limits",
    ],
  },
  {
    name: "Pro",
    note: "Room for your whole workflow",
    price: "$9.99",
    cadence: "per month",
    copy: "More files, bigger ideas, fewer interruptions.",
    cta: "Choose Pro",
    href: "/account/billing",
    features: [
      "Higher file and usage limits",
      "1,000 AI credits each month",
      "Batch processing & priority queue",
      "24-hour job file retention",
      "Public API access",
    ],
  },
  {
    name: "Day pass",
    note: "For the one big day",
    price: "$2.99",
    cadence: "one payment · 24 hours",
    copy: "A little extra power, without a subscription.",
    cta: "Get a day pass",
    href: "/account/billing",
    features: [
      "Pro access for 24 hours",
      "150 credits for your day",
      "Higher upload limits",
      "24-hour job file retention",
    ],
  },
];
export default function PricingPage() {
  return (
    <main className="pricing-page">
      <header className="pricing-heading">
        <span className="eyebrow">A plan for your kind of day</span>
        <h1>
          Start small.
          <br />
          Make room for more.
        </h1>
        <p>
          Keep the everyday tools free. Choose extra capacity when your work
          calls for it.
        </p>
      </header>
      <div className="pricing-grid">
        {plans.map((plan) => (
          <article
            key={plan.name}
            className={`price-card ${plan.name === "Pro" ? "recommended" : ""}`}
          >
            <span className="plan-note">{plan.note}</span>
            <h2>{plan.name}</h2>
            <div className="price-amount">
              {plan.price} <span>{plan.cadence}</span>
            </div>
            <p>{plan.copy}</p>
            <Link
              className={`button ${plan.name === "Pro" ? "button-primary" : "button-secondary"}`}
              href={plan.href}
            >
              {plan.cta}
              <ArrowUpRight size={16} />
            </Link>
            <ul>
              {plan.features.map((feature) => (
                <li key={feature}>
                  <Check size={15} />
                  {feature}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      <section className="pricing-faq">
        <h2>A few useful details.</h2>
        <details>
          <summary>Can I just pay for one job?</summary>
          <p>
            Yes. Eligible tools offer a single-job purchase, usually $0.99,
            $1.99, or $2.99. The tool shows its price before checkout, including
            any configured price override.
          </p>
        </details>
        <details>
          <summary>What are credits used for?</summary>
          <p>
            Credits cover compute-heavy AI work. Each tool shows its cost before
            you run it. Basic file tools and browser tools do not spend AI
            credits. Monthly Pro credits reset each billing cycle; day-pass
            credits expire with the pass.
          </p>
        </details>
        <details>
          <summary>Do I need an account to try RenderCart?</summary>
          <p>
            Browser tools work without an account. You can also try supported
            file tools as a guest within their free limits. Create an account
            for more daily capacity and job history.
          </p>
        </details>
        <details>
          <summary>How do I manage my subscription?</summary>
          <p>
            Open Billing and credits in your workspace, then choose Manage
            subscription to use Stripe’s customer portal.
          </p>
        </details>
      </section>
    </main>
  );
}
