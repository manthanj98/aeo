# Acme — AI Visibility Dashboard

An answer-engine-optimisation (AEO) analytics dashboard: visibility, citations, prompts, keywords and
competitors tracked across ChatGPT, Perplexity, Google AI Overviews, Microsoft Co-Pilot and Claude.

Ships as **one self-contained HTML file**. React, ReactDOM, the template runtime, the theme and the app are
all inlined, so the published page makes no external requests and runs straight off the filesystem.

## Layout

```
src/theme.css          brand tokens + component classes — all styling lives here
src/app.template.html  x-dc markup (structure; only dynamic values stay inline)
src/app.logic.js       component state, derived values and event handlers
vendor/                react 18 UMD, react-dom 18 UMD, dc-runtime
build.py               assembles the deliverable
tools/verify.mjs       Playwright checks: render gates, bug regressions, responsive
dist/                  build output
```

## Build and verify

```bash
npm install            # playwright only
npm run build          # -> dist/pepper-project.html (+ .standalone.html for local testing)
npm run verify         # build, then run all checks headless
npm run shots          # same, plus screenshots into dist/shots/
```

`dist/pepper-project.html` is a body fragment, which is what the artifact host expects — it supplies the
surrounding `<html>`/`<head>`/`<body>`. `dist/pepper-project.standalone.html` is a complete document for
opening directly in a browser.

`tools/verify.mjs` runs 39 checks: every tab and drawer renders with no page errors, no unresolved `{{ }}`
bindings and no `undefined`/`NaN` leaking into the UI; one targeted regression per fixed bug; and no
horizontal page scroll at 1440 / 900 / 480 px.

## Provenance

Rebuilt from `Pepper_Project.html`, a bundled artifact export. That file was a gzip+base64 manifest wrapping
the vendor scripts and an `x-dc` template — not editable source. It was unpacked back into the files above,
debugged, and restyled.

### Fixed

**Layout**

- The Search Performance container carried a hardcoded `width:1163px; height:93px`. The fixed height clipped
  its KPI cards and let the analytics row render on top of them; the fixed width broke every viewport but one.
- The analytics KPI row had an empty heading element, leaving five cards unlabelled. It is now
  "Marketing Performance".
- Removed dead markup: an empty flex spacer row, an empty conditional, and four empty heading blocks.

**Behaviour**

- The "Recommended competitors" panel sat *outside* its `hasRecommendedCompetitors` guard (which was empty),
  so it stayed on screen with zero items once the user had added them all.
- Prompt mentions were keyed by index into the *filtered* list, so changing the engine filter with a drawer
  open silently closed it — or showed a different mention at the same index. They are now keyed by content
  and resolved against the unfiltered set.
- Newly tracked prompts were created without citation-rate or trend fields, rendering blank cells, and their
  placeholder volume fell through the numeric ladder to "Very Low". They now start from a complete zero state
  and report "—" for unknown volume.
- Share of voice was floored at 1%, inventing a figure for prompts with no mentions. Floored at 0.
- Trend values were rounded loosely, so `+0 pts` and `+2 pts` appeared beside `+1.3 pts` in one column.
  All trends now format to one decimal.
- A "To" date earlier than "From" produced `Last -12 days`. The label is clamped and the pickers bound to
  each other.
- Citation data used `Copilot` where the rest of the app used `Microsoft Co-Pilot`, so colour lookups and the
  engine filter missed those rows. Names are normalised through an alias map.
- Search Console data referenced `acme-seo-geo.com` while everything else used `acme.com`.
- Insight recommendation cards were interleaved into the feed and then sorted away. Severity ordering is now
  applied first and the cards woven in afterwards, so both hold.
- Element ids came from `Date.now()`, colliding when two items were added in the same millisecond. Replaced
  with a monotonic counter.
- `promptInspectId`, `inspectUrl` and `openRowMenuUrl` were read and written but never initialised.
- `activeTabLabel` did an unguarded `.find(…).label` that would throw on any unknown tab key.

### Redesigned

Restyled to the Acme brand guidelines. `src/theme.css` holds the tokens — `--ink`, `--navy`, `--navy-2`, the
`--teal*` gold ramp, the `--amber*` clay pair, the neutral scale, three shadow steps, the shared easing curve
and the sans/mono pairing — and the component classes built on them.

The shell picks up the brand hero treatment: a gradient sidebar with dot texture and a shimmering accent rule
under the header. Every tab opens with a numbered section badge. Cards carry a 16px radius and lift on hover;
KPI values render as gradient numerals under mono eyebrow labels; insights use the gold-ruled statement card
with a dark callout for business impact; tables get mono uppercase headers. Charts draw from the brand ramp,
replacing the off-palette pinks and blues. The sidebar and grids collapse below 900px.

The Brand Guidelines tab is now a living style guide — swatches, type ramp and elevation samples render from
the same tokens the rest of the app uses, so it cannot drift from the system it documents.

### Renamed

The product is **Acme** throughout. The previous "Acme SEO & GEO" appeared in 12 places across prompt text,
response excerpts, insight copy and draft articles; each sentence was reworked to stay grammatical.
