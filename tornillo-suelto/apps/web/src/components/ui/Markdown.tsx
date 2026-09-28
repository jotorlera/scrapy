import { Fragment, type ReactNode } from 'react'

/* Renderizador de markdown ligero (sin dependencias): encabezados, listas, citas, negrita, cursiva, código,
   enlaces y [[enlaces wiki]]. Suficiente para salidas de agentes, notas y briefs redactados. */

function inline(text: string, onWikiLink?: (t: string) => void): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(\[\[([^\]]+)\]\])|(\*\*([^*]+)\*\*)|(`([^`]+)`)|(\*([^*]+)\*)|(\[([^\]]+)\]\((https?:[^)\s]+)\))|(https?:\/\/[^\s<)]+)/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[1]) {
      const t = m[2]
      out.push(
        <span key={k++} className="wikilink" role={onWikiLink ? 'link' : undefined} tabIndex={onWikiLink ? 0 : undefined} onClick={onWikiLink ? () => onWikiLink(t) : undefined} onKeyDown={onWikiLink ? (e) => e.key === 'Enter' && onWikiLink(t) : undefined}>
          [[{t}]]
        </span>,
      )
    } else if (m[3]) out.push(<strong key={k++}>{m[4]}</strong>)
    else if (m[5]) out.push(<code key={k++}>{m[6]}</code>)
    else if (m[7]) out.push(<em key={k++}>{m[8]}</em>)
    else if (m[9])
      out.push(
        <a key={k++} href={m[11]} target="_blank" rel="noopener noreferrer">
          {m[10]}
        </a>,
      )
    else if (m[12])
      out.push(
        <a key={k++} href={m[12]} target="_blank" rel="noopener noreferrer">
          {m[12]}
        </a>,
      )
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function Markdown({ text, onWikiLink, className = '' }: { text: string; onWikiLink?: (t: string) => void; className?: string }) {
  const lines = text.replace(/\r/g, '').split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  let k = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(line)
    if (h) {
      const Tag = (`h${h[1].length}`) as 'h1' | 'h2' | 'h3'
      blocks.push(<Tag key={k++}>{inline(h[2], onWikiLink)}</Tag>)
      i++
      continue
    }
    if (/^\s*([-*•]|\d+[.)])\s+/.test(line)) {
      const items: string[] = []
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*•]|\d+[.)])\s+/, ''))
        i++
      }
      const Tag = ordered ? 'ol' : 'ul'
      blocks.push(
        <Tag key={k++}>
          {items.map((it, j) => (
            <li key={j}>{inline(it, onWikiLink)}</li>
          ))}
        </Tag>,
      )
      continue
    }
    if (line.startsWith('>')) {
      const q: string[] = []
      while (i < lines.length && lines[i].startsWith('>')) {
        q.push(lines[i].replace(/^>\s?/, ''))
        i++
      }
      blocks.push(<blockquote key={k++}>{inline(q.join(' '), onWikiLink)}</blockquote>)
      continue
    }
    if (line.startsWith('---')) {
      blocks.push(<hr key={k++} />)
      i++
      continue
    }
    const p: string[] = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,3})\s/.test(lines[i]) && !/^\s*([-*•]|\d+[.)])\s+/.test(lines[i]) && !lines[i].startsWith('>')) {
      p.push(lines[i])
      i++
    }
    blocks.push(
      <p key={k++}>
        {p.map((l, j) => (
          <Fragment key={j}>
            {inline(l, onWikiLink)}
            {j < p.length - 1 ? <br /> : null}
          </Fragment>
        ))}
      </p>,
    )
  }
  return <div className={`md ${className}`}>{blocks}</div>
}
