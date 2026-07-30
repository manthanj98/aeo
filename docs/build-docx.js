const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, convertInchesToTwip, Footer, PageNumber,
} = require('docx');

const SRC = process.argv[2];
const OUT = process.argv[3];

const BODY_FONT = 'Calibri';
const MONO_FONT = 'Consolas';
const BODY_SIZE = 21;          // half-points => 10.5pt
const TABLE_SIZE = 18;         // 9pt
const INK = '1A1A1A';
const MUTED = '595959';
const RULE = 'BFBFBF';
const HEADER_BG = 'EDEDED';
const CONTENT_WIDTH = 9360;    // 6.5" at Letter with 1" margins

// ---------- inline formatting ----------
function parseInline(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    const tok = m[0];
    if (tok.startsWith('**')) {
      runs.push(new TextRun({ ...base, text: tok.slice(2, -2), bold: true }));
    } else if (tok.startsWith('`')) {
      runs.push(new TextRun({
        ...base,
        text: tok.slice(1, -1),
        font: MONO_FONT,
        size: (base.size || BODY_SIZE) - 2,
      }));
    } else {
      runs.push(new TextRun({ ...base, text: tok.slice(1, -1), italics: true }));
    }
    last = m.index + tok.length;
  }
  if (last < text.length) runs.push(new TextRun({ ...base, text: text.slice(last) }));
  return runs.length ? runs : [new TextRun({ ...base, text: '' })];
}

// ---------- block parsing ----------
const lines = fs.readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n').split('\n');
const blocks = [];
let i = 0;

const isTableLine = (l) => /^\s*\|/.test(l);
const isBullet = (l) => /^(\s*)[-*]\s+/.test(l);
const isOrdered = (l) => /^(\s*)\d+\.\s+/.test(l);
const isHeading = (l) => /^#{1,6}\s+/.test(l);
const isHr = (l) => /^\s*---+\s*$/.test(l);

while (i < lines.length) {
  const line = lines[i];
  if (!line.trim()) { i++; continue; }

  if (isHr(line)) { blocks.push({ type: 'hr' }); i++; continue; }

  if (isHeading(line)) {
    const m = line.match(/^(#{1,6})\s+(.*)$/);
    blocks.push({ type: 'heading', level: m[1].length, text: m[2].trim() });
    i++;
    continue;
  }

  if (isTableLine(line)) {
    const raw = [];
    while (i < lines.length && isTableLine(lines[i])) { raw.push(lines[i]); i++; }
    const cells = raw
      .filter((l) => !/^\s*\|[\s|:-]+\|\s*$/.test(l))
      .map((l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim()));
    blocks.push({ type: 'table', rows: cells });
    continue;
  }

  if (isBullet(line) || isOrdered(line)) {
    const ordered = isOrdered(line);
    const items = [];
    while (i < lines.length) {
      const l = lines[i];
      if (!l.trim()) {
        // blank line ends the list unless the next line continues it
        const next = lines[i + 1] || '';
        if (isBullet(next) || isOrdered(next) || /^\s{2,}\S/.test(next)) { i++; continue; }
        break;
      }
      if (isBullet(l) || isOrdered(l)) {
        const m = l.match(/^(\s*)(?:[-*]|\d+\.)\s+(.*)$/);
        items.push({ indent: Math.floor(m[1].length / 2), text: m[2].trim() });
      } else if (/^\s{2,}\S/.test(l) && items.length) {
        items[items.length - 1].text += ' ' + l.trim();
      } else {
        break;
      }
      i++;
    }
    blocks.push({ type: 'list', ordered, items });
    continue;
  }

  // paragraph
  const para = [];
  while (
    i < lines.length && lines[i].trim() &&
    !isHeading(lines[i]) && !isTableLine(lines[i]) && !isHr(lines[i]) &&
    !isBullet(lines[i]) && !isOrdered(lines[i])
  ) {
    para.push(lines[i].trim());
    i++;
  }
  // A run of lines that are each "**Label:** value" is a metadata stack, not prose.
  if (para.length > 1 && para.every((l) => /^\*\*[^*]+:\*\*/.test(l))) {
    blocks.push({ type: 'meta', lines: para });
  } else {
    blocks.push({ type: 'para', text: para.join(' ') });
  }
}

// ---------- emit ----------
const children = [];
let orderedInstance = 0;

const HEADING_MAP = {
  1: HeadingLevel.HEADING_1,
  2: HeadingLevel.HEADING_2,
  3: HeadingLevel.HEADING_3,
  4: HeadingLevel.HEADING_4,
};

function tableColumnWidths(rows) {
  const colCount = Math.max(...rows.map((r) => r.length));
  const weights = new Array(colCount).fill(1);
  for (let c = 0; c < colCount; c++) {
    let maxLen = 1;
    for (const r of rows) {
      const txt = (r[c] || '').replace(/[*`]/g, '');
      if (txt.length > maxLen) maxLen = txt.length;
    }
    weights[c] = Math.sqrt(maxLen);
  }
  const total = weights.reduce((a, b) => a + b, 0);
  const maxLens = weights.map((_, c) =>
    Math.max(...rows.map((r) => (r[c] || '').replace(/[*`]/g, '').length), 1));
  let widths = weights.map((w, c) => {
    // Narrow columns ("#", "AS") shouldn't be padded up to a prose-column minimum.
    const min = maxLens[c] <= 4 ? 520 : colCount > 4 ? 800 : 1100;
    return Math.max(min, Math.round((w / total) * CONTENT_WIDTH));
  });
  // normalise so the columns sum exactly to the table width
  const sum = widths.reduce((a, b) => a + b, 0);
  widths = widths.map((w) => Math.round((w / sum) * CONTENT_WIDTH));
  const drift = CONTENT_WIDTH - widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += drift;
  return widths;
}

const CELL_BORDER = { style: BorderStyle.SINGLE, size: 4, color: RULE };

for (const b of blocks) {
  if (b.type === 'heading') {
    const isTitle = b.level === 1;
    children.push(new Paragraph({
      heading: HEADING_MAP[b.level] || HeadingLevel.HEADING_4,
      spacing: { before: isTitle ? 0 : b.level === 2 ? 360 : 260, after: isTitle ? 200 : 120 },
      children: parseInline(b.text, {
        font: BODY_FONT,
        color: INK,
        size: isTitle ? 36 : b.level === 2 ? 27 : 23,
        bold: true,
      }),
      border: b.level === 2
        ? { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } }
        : undefined,
    }));
  } else if (b.type === 'meta') {
    for (const l of b.lines) {
      children.push(new Paragraph({
        spacing: { after: 20, line: 264 },
        children: parseInline(l, { font: BODY_FONT, size: 19, color: MUTED }),
      }));
    }
    children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  } else if (b.type === 'para') {
    children.push(new Paragraph({
      spacing: { after: 160, line: 288 },
      alignment: AlignmentType.LEFT,
      children: parseInline(b.text, { font: BODY_FONT, size: BODY_SIZE, color: INK }),
    }));
  } else if (b.type === 'hr') {
    children.push(new Paragraph({
      spacing: { before: 160, after: 200 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 2 } },
      children: [],
    }));
  } else if (b.type === 'list') {
    if (b.ordered) orderedInstance++;
    for (const it of b.items) {
      children.push(new Paragraph({
        numbering: b.ordered
          ? { reference: 'md-numbers', level: Math.min(it.indent, 1), instance: orderedInstance }
          : { reference: 'md-bullets', level: Math.min(it.indent, 1) },
        spacing: { after: 90, line: 288 },
        children: parseInline(it.text, { font: BODY_FONT, size: BODY_SIZE, color: INK }),
      }));
    }
    children.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  } else if (b.type === 'table') {
    const widths = tableColumnWidths(b.rows);
    const colCount = widths.length;
    const rows = b.rows.map((cells, rIdx) => new TableRow({
      tableHeader: rIdx === 0,
      children: Array.from({ length: colCount }, (_, c) => new TableCell({
        width: { size: widths[c], type: WidthType.DXA },
        shading: rIdx === 0
          ? { type: ShadingType.CLEAR, fill: HEADER_BG, color: 'auto' }
          : undefined,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
          spacing: { after: 0, line: 252 },
          children: parseInline(cells[c] || '', {
            font: BODY_FONT,
            size: TABLE_SIZE,
            color: INK,
            bold: rIdx === 0 || undefined,
          }),
        })],
      })),
    }));
    children.push(new Table({
      columnWidths: widths,
      width: { size: CONTENT_WIDTH, type: WidthType.DXA },
      borders: {
        top: CELL_BORDER, bottom: CELL_BORDER, left: CELL_BORDER, right: CELL_BORDER,
        insideHorizontal: CELL_BORDER, insideVertical: CELL_BORDER,
      },
      rows,
    }));
    children.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
  }
}

const doc = new Document({
  creator: 'Pepper Product',
  title: 'PR/FAQ — AI Visibility (Atlas)',
  description: 'Amazon-style PR/FAQ and product requirements for the Atlas AI Visibility product',
  numbering: {
    config: [
      {
        reference: 'md-bullets',
        levels: [
          {
            level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.2) } } },
          },
          {
            level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.6), hanging: convertInchesToTwip(0.2) } } },
          },
        ],
      },
      {
        reference: 'md-numbers',
        levels: [
          {
            level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.35), hanging: convertInchesToTwip(0.25) } } },
          },
          {
            level: 1, format: LevelFormat.LOWER_LETTER, text: '%2.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.65), hanging: convertInchesToTwip(0.25) } } },
          },
        ],
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: {
          top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({
            children: ['PR/FAQ — AI Visibility (Atlas) · v0.1 · page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES],
            font: BODY_FONT, size: 16, color: MUTED,
          })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log('wrote', OUT, buf.length, 'bytes;', blocks.length, 'blocks');
});
