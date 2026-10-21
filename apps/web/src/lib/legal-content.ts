export type LegalSection = {
  heading: string;
  paragraphs: string[];
};

export type LegalDocument = {
  slug: string;
  title: string;
  description: string;
  sections: LegalSection[];
};

export const legalDocuments: LegalDocument[] = [
  {
    slug: "terms",
    title: "Terms of Service",
    description: "Draft terms for using RenderCart accounts, tools, subscriptions, and generated files.",
    sections: [
      {
        heading: "About this draft",
        paragraphs: [
          "This is a launch-preparation template, not an approved legal agreement. Replace every bracketed value, confirm the rules for the places where RenderCart will operate, and have qualified counsel review it before accepting customers.",
          "Service operator: [LEGAL ENTITY NAME], located in [JURISDICTION]. Contact: [CONTACT EMAIL]. Effective date: [EFFECTIVE DATE].",
        ],
      },
      {
        heading: "Accounts and access",
        paragraphs: [
          "You are responsible for the accuracy of your account information, protecting your sign-in credentials, and activity carried out through your account. Tell us promptly at [CONTACT EMAIL] if you believe someone has accessed your account without permission.",
          "We may limit or suspend access when reasonably necessary to protect users, the service, or third parties, or to address a suspected breach of these terms. Account closure, data export, and appeal procedures must be completed by the operator before launch.",
        ],
      },
      {
        heading: "Using tools and submitting content",
        paragraphs: [
          "You keep your rights in files, text, and other content that you submit. You authorize RenderCart to process that content only as needed to provide the tool you requested, secure the service, and provide support. You are responsible for having the rights and permissions needed to submit and use that content.",
          "Do not use RenderCart to violate another person's rights, break applicable law, bypass access controls, distribute malware, or interfere with the service. The Acceptable Use Policy describes additional restrictions.",
          "Tools and generated results can contain mistakes or lose formatting. You are responsible for checking outputs before relying on, publishing, or sharing them. Do not rely on a tool output as legal, medical, financial, or other professional advice.",
        ],
      },
      {
        heading: "Plans, payments, and cancellations",
        paragraphs: [
          "Available plans and prices are shown on the pricing page at the time of purchase. The current proposed plans include Pro at $9.99 per month, a day pass, and individual paid jobs; the operator must confirm taxes, renewal terms, currency, and final prices before launch.",
          "Payments are processed by Stripe. Subscription cancellation, renewal, failed-payment handling, and any applicable tax are subject to the checkout details shown when you purchase and the final policy adopted by the operator.",
          "Credits spent on a job that fails are returned according to the service's billing rules. Requests for refunds of money are reviewed manually under the final Refund Policy. Add any mandatory consumer cancellation and refund rights for the selected jurisdiction here.",
        ],
      },
      {
        heading: "Availability and liability",
        paragraphs: [
          "The operator may change, pause, or discontinue a tool, subject to applicable law and any paid-plan commitments. Before launch, counsel must define the service warranty, limitation of liability, indemnity, dispute process, governing law, and any required consumer notices for [JURISDICTION].",
        ],
      },
      {
        heading: "Contact",
        paragraphs: ["Questions about these terms: [LEGAL ENTITY NAME], [POSTAL ADDRESS], [CONTACT EMAIL]."],
      },
    ],
  },
  {
    slug: "privacy",
    title: "Privacy Policy",
    description: "Draft privacy notice describing RenderCart accounts, uploaded files, AI processing, billing, and retention.",
    sections: [
      {
        heading: "About this draft",
        paragraphs: [
          "This draft reflects the planned RenderCart product and must be completed and reviewed for the operator's actual services and jurisdiction before launch. Replace [LEGAL ENTITY NAME], [JURISDICTION], [CONTACT EMAIL], and [EFFECTIVE DATE].",
          "The service operator and data controller (where that term applies) is [LEGAL ENTITY NAME], [POSTAL ADDRESS], [CONTACT EMAIL].",
        ],
      },
      {
        heading: "Information processed",
        paragraphs: [
          "Depending on how you use RenderCart, the service processes account details such as email address and sign-in provider; authentication and security records; plan, purchase, and credit records; tool options and prompts; uploaded files and generated results; job status and error details; and basic request and abuse-prevention logs.",
          "Payment card information is handled by Stripe. RenderCart receives payment and subscription identifiers and related transaction status needed to provide purchases and support billing.",
        ],
      },
      {
        heading: "How files and AI requests are processed",
        paragraphs: [
          "Uploaded files and generated results are stored temporarily and are scheduled for deletion based on the tool and account level, generally within 1 to 24 hours. Some features, such as saved business records or owner-created Vault shares, have separate retention periods and deletion controls. Confirm exact retention by feature before launch.",
          "AI requests are routed to the operator's configured infrastructure first. If local capacity is unavailable and fallback is enabled, text and chat requests may be sent to OpenRouter and its selected model provider. OpenRouter is used for language-model requests; it does not process image background removal, image upscaling, or audio transcription. Do not submit sensitive information unless you are comfortable with the configured processing path.",
          "The operator must document each deployed AI provider, its retention and training settings, processing locations, and any contractual safeguards before launch. Add those details here.",
        ],
      },
      {
        heading: "Service providers and purposes",
        paragraphs: [
          "RenderCart uses service providers for hosting, file storage, email, authentication, payment processing, and (when enabled) AI and self-hosted Umami analytics. Analytics is configured without cookies, excludes URL query strings, respects browser Do Not Track settings, and records public page views and selected product events. The final provider list, locations, and links to provider privacy notices must be added before launch.",
          "Information is used to provide tools and accounts, process payments, secure and troubleshoot the service, prevent abuse, respond to support requests, and meet legal obligations. Analytics does not record account, admin, job, authentication, or Vault pageviews or activity, except for a generic purchase-complete event after a Stripe checkout return.",
        ],
      },
      {
        heading: "Retention and your choices",
        paragraphs: [
          "You can request account access, correction, export, or deletion through [PRIVACY REQUEST URL OR CONTACT EMAIL]. Some transaction, security, or legal records may need to be retained for a limited period where permitted or required by law. State the applicable retention periods and rights for [JURISDICTION] before launch.",
          "Temporary file deletion does not necessarily remove a file you separately downloaded or copied. Explain the effect of account deletion on saved business records, queued jobs, and backups here.",
        ],
      },
      {
        heading: "Security, children, and changes",
        paragraphs: [
          "The operator uses access controls, encryption, and operational safeguards appropriate to the service, but no online service can guarantee absolute security. Document incident contact and breach-notification procedures before launch.",
          "The service is not designed for children under [MINIMUM AGE]. Add the age requirement and any required parental-consent process for the selected jurisdiction.",
          "Material changes will be posted here with an updated effective date. Contact [CONTACT EMAIL] with privacy questions or requests.",
        ],
      },
    ],
  },
  {
    slug: "acceptable-use",
    title: "Acceptable Use Policy",
    description: "Draft rules for lawful and responsible use of RenderCart tools and shared infrastructure.",
    sections: [
      {
        heading: "About this draft",
        paragraphs: [
          "This template must be reviewed against the final tool catalog and applicable law before launch. Operator: [LEGAL ENTITY NAME]. Contact: [ABUSE EMAIL]. Effective date: [EFFECTIVE DATE].",
        ],
      },
      {
        heading: "Prohibited uses",
        paragraphs: [
          "Do not use the service to break applicable law; violate copyright, privacy, publicity, or other rights; evade security, access, or payment controls; create or distribute malware; send spam or phishing; harass or threaten people; or interfere with another user's access to the service.",
          "Do not upload content you do not have permission to process. Do not use AI or media tools to impersonate, deceive, exploit, or target a person without authorization. Restricted tools, if enabled, are available only to the designated super administrator and are not part of the public tool catalog.",
          "Do not attempt to probe, overload, reverse engineer, or disrupt RenderCart infrastructure, other users' data, or connected providers. Do not use automated access except through documented APIs and within their published limits.",
        ],
      },
      {
        heading: "Reports and enforcement",
        paragraphs: [
          "Report suspected abuse or rights violations to [ABUSE EMAIL] and include the relevant URL, tool, or job identifier and enough detail to investigate. The operator may remove content, stop jobs, limit features, or suspend accounts when reasonably necessary to protect the service or comply with law.",
          "Add the final appeal, repeat-infringer, urgent-safety, and law-enforcement response procedures before launch.",
        ],
      },
    ],
  },
  {
    slug: "dmca",
    title: "Copyright and DMCA Notices",
    description: "Draft copyright complaint and counter-notice contact page for RenderCart.",
    sections: [
      {
        heading: "About this draft",
        paragraphs: [
          "This page is an operational template, not a designation of a statutory agent. Before launch, the operator must confirm which copyright procedures apply, complete required registrations, and replace [LEGAL ENTITY NAME], [JURISDICTION], [AGENT NAME], [POSTAL ADDRESS], and [COPYRIGHT EMAIL].",
        ],
      },
      {
        heading: "Submitting a copyright report",
        paragraphs: [
          "Send notices to [COPYRIGHT EMAIL] or [POSTAL ADDRESS]. Include the material claimed to be infringed, the location of the material, your contact information, a description of your rights or authority to act, and any statements required by the law that applies to your notice.",
          "The operator will review complete notices and take action as required by applicable law and the service's procedures. A notice may be shared with the user who submitted the material when needed to investigate or respond.",
        ],
      },
      {
        heading: "Counter-notices and repeat reports",
        paragraphs: [
          "If content was removed in error, contact [COPYRIGHT EMAIL] with the affected content identifier, your contact information, an explanation, and any statements or consent required by applicable law. Do not include a counter-notice process or response deadline until counsel confirms the applicable requirements.",
          "The operator's designated copyright contact, repeat-infringer standard, restoration process, and record-retention procedure must be finalized before launch.",
        ],
      },
    ],
  },
  {
    slug: "refunds",
    title: "Refund Policy",
    description: "Draft policy for RenderCart credits, failed jobs, individual purchases, day passes, and subscriptions.",
    sections: [
      {
        heading: "About this draft",
        paragraphs: [
          "This template must be completed for the selected jurisdiction and reviewed before launch. Operator: [LEGAL ENTITY NAME]. Contact: [BILLING EMAIL]. Effective date: [EFFECTIVE DATE]. Any mandatory consumer rights remain unaffected.",
        ],
      },
      {
        heading: "Failed jobs and credits",
        paragraphs: [
          "Credits held for a job are released when the job fails. If a completed job has a material processing problem, contact [BILLING EMAIL] with the job ID and a short description so the operator can investigate.",
          "Credits are not cash and cannot be transferred unless required by law or expressly stated at purchase. Add rules for expired, unused, promotional, and purchased credit balances before launch.",
        ],
      },
      {
        heading: "Individual purchases and day passes",
        paragraphs: [
          "Requests for a refund of a paid job or day pass are reviewed individually. State the request window, eligibility, and any exceptions approved by the operator here. The current planned workflow is manual review through the billing contact.",
        ],
      },
      {
        heading: "Subscriptions",
        paragraphs: [
          "You may manage or cancel a subscription through account billing. The final checkout terms must state when cancellation takes effect, whether access continues through the current paid period, how renewals work, and how mandatory cancellation rights are handled.",
        ],
      },
      {
        heading: "Requesting help",
        paragraphs: ["Email [BILLING EMAIL] from your account address and include the purchase or job ID. Do not send full payment card numbers by email."],
      },
    ],
  },
];

export const legalDocumentBySlug = new Map(legalDocuments.map((document) => [document.slug, document]));
