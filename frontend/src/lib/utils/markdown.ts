export interface InlineToken {
  type: 'text' | 'strong' | 'em' | 'code';
  value: string;
}

export interface BlockToken {
  type: 'paragraph' | 'list' | 'codeblock';
  items?: InlineToken[][]; // for lists
  inlines?: InlineToken[]; // for paragraphs
  code?: string; // for codeblocks
}

/**
 * Safely parse markdown inline formatting (**bold**, *italic*, `code`).
 * Returns structured tokens that bind directly to DOM textContent in Svelte templates.
 * Never touches innerHTML.
 */
export function parseInlines(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    // 1. Inline Code: `code`
    const codeMatch = remaining.match(/^`([^`]+)`/);
    if (codeMatch && codeMatch[1]) {
      tokens.push({ type: 'code', value: codeMatch[1] });
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }

    // 2. Bold: **bold** or __bold__
    const boldMatch = remaining.match(/^(\*\*|__)(.*?)\1/);
    if (boldMatch && boldMatch[2]) {
      tokens.push({ type: 'strong', value: boldMatch[2] });
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }

    // 3. Italic: *italic* or _italic_
    const italicMatch = remaining.match(/^(\*|_)(.*?)\1/);
    if (italicMatch && italicMatch[2]) {
      tokens.push({ type: 'em', value: italicMatch[2] });
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }

    // Plain text up to next special character
    const nextSpecial = remaining.search(/[`*_]/);
    if (nextSpecial === -1) {
      tokens.push({ type: 'text', value: remaining });
      break;
    } else if (nextSpecial > 0) {
      tokens.push({ type: 'text', value: remaining.slice(0, nextSpecial) });
      remaining = remaining.slice(nextSpecial);
    } else {
      // Current char is special but didn't match a token rule, consume as literal text
      tokens.push({ type: 'text', value: remaining[0]! });
      remaining = remaining.slice(1);
    }
  }

  return tokens;
}

/**
 * Parses markdown blocks (paragraphs, unordered lists, fenced code blocks).
 * Completely safe for DOM rendering.
 */
export function parseMarkdown(markdown: string): BlockToken[] {
  const lines = markdown.split(/\r?\n/);
  const blocks: BlockToken[] = [];
  let currentList: InlineToken[][] | null = null;
  let inCodeBlock = false;
  let codeBuffer: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;

    if (line.startsWith('```')) {
      if (inCodeBlock) {
        blocks.push({ type: 'codeblock', code: codeBuffer.join('\n') });
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        if (currentList) {
          blocks.push({ type: 'list', items: currentList });
          currentList = null;
        }
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Unordered or ordered list item
    const listMatch = line.match(/^[-*•]\s+(.*)$/) || line.match(/^\d+\.\s+(.*)$/);
    if (listMatch && listMatch[1]) {
      if (!currentList) currentList = [];
      currentList.push(parseInlines(listMatch[1]));
      continue;
    }

    // Blank line
    if (!line.trim()) {
      if (currentList) {
        blocks.push({ type: 'list', items: currentList });
        currentList = null;
      }
      continue;
    }

    // Paragraph
    if (currentList) {
      blocks.push({ type: 'list', items: currentList });
      currentList = null;
    }

    blocks.push({ type: 'paragraph', inlines: parseInlines(line) });
  }

  if (inCodeBlock) {
    blocks.push({ type: 'codeblock', code: codeBuffer.join('\n') });
  } else if (currentList) {
    blocks.push({ type: 'list', items: currentList });
  }

  return blocks;
}
