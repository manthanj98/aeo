# PR/FAQ — AI Visibility (Atlas)

**Working title:** Atlas AI Visibility
**Status:** Draft for review — not approved
**Owner:** Product (Atlas)
**Reviewers:** Engineering, Design, Data, Creator Ops, GTM
**Version:** 0.1 · 2026-07-30
**Source of truth for scope:** the clickable prototype `pepperproject.standalone.html` (Acme demo tenant)

**How to read this document.** Sections 1–3 are the Amazon-style PR/FAQ: the press
release we would publish on launch day, the questions a customer will ask, and the
questions we have to answer internally before we build. Sections 4–11 are the
requirements the PR/FAQ commits us to — surface by surface, with metric definitions,
data sources, and the things we are explicitly *not* building. Teams building in Atlas
should treat §4–§8 as the shared contract and §11 as the list of things still to settle.

Every number, label, and column in §4–§7 is taken from the prototype. Anything not
evidenced by the prototype is marked **[ASSUMPTION]** or **[OPEN]**. Do not build
against an **[OPEN]** item without closing it first.

---

## 1. Press release

### Pepper launches AI Visibility in Atlas — see how AI answer engines describe your brand, and fix it in the same place

**Subhead:** One dashboard for how a brand shows up across ChatGPT, Perplexity, Google
AI Overviews, Microsoft Co-Pilot, and Claude — joined to Search Console and Analytics,
with prioritised insights that turn into published content.

**Bengaluru — [LAUNCH DATE]** — Pepper today announced AI Visibility, a new product in
the Atlas platform that shows marketing teams exactly how AI answer engines represent
their brand, why it is changing, and what to publish to change it. AI Visibility is
available to Atlas customers starting today.

Buyers have stopped starting with a list of ten blue links. They ask an assistant, read
one synthesised answer, and act on it. That answer names a handful of brands and cites a
handful of URLs — and most marketing teams have no idea whether they are in it. The
analytics stack they trust was built for a world of rankings and clicks: Search Console
tells them where they rank, Analytics tells them what happened after a visit, and
neither one can tell them that a competitor is now the brand ChatGPT recommends when
someone asks about pricing.

AI Visibility closes that gap. Teams pick the prompts that matter to their category,
and Atlas runs them across five answer engines on a schedule, by region and device. For
each prompt it records whether the brand was mentioned, in what position, with what
sentiment, and which URLs were cited — the brand's and its competitors'. Six metrics
roll that up: Visibility, Mention Rate, Share of Voice, Citation Rate, Sentiment, and
Average Position. Each one is defined in plain language in the product, so a CMO and an
SEO analyst are reading the same number the same way.

The part teams tell us they cannot get anywhere else is the join. AI Visibility puts
answer-engine citations, Search Console performance, and Analytics outcomes on the same
row, for the same URL, over the same period — a 360-degree view of every page. A page
with strong impressions and a weak citation rate is a structured-data problem. A page
gaining both citations and clicks is a page to defend. A page cited constantly but
untouched for six months is about to start slipping. Those are different jobs, and
until now they looked identical in a spreadsheet.

Atlas does not stop at the chart. AI Visibility continuously scans the joined data and
surfaces insights ranked by severity, each one written as a claim with a root cause and
a business impact — "Pricing-related prompts have zero brand citations this month",
traced to competitors owning pricing-comparison answers, with the pipeline consequence
spelled out. Every insight carries one action: draft the article that closes the gap, or
update the article that is losing ground. Atlas generates the draft or the proposed
change set, shows what changed and why, and publishes to the customer's CMS. When a team
would rather have a specialist do it, they can hand the insight to a top-3% creator on
the Pepper platform from the same screen.

"We could see our rankings were fine and our AI mentions were falling, and nobody could
tell us which one to worry about," said [CUSTOMER NAME], [TITLE] at [CUSTOMER COMPANY].
"AI Visibility told us pricing prompts were the hole, showed us who was in there
instead of us, and had a draft ready. That used to be a three-week investigation."
**[ASSUMPTION — placeholder quote, to be replaced with a real design-partner quote before launch]**

"Dashboards that only measure are a tax on the team," said [PEPPER EXEC], [TITLE] at
Pepper. "The reason we built this into Atlas is that Atlas already knows how to make
content and already has the creators. Seeing the gap and closing it should not be two
different products."

AI Visibility is available now to Atlas customers. Connect a domain, Google Search
Console, and Google Analytics; Atlas proposes a starting prompt set, keyword set, and
competitor set from the category, and the first full report lands within [X] days.
Visit [URL] to get started.

---

## 2. Customer FAQ

**What exactly does this measure?**
Six metrics, over the prompts you choose to track, across five answer engines:

| Metric | Definition (as shown in-product) |
| --- | --- |
| Visibility | Overall visibility across tracked prompts, weighted by mention rate, position, and share of voice. |
| Mention Rate | Answers mentioning your brand ÷ total answers (0–100%). Higher means greater visibility. |
| Share of Voice | Answers mentioning your brand ÷ answers mentioning your brand **or** a competitor (0–100%). Higher means you dominate the conversation relative to competitors. |
| Citation Rate | Answers citing your domain ÷ total answers with at least one citation (0–100%). Multiple URLs from the same domain count once. |
| Sentiment | Positive mentions + half of neutral mentions ÷ total brand mentions (0–100). |
| Average Position | Average position of your brand's mention within the answer (1 = first mention). Lower is better. |

**Which answer engines are covered?**
ChatGPT, Perplexity, Google AI Overviews, Microsoft Co-Pilot, and Claude. Every metric,
table, and filter can be scoped to one engine or viewed across all five.

**How do you decide which prompts to track?**
You do — and Atlas helps. You add prompts freely, group them into topics you name, and
Atlas suggests more based on your category and where competitors are being cited. Each
prompt is classified Brand Related or Category Related and carries a search volume, so
you can tell a high-intent prompt from a vanity one. There is also a Copilot: describe
the buyer you care about in plain language and it proposes prompts you can accept with
one click.

**How often does the data refresh?**
You choose: daily, weekly, every two weeks, or monthly. Weekly is the default.

**Can I see the actual AI answers, not just the score?**
Yes. Prompt Mentions shows every individual answer we collected — the engine, whether
you were mentioned, your position, the sentiment, the date, how many citations it
carried, and an excerpt. Answer History goes further, per prompt: date, persona,
platform, answer preview, whether you were cited, whether you were mentioned, which
competitors appeared, and whether the answer carried ads.

**Does it show paid placement in AI answers?**
It reports Paid Share of Voice by competitor for ChatGPT Ads, and flags whether an
individual answer contained ads. **[OPEN — coverage limited to ChatGPT Ads in v1;
other engines' ad surfaces are not committed.]**

**Can I compare myself to competitors?**
Yes, on one table: authority score, monthly traffic, keyword count, backlinks, plus all
five AEO metrics, average AEO position, shared keyword count, and average SERP position
on those shared keywords. Atlas also recommends competitors it sees appearing alongside
you in AI answers, so the tracked set stays current.

**How does this connect to the SEO reporting I already have?**
It is the same product, not a neighbour. Search Console and Analytics are joined to
answer-engine data per URL in the Pages view, and the Performance view carries organic
KPIs (average position, CTR, clicks, impressions) and audience KPIs (users, sessions,
engagement rate, conversions, revenue) alongside the AEO metrics for the same period.
Sitemap indexation and backlink authority are tracked in the same place.

**What do I actually do with an insight?**
Each insight names one action — draft a new article, or update an existing one. Atlas
generates the draft, or for an update, the specific proposed changes with the reason for
each. You review, then publish to your CMS. If you would rather hand it to a
specialist, you can request a top-3% Pepper creator from the same card.

**Will AI-generated content sound like our brand?**
Brand Guidelines is a first-class surface, not a settings page. Voice and tone,
typography, colour, and component rules live there, plus free-text guidance notes you
add ("always link back to the source report"). Atlas suggests guidance based on the
mistakes it commonly sees in AI summaries for your category, and applies these rules to
everything it drafts.

**Can I slice by market and device?**
Region (United States, United Kingdom, India, Brazil), device (desktop, mobile, tablet),
engine, date range, and preset windows of 7 / 30 / 90 / 180 days and 12 months.

**Can I get the data out?**
Keyword data exports to CSV in v1. **[OPEN — API access and exports for prompts,
pages, and competitors are not committed for v1.]**

---

## 3. Internal FAQ

**Why is Pepper the right company to build this?**
Every competitor in this category — AthenaHQ, Profound, Peec AI, Scrunch AI, and the
incumbents adding AEO modules — stops at measurement. They tell a customer they have a
citation gap and leave the work on the customer's desk. Pepper already has the content
engine and the creator marketplace, so we can close the loop in one product: detect,
draft, publish, and if the customer wants a human, staff it. Measurement is the wedge;
the content is the business.

**Why now?**
The buying journey has already moved and the measurement layer has not. Teams are
currently trying to reason about AI visibility from Search Console impressions and
anecdote. The prototype's own insight set is the argument: single-engine concentration
risk, zero citations on pricing prompts, competitors owning a positioning cluster —
these are decisions being made blind today.

**What is the wedge vs. the moat?**
Wedge: the joined 360-degree view per URL. Nobody else has answer-engine citations,
Search Console, and Analytics on the same row, and it is the join that makes an insight
diagnosable rather than merely alarming. Moat: insight → draft → publish → creator.
Each loop makes the next insight better and pulls content spend onto Atlas.

**Who is the primary user?**
The person accountable for organic growth — Head of SEO / Content, or a growth marketer
at a mid-market or enterprise B2B company. Secondary: the CMO who reads Performance and
Insights only, and the analyst who lives in Pages, Keywords, and Competitors.
**[ASSUMPTION — persona set inferred from the prototype's information density and
metric vocabulary; validate with design partners.]**

**Where does the data come from, and what do we have to build?**

| Data | Source | Build |
| --- | --- | --- |
| Answer-engine responses, mentions, positions, citations, sentiment | Prompt execution against five engines, per region/device, on the customer's schedule | **New.** Core collection infrastructure. Biggest technical risk. |
| Organic performance (impressions, clicks, CTR, position), sitemaps, index coverage | Google Search Console | Integration |
| Audience and revenue (users, sessions, engagement, conversions, revenue) | Google Analytics | Integration |
| Keyword volume, difficulty, value, SERP features; backlinks, referring domains, authority; competitor traffic/keywords/backlinks | Third-party SEO data provider | **[OPEN — vendor not selected. Material cost and coverage decision; blocks Keywords, Backlinks, and half of Competitors.]** |
| Prompt / keyword / competitor / guidance recommendations, insight generation, article drafting | Pepper AI layer + Atlas content engine | **New** |
| Publishing | Customer CMS | Integration. **[OPEN — which CMSes ship in v1.]** |
| Creator handoff | Pepper creator marketplace | Integration |

**How do prompts actually get executed, and what does it cost?**
This is the question that decides the product's unit economics and it is not answered by
the prototype. Cost scales as `prompts × engines × regions × devices × refresh
frequency`, and the prototype offers daily refresh across 5 engines and 4 regions as a
customer-facing toggle. **[OPEN — required before build: per-engine access method
(official API, partner, or other), rate limits, cost per execution, whether device
segmentation is genuinely observable or modelled, and the resulting caps we must put on
tracked-prompt counts per plan.]** Do not ship a daily × all-regions toggle until this
is closed.

**Are the AEO metrics comparable across engines?**
Not naively, and the prototype presents them as if they are. Engines differ in answer
length, citation habits, and how often they name brands at all, so a 20% citation rate
on Google AI Overviews and on Claude are not the same achievement. **[OPEN — decide
whether Visibility is normalised per engine and whether cross-engine tables need a
comparability caveat in-product.]** We ship the definitions verbatim in-product either
way; a metric nobody can reproduce is a support ticket.

**How is sentiment computed and how do we defend it?**
The formula is fixed and published (positive + ½ neutral ÷ total mentions), but the
per-mention classification behind it is a model call. **[OPEN — classifier choice,
measured accuracy, and whether customers can inspect or override a classification. A
customer will eventually dispute a "negative" and we need an answer.]**

**How are insights generated — rules or model?**
The prototype's twelve insights are all recognisable patterns over the joined data:
citation decline on a URL, zero citations on a prompt cluster, citations and impressions
rising together, high impressions with low CTR, strong SEO with low citations,
competitor-cited content gap, mentions up with sentiment down, single-engine
concentration, stale high-citation page, under-indexed engine, unlinked brand mentions,
and community discussion without presence. That reads as a rules library with model-written
narration, which is also the right v1: deterministic detection is explainable and
testable, and the model only writes the root cause, impact, and draft.
**[OPEN — confirm this split with Data/ML, and define thresholds per pattern.]**

**What is the risk in "Publish to CMS"?**
Reputational, and it is the highest-consequence button in the product. Atlas would be
writing to a customer's live site based on a machine-generated draft. Requirements:
publishing is never automatic, a human approves every change, updates show a
before/after diff (the prototype states this explicitly as pending), every publish is
attributed and reversible, and Brand Guidelines are applied before a draft is shown.
**[OPEN — approval roles and audit-trail requirements.]**

**Does the creator handoff cannibalise or compound?**
Compounds, and it is the reason the product exists commercially. The insight is the
qualified brief: it already names the gap, the prompts, the competitors, and the target
page. **[OPEN — commercial model for the handoff: bundled credits, marketplace rate,
or lead-gen into services. Owner: GTM.]**

**What is the pricing model?**
**[OPEN — nothing in the prototype indicates pricing. Must be resolved with the
prompt-execution cost model above, since tracked prompts, engines, regions, and refresh
frequency are the cost drivers and therefore the natural metering dimensions.]**

**What did we find in the prototype that is not in scope?**
Three sets of scaffolding exist in the prototype's logic but render nowhere: a
four-step tracking setup wizard (Keywords → Target → Search settings → Review), a
seven-tab SEO report shell (Positions, Overview, Landing pages, Competitors' pages,
Tracking visibility, Tracking overview, Competitors discovery), and competitor
leaderboards ranked by each of the five AEO metrics. Treat these as intent, not
commitment — see §9.

**What are the top three risks?**
1. **Engine access.** If we cannot execute prompts reliably and affordably across five
   engines, there is no product. Everything else is downstream. Mitigate by proving
   collection on two engines before building breadth.
2. **Metric credibility.** The product's authority rests on numbers a customer cannot
   independently verify. One indefensible sentiment score or unreproducible citation
   rate costs more trust than a missing feature.
3. **Publishing blast radius.** An automated change to a customer's live site that
   breaks brand or accuracy is the fastest way to lose an enterprise account.

**What breaks if we ship only the dashboard?**
We become a more expensive version of four competitors, and we hand our content
opportunity to whoever the customer already uses. The insight → draft → publish path is
not a phase-two nicety; it is the differentiation. If scope must be cut, cut breadth of
surfaces, not depth of the loop.

---

## 4. Product requirements — global

### 4.1 Information architecture

The left navigation is grouped, and the grouping is the product's mental model. Ship it
as-is.

| Group | Surface | Purpose |
| --- | --- | --- |
| **Overview** | Performance | AEO + organic + audience KPIs for the period |
| | Insights | Ranked, actionable patterns |
| **360 Degree View** | Pages | Per-URL join of citations, search, analytics |
| | Prompts | The tracked prompt set and per-answer evidence |
| | Keywords | Tracked keyword rankings and search performance |
| | Competitors | Relative authority, traffic, and AEO share |
| **Monitoring** | Sitemaps | Submission and indexation status |
| | Backlinks | Referring domains and authority |
| **Brand Artifacts** | Brand Guidelines | Tokens, voice, and rules applied to generated content |

Default surface on load: Performance.

### 4.2 Global controls

- **Domain context** — the tenant's domain is always visible in the top bar (`acme.com`
  in the prototype). Single domain per workspace in v1. **[ASSUMPTION]**
- **Refresh frequency** — daily / weekly / every 2 weeks / monthly, default weekly, set
  from the top bar and applied to prompt execution. Gated by §3's cost model.
- **Date range** — explicit from/to pickers with min/max coupling (From cannot exceed
  To), plus preset windows of 7d / 30d / 90d / 180d / 12mo on analytical surfaces.
- **Filters** — region (United States, United Kingdom, India, Brazil), device (all,
  desktop, mobile, tablet), engine (all five, individually selectable). Filter state is
  per-surface in the prototype; **[OPEN — should filters be global and sticky? Per-surface
  state is a real usability cost when a user is comparing two surfaces.]**
- **Copilot** — one drawer, context-aware by surface: Prompt Copilot, Keyword Copilot,
  Competitor Copilot, Brand Copilot. Accepts free text, returns suggestions the user
  adds with one click, and suggestions disappear once accepted.
- **Comparison baseline** — every trend, delta, and "▲/▼ vs prior" reads against the
  immediately preceding period of equal length. This must be stated in-product.

### 4.3 Interaction patterns to standardise

These recur on every surface and should be built once:

1. **Inspection drawer** — right-hand overlay opened from a per-row eye icon; closes on
   scrim click; used for prompts, pages, keywords, and insights.
2. **Recommendation panel** — inline card listing platform-suggested items with `+ Add`
   per item, shown above the table it feeds, hidden when empty.
3. **KPI tile** — label with an `i` affordance revealing the metric's full definition on
   hover, value, and a coloured delta against the prior period.
4. **Metric table** — value plus signed trend in a single cell, coloured positive /
   negative / neutral, horizontally scrollable with a minimum width rather than
   collapsing columns.
5. **Zero states** — a newly tracked prompt renders a complete zero-value row (0.0% with
   +0.0 pts trends), never blanks.

---

## 5. Product requirements — Overview surfaces

### 5.1 Performance

Three stacked sections against one shared period and filter set (region, time range,
device):

1. **AEO Metrics** — six KPI tiles: Visibility, Mention Rate, Share of Voice, Citation
   Rate, Sentiment, Average Position. Each with prior-period delta and hover definition
   (§2 table is the canonical copy — ship these strings verbatim).
2. **Visibility by AI engine** — one row per engine: visibility score, mention rate,
   share of voice, citation rate, sentiment score, average position.
3. **Top competing brands** — the brands appearing most often alongside the customer,
   with a per-brand note.
4. **Search Performance** — from Search Console: average position, average CTR, total
   clicks, total impressions, each with prior-period delta.
5. **Marketing Performance** — from Analytics: users, sessions, engagement rate,
   conversions, revenue, each with prior-period delta.

### 5.2 Insights

The most important surface in the product. Each insight is a card containing:

- **A title written as a claim**, naming the entity — a URL, a prompt cluster, an engine.
  Not a metric name.
- **Severity** — High / Medium / Low, colour-coded, and the default sort order.
- **Recency** — relative age ("12h", "3d", "1w").
- **A headline statistic** with its delta and a supporting micro-chart. The prototype
  uses line, bar, horizontal-bar, and donut forms, chosen per insight; the chart form is
  a property of the insight type, not a user choice.
- **Root cause** — a tagged attribution (e.g. "Google AI Overviews · 71% of citations")
  plus a sentence of explanation, and a link into the detailed breakdown.
- **Business impact** — an impact level and a paragraph in business terms (pipeline,
  brand perception, resilience), not metric terms. This is what makes the surface
  readable by a CMO.
- **Exactly one action** — `Draft article →` or `Update article →`.

**Detailed breakdown drawer:** headline stat, trend chart, top contributors (dimension,
value, share, supporting count), a "How it developed" period-by-period timeline
(period / status / detail), and "Why it matters".

**Article drawer:** shows provenance ("Generated from: <insight title>") and then either
generated draft paragraphs (new article) or a list of proposed changes, each with a
label and a detail, plus the reason for the change (new-vs-update is determined by the
insight, not the user). Terminates in `Publish to CMS`, with a published-state
confirmation. The prototype notes the before/after diff for updates is not yet built —
**it is required before this ships** (§3).

**Creator handoff:** a persistent panel offering connection to a top-3% Pepper creator,
with a request-sent state. Requirements for the request payload and routing are
**[OPEN — Creator Ops]**.

**Insight patterns to implement in v1** — the twelve in the prototype, which double as
the detection backlog: citation-rate decline on a URL; zero citations on a prompt
cluster; citations and impressions rising together; high impressions + low CTR + high
citation rate; strong SEO + low citations; competitor-cited content gap; mentions up +
sentiment down; single-engine concentration; stale high-citation page; under-indexed
engine; unlinked brand mentions on high-authority domains; community discussion without
brand presence. Thresholds per pattern are **[OPEN]**.

---

## 6. Product requirements — 360 Degree View surfaces

### 6.1 Pages

A single table with three column groups under one header, filtered by region, time
range, device, and engine:

| Group | Columns |
| --- | --- |
| AEO Health | Citations (with delta), Average citation position (with delta) |
| Site Engagement | Traffic (with delta), Engagement, Conversions |
| Search Performance | Average position, Impressions, Clicks, CTR (each with delta) |

Each row shows the URL and its top prompt. The three-group header is the product's core
claim rendered as a table — do not flatten it.

**URL inspection drawer:** AEO KPIs for the URL (citations, citation rate, average
position) with the same filter set; visibility by engine (citation rate, average
position, citation share); top 5 prompts driving citations with mention rate; Site
Engagement block (sessions, traffic, engagement, conversions) with a traffic sparkline;
Search Performance block (clicks, impressions, CTR, position) with a CTR sparkline; and
index coverage with a verdict and crawl detail.

### 6.2 Prompts

Two tabs — **Your prompts** and **Prompt Mentions** — over a shared filter bar (date
range, region, platform), with search, `Edit Topics`, `+ Add Prompts`, and `Ask Copilot`.

**Your prompts.** One row per tracked prompt: prompt text, topic (colour-coded), prompt
type (Brand Related / Category Related), volume, mention rate, citation rate, share of
voice, and positive rate — mention, citation, and SoV each with a signed trend. Rows are
removable and open an inspection drawer. Below the table, visibility by AI engine
(citation rate, average position, citation share). Above it, when present, the
platform-recommended prompt panel with topic attribution and `+ Add`.

- **Topics** are user-defined, named, colour-coded groupings, editable in a modal, and
  creatable inline while adding a prompt. The prototype ships five as a starting set.
- **Prompt inspection drawer:** topic, type, volume, mention rate, citation rate,
  positive rate; visibility by engine; top competitors with a per-competitor note; and
  share of voice by competitor, ranked.

**Prompt Mentions.** Per-answer evidence, filterable by engine: prompt text, response
excerpt, engine, mentioned (yes/no), position, sentiment, date, citation count. Selecting
a row opens a full analysis: prompt visibility over time, mention rate by competitor,
mention rate by platform, Paid Share of Voice by competitor (ChatGPT Ads), and **Answer
History** — date, persona, platform, answer preview, cited, mentioned, competitors, and
whether the answer carried ads.

- **Personas** appear as a dimension on Answer History and as a filter chip. **[OPEN —
  persona is a first-class concept in the data model but has no management UI in the
  prototype. Define whether personas are user-authored, and how they parameterise prompt
  execution, before building this surface.]**

### 6.3 Keywords

Tracked keyword set with add / remove, search, CSV export, and the shared date / region /
platform filters. Columns: keyword, impressions, clicks, CTR, position, change, volume,
SERP features, traffic value, keyword difficulty. Platform-recommended keywords appear in
a recommendation panel; Keyword Copilot proposes more. Inspection drawer covers search
performance, ranking details, and SERP features.

### 6.4 Competitors

Tracked competitor domains with add / remove and the shared filters, plus a
recommendation panel for domains appearing alongside the brand in AI answers.

**Competitor Comparison table** — one row per domain: authority, monthly traffic,
keyword count, backlinks, mention rate, citation rate, share of voice, sentiment,
average AEO position, shared keyword count, and average SERP position on shared
keywords. The customer's own domain appears in the table and is not removable.

---

## 7. Product requirements — Monitoring and Brand Artifacts

### 7.1 Sitemaps

Per sitemap on the property: sitemap URL, status, submitted vs. indexed counts, last
downloaded, warnings. Sourced from Search Console.

### 7.2 Backlinks

Root-domain authority summary: authority score, total backlinks, referring domains,
referring URLs, and a dofollow/nofollow split with a ratio check. Referring-domain table:
domain, authority score, backlink count, link type, first seen. Dependent on the SEO data
vendor decision (§3).

### 7.3 Brand Guidelines

A living style guide plus a rules store, both of which feed generated content:

- **Voice & tone** — the written standard applied to drafts.
- **Typography, colour palette, elevation & components** — rendered directly from the
  live design tokens, so the documentation cannot drift from the system it documents.
  Keep this property; it is why the surface stays trustworthy.
- **Guidance notes** — free-text rules the customer adds and removes.
- **Recommended guidance** — platform suggestions based on common AI-summary mistakes for
  the category, added with `+ Add`.
- **Brand Copilot** — proposes guidance in context.

**Requirement:** every draft and proposed change produced in Insights must be generated
under the active Brand Guidelines. If a rule is added, subsequently generated content
must reflect it. **[OPEN — is regeneration of existing drafts on rule change expected?]**

---

## 8. Non-functional requirements

- **Density without breakage.** These are 10–13 column tables. Horizontal scroll within a
  minimum-width container; the page itself must never scroll horizontally. Filter bars,
  KPI grids, and header rows wrap.
- **Definitional transparency.** Every metric exposes its definition at the point of use.
  No metric ships without one.
- **Provenance.** Every generated artefact states what it was generated from. Every
  number states its period and comparison baseline.
- **Zero and partial states.** Newly tracked entities render complete zero rows. Missing
  third-party data renders an em-dash, never a zero.
- **Freshness visibility.** The user must be able to tell when data was last collected
  and what the next scheduled collection is. **[OPEN — not present in the prototype;
  required, since refresh frequency is user-configurable.]**
- **Accessibility and theming.** Colour is never the only carrier of meaning (severity,
  trend direction, mention yes/no all currently rely on it). **[OPEN — WCAG target.]**
- **Performance, availability, data retention, tenancy, roles and permissions, audit
  logging.** **[OPEN — none are addressed by the prototype. Roles matter most: publishing
  to a live CMS and editing a tracked set are not the same privilege.]**

---

## 9. Out of scope for v1

Explicitly not committed. Present in the prototype's logic but not surfaced, or absent
entirely:

1. **Tracking setup wizard** (Keywords → Target → Search settings → Review) — logic
   exists, renders nowhere. Onboarding needs a decision either way.
2. **Seven-tab SEO report shell** (Positions, Overview, Landing pages, Competitors'
   pages, Tracking visibility, Tracking overview, Competitors discovery) — scaffolded,
   unrendered. Overlaps existing Atlas SEO reporting; resolve overlap before scheduling.
3. **Competitor leaderboards** by each of the five AEO metrics — computed, unrendered.
4. **Multi-domain / multi-brand workspaces.**
5. **Public API and non-keyword exports.**
6. **Alerting and scheduled digests** — no notification surface exists, which is odd for
   a product whose value is noticing change. Strong candidate for v1.1.
7. **Ad surfaces beyond ChatGPT Ads.**
8. **Automated publishing without human approval** — deliberately excluded, permanently.

---

## 10. Success measures

**[ASSUMPTION — targets to be set by Product and GTM; the metrics themselves follow from
the strategy in §3.]**

- **Activation:** % of new workspaces with a connected domain, GSC, GA, and ≥1 tracked
  prompt within 7 days.
- **Core loop:** % of insights that reach a generated draft; % of drafts published; median
  time from insight surfaced to published.
- **Differentiation:** % of accounts using Pages (the join) weekly; creator-handoff
  requests per account per month.
- **Retention:** weekly active accounts; prompt-set growth per account over time (a
  shrinking tracked set is churn's leading indicator).
- **Outcome:** movement in Citation Rate and Share of Voice on prompt clusters where a
  published action was taken, against untouched clusters as control.

---

## 11. Open questions — blocking

Ordered by what blocks the most work. Each needs an owner and a date.

| # | Question | Blocks | Owner |
| --- | --- | --- | --- |
| 1 | Engine access method, rate limits, and per-execution cost across all five engines | The entire product | Eng |
| 2 | Is device segmentation genuinely observable per engine, or modelled? | Every device filter | Eng / Data |
| 3 | Cross-engine metric comparability and Visibility normalisation | Performance, Pages, Prompts | Data |
| 4 | Sentiment classifier, measured accuracy, and dispute path | Sentiment everywhere | Data / ML |
| 5 | SEO data vendor selection | Keywords, Backlinks, half of Competitors | Product / Eng |
| 6 | Insight detection: rules vs. model, and thresholds per pattern | Insights | Data / Product |
| 7 | CMS integrations in v1, approval roles, audit trail, before/after diff | Publish to CMS | Eng / Product |
| 8 | Persona model — user-authored or inferred; how it parameterises execution | Prompt Mentions, Answer History | Product |
| 9 | Pricing and metering dimensions | GTM, and the caps in #1 | GTM |
| 10 | Creator-handoff commercial model and routing | Creator handoff | GTM / Creator Ops |
| 11 | Filter scope: global and sticky vs. per-surface | Global shell | Design |
| 12 | Tenancy, roles, retention, availability targets | Platform work | Eng |

---

## Appendix A — Reference values from the prototype

Use these as the demo/seed dataset, not as production defaults.

- **Engines:** ChatGPT, Perplexity, Google AI Overviews, Microsoft Co-Pilot, Claude.
  Aliases normalised on ingest ("Copilot" and "Co-Pilot" → Microsoft Co-Pilot; "Google AI
  Overview" → Google AI Overviews).
- **Regions:** United States, United Kingdom, India, Brazil.
- **Devices:** all, desktop, mobile, tablet.
- **Preset windows:** 7d, 30d, 90d, 180d, 12mo. Prototype default 180d.
- **Refresh:** daily, weekly (default), every 2 weeks, monthly.
- **Prompt types:** Brand Related, Category Related.
- **Seed topics:** AI Agents & Workflow Automation; Programmatic SEO & Content Scale; AI
  Data Processing & Operations; Brand & Company Info; Pricing & Competitive Positioning.
- **Demo tenant:** `acme.com`, benchmarked against athenahq.ai, tryprofound.com, peec.ai,
  conductor.com, semrush.com, brightedge.com, scrunchai.com, airops.com.
- **Demo KPI values:** Visibility 34% (+3.2 pts), Mention Rate 58% (−2.4 pts), Share of
  Voice 21% (+1.1 pts), Citation Rate 46% (+5.8 pts), Sentiment 82 (+4 pts), Average
  Position 2.4 (steady).

## Appendix B — Prototype provenance

`pepperproject.standalone.html` — self-contained React prototype, Acme demo tenant, all
data mocked. Verified against it while writing this document: navigation and grouping,
all ten rendered surfaces, every table's column set, all filter option sets, all six
metric definitions (quoted verbatim), the twelve insight patterns, both article-drawer
modes, and the three unrendered feature sets listed in §9.
