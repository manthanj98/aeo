// Builds the one-page conceptual eval brief as a Word document.
//   node docs/build_onepager.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  AlignmentType, BorderStyle, LevelFormat, convertInchesToTwip,
} = require("docx");

const INK = "1A0F2E";
const PLUM = "4A2C7A";
const GOLD = "8C7133";
const BODY = "23202B";

const FONT = "Calibri";
const SIZE = 20;      // half-points -> 10pt body
// Word 'auto' line spacing, in 240ths of a line. 220 is a shade under single:
// enough air to read comfortably, tight enough to hold one page.
const LEAD = 220;

// Tight but readable: the whole brief has to land on one page.
const gap = (before, after) => ({ before, after, line: LEAD });

function h(text) {
  return new Paragraph({
    spacing: gap(150, 50),
    children: [new TextRun({ text, bold: true, size: 21, color: PLUM, font: FONT,
      allCaps: true, characterSpacing: 14 })],
  });
}

function p(runs, opts = {}) {
  return new Paragraph({
    spacing: gap(opts.before ?? 0, opts.after ?? 70),
    indent: opts.indent,
    children: (Array.isArray(runs) ? runs : [runs]).map((r) =>
      typeof r === "string"
        ? new TextRun({ text: r, size: SIZE, color: BODY, font: FONT })
        : new TextRun({ size: SIZE, color: BODY, font: FONT, ...r })),
  });
}

function bullet(runs, opts = {}) {
  return new Paragraph({
    numbering: { reference: "dots", level: 0 },
    spacing: gap(0, opts.after ?? 40),
    children: (Array.isArray(runs) ? runs : [runs]).map((r) =>
      typeof r === "string"
        ? new TextRun({ text: r, size: SIZE, color: BODY, font: FONT })
        : new TextRun({ size: SIZE, color: BODY, font: FONT, ...r })),
  });
}

const doc = new Document({
  creator: "Pepper",
  title: "Would Atlas actually give CS managers their four hours back?",
  description: "Measurement, dataset and success criteria for the CS reporting workstream",
  numbering: {
    config: [{
      reference: "dots",
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: "•",
        alignment: AlignmentType.LEFT,
        style: {
          paragraph: {
            indent: { left: convertInchesToTwip(0.24), hanging: convertInchesToTwip(0.14) },
          },
          run: { color: GOLD },
        },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },   // US Letter
        margin: {
          top: convertInchesToTwip(0.62),
          bottom: convertInchesToTwip(0.55),
          left: convertInchesToTwip(0.75),
          right: convertInchesToTwip(0.75),
        },
      },
    },
    children: [
      // ---------------------------------------------------------- masthead
      new Paragraph({
        spacing: { after: 30, line: 240 },
        children: [new TextRun({
          text: "PEPPER ATLAS  ·  CS REPORTING",
          size: 15, bold: true, color: GOLD, font: FONT, characterSpacing: 26,
        })],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 30, line: 260 },
        children: [new TextRun({
          text: "Would Atlas actually give CS managers their four hours back?",
          bold: true, size: 27, color: INK, font: FONT,
        })],
      }),
      new Paragraph({
        spacing: { after: 90, line: 220 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "D8CFE4", space: 6 } },
        children: [new TextRun({
          text: "How we would measure it, what we would need, and what would count as a win",
          size: 19, italics: true, color: "5F5570", font: FONT,
        })],
      }),

      // -------------------------------------------------- what we're claiming
      h("What we are actually claiming"),
      p([
        { text: "“4+ hours a week” is not one activity. " },
        "It is pulling the data, stitching it together, building the deck, writing the story, " +
        "checking it, sending it, and answering the follow-ups. Atlas removes the first three " +
        "almost entirely and helps with the fourth. It does nothing for the checking — and may " +
        "add to it, because someone now has to verify what the AI wrote. A client with a live " +
        "dashboard also tends to ask more questions, not fewer. So the claim to test is not " +
        "“Atlas removes four hours of work.” It is ",
        { text: "“Atlas removes more work than it creates.”", bold: true },
      ]),

      // ------------------------------------------------------------ measurement
      h("Measurement"),
      p([
        { text: "Do not ask people how long it took. ", bold: true },
        "Self-reported estimates of routine work are consistently inflated, and they barely move " +
        "when the work actually changes.",
      ], { after: 45 }),
      p([
        { text: "Use a ruler that already exists. ", bold: true },
        "The edit timestamps on the spreadsheets and decks CS managers already build tell us how " +
        "long each report took — retroactively, for the last two quarters. That gives us a " +
        "baseline without waiting to collect one, and it is the same ruler before and after, so we " +
        "are comparing like with like.",
      ], { after: 45 }),
      p([
        { text: "Measure the whole loop, ", bold: true },
        "from the first data pull to the last client follow-up — not just the part Atlas automates.",
      ], { after: 55 }),
      p("Two numbers get reported, because they can disagree:", { after: 40 }),
      bullet([
        { text: "Time per report", bold: true },
        " — what the product directly changes.",
      ]),
      bullet([
        { text: "Reporting hours per person per week", bold: true },
        " — the actual promise.",
      ], { after: 55 }),
      p("If the first improves and the second does not, the time went somewhere — usually into " +
        "carrying more accounts. That is a real business result, but it is not the promise we made, " +
        "and it should be reported as what it is."),

      // --------------------------------------------------------------- dataset
      h("What we would need"),
      bullet([
        { text: "The back catalogue. ", bold: true },
        "Every report cycle from the past two quarters, reconstructed from existing file and email " +
        "records. Our baseline, with no new instrumentation.",
      ]),
      bullet([
        { text: "Shadowing. ", bold: true },
        "Sitting with CS managers through roughly 25 report cycles, to check the timestamp measure " +
        "against reality and see where the time actually goes.",
      ]),
      bullet([
        { text: "Past reports paired with the data behind them. ", bold: true },
        "For the question that comes before “is it faster”: is it still good? ",
        { text: "This one has to start now", bold: true },
        " — we cannot reconstruct later what the data looked like at the time.",
      ]),
      bullet([
        { text: "Client-side signals. ", bold: true },
        "Are clients opening the dashboard, and are they still happy with what they get?",
      ], { after: 20 }),

      // --------------------------------------------------------------- rollout
      h("How we would run it"),
      p("Give Atlas to a few CS managers at a time, in a randomised order, until everyone has it. " +
        "Each person becomes their own before-and-after, which matters on a team this size, and " +
        "nobody sits in a control group for months watching colleagues use the new tool. Discount " +
        "everyone’s first report — the first one on any new tool is slower, and counting it " +
        "would understate the result."),

      // ------------------------------------------------------------- criteria
      h("What would count as a win"),
      bullet([
        { text: "Success. ", bold: true },
        "Reporting time per person roughly halves, from 4+ hours to under two, and holds for a " +
        "month after the novelty wears off.",
      ]),
      bullet([
        { text: "Partial. ", bold: true },
        "Time per report falls but weekly hours do not, or the saving fades. Iterate; do not " +
        "declare victory.",
      ]),
      bullet([
        { text: "Failure. ", bold: true },
        "The saving is marginal, or clients notice the reports got worse.",
      ], { after: 55 }),
      p([
        { text: "Quality is a gate, not a tiebreaker. ", bold: true },
        "Before we measure anyone’s time, Atlas’s reports have to hold up against ones our own " +
        "team wrote — surfacing what a good CS manager would have surfaced, with no invented " +
        "numbers and nothing off-brand. A faster report nobody trusts is not a saving.",
      ]),

      // ----------------------------------------------------------- the trap
      h("The two ways this claim usually turns out false"),
      p("Both are work moving rather than disappearing: onto the client, who now assembles their " +
        "own view, or onto someone else inside Pepper. We measure both — otherwise the number is " +
        "an accounting trick.", { after: 0 }),
    ],
  }],
});

const out = path.join(__dirname, "atlas-eval-brief.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
