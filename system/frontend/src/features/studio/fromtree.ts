// Reverse of toPageTree, constrained on purpose: it accepts ONLY the section/columns/
// column/heading/text/button/image shapes toPageTree produces, and refuses anything else
// (fail closed - the studio must never silently load a tree it cannot edit faithfully).
// Project-level fields (colors, font, radius, motion, language) are not stored in the
// tree; they are kept from the project passed in.
import { toPageTree, type PageNode } from './pagetree';
import { validateProject, type Device, type Project, type Section } from './model';

function unescape(value: string): string {
  return value.replace(/&(#39|amp|lt|gt|quot);/g, (_, c: string) => ({ 'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', '#39': "'" }[c] ?? ''));
}

function htmlText(node: PageNode | undefined, lang: string): string {
  if (!node || node.type !== 'text') throw new Error('expected text node');
  const html = (node.content[lang] as { html?: string } | undefined)?.html ?? (node.content.en as { html?: string } | undefined)?.html ?? (node.content.ar as { html?: string } | undefined)?.html;
  if (typeof html !== 'string') throw new Error('text node without html');
  const match = html.match(/^<p>([\s\S]*)<\/p>$/);
  if (!match) throw new Error('unsupported html shape');
  return unescape(match[1]);
}

function visible(node: PageNode, device: Device): boolean {
  const v = node.settings[device]?.visible;
  return v === undefined ? true : v === true;
}

function cardFromColumn(col: PageNode, lang: string): { title: string; text: string } {
  if (col.type !== 'column' || !col.children?.length) throw new Error('expected a card column');
  const blocks = col.children;
  if (blocks.some(c => !['heading', 'text'].includes(c.type))) throw new Error('unsupported card block');
  const heading = blocks.find(c => c.type === 'heading');
  const text = blocks.find(c => c.type === 'text');
  if (!heading || !text || blocks.length !== 2) throw new Error('card without heading and text');
  const title = (heading.content[lang] as { text?: string } | undefined)?.text ?? (heading.content.en as { text?: string } | undefined)?.text ?? (heading.content.ar as { text?: string } | undefined)?.text;
  if (typeof title !== 'string') throw new Error('card heading without content');
  return { title, text: htmlText(text, lang) };
}

function sectionFromRow(row: PageNode, index: number, lang: string, nextRowId: string | undefined): Section {
  if (row.type !== 'columns' || !row.children?.length) throw new Error('expected a columns row');
  const anyImage = row.children.some(c => c.type === 'column' && c.children?.some(b => b.type === 'image'));
  const leadCol = row.children[0];
  const leadBlocks = leadCol?.type === 'column' ? leadCol.children ?? [] : [];
  const leadHasButton = leadBlocks.some(b => b.type === 'button');
  if (!anyImage && !leadHasButton) {
    // Feature-cards row: lead copy column (eyebrow, heading, intro; no button/note)
    // plus 1-4 card columns (heading + text). Emitted by toPageTree for kind 'features'.
    if (row.children.length < 2 || row.children.length > 5) throw new Error('features row with unsupported column count');
    if (leadBlocks.some(c => !['text', 'heading'].includes(c.type))) throw new Error('unsupported lead block');
    const heading = leadBlocks.find(c => c.type === 'heading');
    if (!heading) throw new Error('features lead without heading');
    const title = (heading.content[lang] as { text?: string } | undefined)?.text ?? (heading.content.en as { text?: string } | undefined)?.text ?? (heading.content.ar as { text?: string } | undefined)?.text;
    if (typeof title !== 'string') throw new Error('features heading without content');
    const texts = leadBlocks.filter(c => c.type === 'text');
    return {
      id: `section-${index}`,
      eyebrow: texts.length > 0 ? htmlText(texts[0], lang) : '',
      title,
      description: texts.length > 1 ? htmlText(texts[1], lang) : '',
      button: '',
      image: '',
      visible: { desktop: visible(row, 'desktop'), tablet: visible(row, 'tablet'), mobile: visible(row, 'mobile') },
      reversed: false,
      kind: 'features',
      cards: row.children.slice(1).map(c => cardFromColumn(c, lang)),
    };
  }
  if (row.children.length > 2) throw new Error('row with more than two columns');
  const copyCol = row.children.find(c => c.type === 'column' && c.children?.some(b => b.type === 'heading'));
  const mediaCol = row.children.find(c => c !== copyCol);
  if (!copyCol || !copyCol.children?.length) throw new Error('expected a copy column');
  if (mediaCol && mediaCol.type !== 'column') throw new Error('expected a media column');
  const reversed = row.settings?.desktop?.reverse === true;
  const blocks = copyCol.children;
  const imageNode = mediaCol?.children?.find(c => c.type === 'image');
  if (mediaCol?.children?.some(c => c.type !== 'image')) throw new Error('unsupported media block');
  const heading = blocks.find(c => c.type === 'heading');
  const button = blocks.find(c => c.type === 'button');
  if (!heading || !button) throw new Error('row without heading or button');
  const title = (heading.content[lang] as { text?: string } | undefined)?.text ?? (heading.content.en as { text?: string } | undefined)?.text ?? (heading.content.ar as { text?: string } | undefined)?.text;
  const label = (button.content[lang] as { label?: string } | undefined)?.label ?? (button.content.en as { label?: string } | undefined)?.label ?? (button.content.ar as { label?: string } | undefined)?.label;
  if (typeof title !== 'string' || typeof label !== 'string') throw new Error('heading/button without content');
  // The CTA href is generated by toPageTree: an anchor to the next row, or the
  // page root from the last one. '#preview' is the constant earlier builds
  // wrote; it is accepted and upgraded to the anchor form on the next save.
  // Any other destination is a custom link this prototype has no control for.
  const href = (button.content[lang] as { href?: string } | undefined)?.href ?? (button.content.en as { href?: string } | undefined)?.href ?? (button.content.ar as { href?: string } | undefined)?.href ?? '';
  const expected = nextRowId ? `#${nextRowId}` : '#n_root01';
  if (href !== expected && href !== '#preview') throw new Error('custom button destination');
  // The editorial note is generated by toPageTree from the section index, not edited.
  const texts = blocks.filter(c => c.type === 'text' && c.settings?.desktop?.variant !== 'note');
  if (blocks.some(c => !['text', 'heading', 'button'].includes(c.type))) throw new Error('unsupported block');
  const src = (imageNode?.content[lang] as { src?: string } | undefined)?.src ?? (imageNode?.content.en as { src?: string } | undefined)?.src ?? '';
  return {
    id: `section-${index}`,
    eyebrow: texts.length > 0 ? htmlText(texts[0], lang) : '',
    title,
    description: texts.length > 1 ? htmlText(texts[1], lang) : '',
    button: label,
    image: typeof src === 'string' ? src : '',
    visible: { desktop: visible(row, 'desktop'), tablet: visible(row, 'tablet'), mobile: visible(row, 'mobile') },
    reversed,
  };
}

export function fromPageTree(tree: PageNode, base: Project): Project {
  if (!tree || tree.type !== 'section' || !Array.isArray(tree.children) || tree.children.length === 0) {
    throw new Error('not a studio page tree');
  }
  if (JSON.stringify(tree).length > 200000 || tree.children.length > 20) throw new Error('oversized studio tree');
  const sections = tree.children.map((row, i) => sectionFromRow(row, i, base.language, tree.children?.[i + 1]?.id));
  const restored = { ...base, sections };
  if (!validateProject(restored)) throw new Error('invalid restored project');
  // Rebuilding must preserve every editable value and every fixed setting/content
  // field. Only generated node ids are excluded; arbitrary extra keys are not.
  // This catches rich markup, extra blocks, translations, image alt text/crop,
  // custom destinations and per-device settings the prototype has no controls for.
  // Generated values are excluded from the comparison: node ids, and the
  // generated button href (validated above, rewritten by toPageTree on save).
  const stripGenerated = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(stripGenerated);
    if (value && typeof value === 'object') {
      const node = value as Record<string, unknown>;
      if (node.type === 'button' && node.content && typeof node.content === 'object') {
        const content = Object.fromEntries(Object.entries(node.content as Record<string, unknown>).map(([lang, fields]) =>
          [lang, fields && typeof fields === 'object' ? Object.fromEntries(Object.entries(fields as Record<string, unknown>).filter(([k]) => k !== 'href')) : fields]));
        return { ...node, content };
      }
      return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, stripGenerated(v)]));
    }
    return value;
  };
  const canonical = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).filter(([key]) => !(key === 'id' && 'type' in value && 'settings' in value && 'content' in value))
        .sort(([a], [b]) => a.localeCompare(b)).map(([key, entry]) => [key, canonical(entry)]));
    }
    return value;
  };
  const left = canonical(stripGenerated(tree));
  const right = canonical(stripGenerated(toPageTree(restored)));
  if (JSON.stringify(left) !== JSON.stringify(right)) {
    throw new Error('tree contains data this prototype cannot preserve');
  }
  return restored;
}
