// A deliberately small Markdown subset for chat replies: paragraphs, bullet
// and numbered lists, **bold**, `code` and http(s) links. Renders React
// elements, never HTML, so model output can't inject markup.

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\((https?:\/\/[^\s)]+)\))/g;

function inline(text) {
  const out = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) out.push(text.slice(last, match.index));
    const token = match[0];
    const key = match.index;
    if (token.startsWith("**")) out.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`")) out.push(<code key={key}>{token.slice(1, -1)}</code>);
    else {
      const label = token.slice(1, token.indexOf("]("));
      out.push(<a key={key} href={match[2]} target="_blank" rel="noopener noreferrer">{label}</a>);
    }
    last = match.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const BULLET = /^\s*[-*•]\s+/;
const NUMBERED = /^\s*\d+[.)]\s+/;

export default function Markdown({ text }) {
  const blocks = [];
  let list = null;
  let para = [];

  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", lines: para });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const line of text.split("\n")) {
    const kind = BULLET.test(line) ? "ul" : NUMBERED.test(line) ? "ol" : null;
    if (kind) {
      flushPara();
      if (!list || list.type !== kind) {
        flushList();
        list = { type: kind, items: [] };
      }
      list.items.push(line.replace(kind === "ul" ? BULLET : NUMBERED, ""));
    } else if (!line.trim()) {
      flushPara();
      flushList();
    } else if (list && /^\s{2,}/.test(line)) {
      list.items[list.items.length - 1] += ` ${line.trim()}`;
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();

  return blocks.map((block, i) => {
    if (block.type === "p") {
      return (
        <p key={i}>
          {block.lines.map((line, j) => (
            <span key={j}>
              {j > 0 && <br />}
              {inline(line)}
            </span>
          ))}
        </p>
      );
    }
    const List = block.type;
    return <List key={i}>{block.items.map((item, j) => <li key={j}>{inline(item)}</li>)}</List>;
  });
}
