import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Note, ReviewCard } from '../api/types'
import { EmptyState, ErrorBox, Loading, Tabs } from '../components/ui/basics'
import { Markdown } from '../components/ui/Markdown'
import { Modal } from '../components/ui/Modal'
import { fmtAgo, fmtDateTime, isoDateLocal } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useStore } from '../state/store'
import './screens.css'

const SIGNATURE = 'Dr. José Francisco Tornero-Aguilera'

const ESSAY_TEMPLATE = (title = '[Título del ensayo]') => `# ${title}

**Asignatura:** [Asignatura] · **Práctica N.º:** [N] · **Fecha:** ${isoDateLocal()}

## Resumen
[150-200 palabras: pregunta, tesis, método y conclusión.] Palabras clave: [tres a cinco].

## 1. Introducción
Pregunta: … Tesis: … Estructura: …

## 2. Marco conceptual
Autores y conceptos: [[Rawls]], [[Pettit]], [[libertad negativa]]…

## 3. Desarrollo / análisis
Argumento propio con evidencia citada (evento: [[título del evento]]).

## 4. Conclusiones
…

## Referencias (APA 7)
– Apellido, N. (Año). *Título*. Editorial.

## Anexo I. Registro manuscrito
Figura A1. Borrador manuscrito de la práctica. Fotografía del autor, ${isoDateLocal()}.

---
${SIGNATURE}
`

function NotesTab({ initialNoteId, startNew }: { initialNoteId: string | null; startNew: boolean }) {
  const { toast } = useStore()
  const [q, setQ] = useState('')
  const { data, error, loading, reload } = useAsync<{ notes: Note[] }>(() => api.notes(q || undefined), [q])
  const [sel, setSel] = useState<string | null>(initialNoteId)
  const [note, setNote] = useState<Note | null>(null)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [course, setCourse] = useState('')
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState(false)
  const [isNew, setIsNew] = useState(startNew)

  useEffect(() => {
    if (startNew) {
      setIsNew(true)
      setSel(null)
      setNote(null)
      setTitle('')
      setBody('')
      setCourse('')
      setDirty(false)
    }
  }, [startNew])

  useEffect(() => {
    if (!sel) return
    api
      .note(sel)
      .then((n) => {
        setNote(n)
        setTitle(n.title ?? '')
        setBody(n.body_text)
        setCourse(n.course ?? '')
        setDirty(false)
        setIsNew(false)
      })
      .catch(() => setNote(null))
  }, [sel])

  const save = useCallback(async () => {
    if (isNew || !sel) {
      const r = await api.createNote({ title: title || undefined, body_text: body, course: course || undefined })
      setSel(r.id)
      setIsNew(false)
      toast('Nota creada')
    } else {
      await api.updateNote(sel, { title: title || undefined, body_text: body, course: course || undefined })
      toast('Nota guardada')
      const n = await api.note(sel)
      setNote(n)
    }
    setDirty(false)
    reload()
  }, [isNew, sel, title, body, course, toast, reload])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        e.preventDefault()
        if (dirty || isNew) void save()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dirty, isNew, save])

  const remove = async () => {
    if (!sel || !window.confirm('¿Borrar la nota?')) return
    await api.deleteNote(sel)
    setSel(null)
    setNote(null)
    setIsNew(true)
    setTitle('')
    setBody('')
    reload()
  }

  const openByTitle = (t: string) => {
    const found = data?.notes.find((n) => n.title === t)
    if (found) setSel(found.id)
    else {
      setIsNew(true)
      setSel(null)
      setNote(null)
      setTitle(t)
      setBody(`# ${t}\n\n`)
      setDirty(true)
    }
  }

  return (
    <div className="taller">
      <aside className="notes-list">
        <div className="row" style={{ padding: '0 8px 6px' }}>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar notas…" aria-label="Buscar notas" className="grow" />
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={() => {
              setIsNew(true)
              setSel(null)
              setNote(null)
              setTitle('')
              setBody('')
              setCourse('')
              setDirty(false)
            }}
          >
            Nueva
          </button>
        </div>
        {loading && !data && <Loading />}
        <ErrorBox error={error} />
        {data?.notes.length === 0 && <div className="muted small" style={{ padding: 8 }}>Sin notas. Escribe la primera o usa la plantilla de ensayo.</div>}
        {data?.notes.map((n) => (
          <div key={n.id} className={`note-row ${sel === n.id ? 'active' : ''}`} onClick={() => setSel(n.id)} data-nav-item="" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setSel(n.id)}>
            <div className="truncate" style={{ color: 'var(--c-heading)' }}>
              {n.title ?? '(sin título)'}
            </div>
            <div className="muted small">
              {fmtAgo(n.updated_at)}
              {n.course ? ` · ${n.course}` : ''}
              {n.links.length ? ` · ${n.links.length} enlaces` : ''}
            </div>
          </div>
        ))}
      </aside>
      <div className="editor">
        <div className="row wrap">
          <input
            type="text"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value)
              setDirty(true)
            }}
            placeholder="Título"
            aria-label="Título"
            className="grow"
            style={{ fontSize: 16 }}
          />
          <input
            type="text"
            value={course}
            onChange={(e) => {
              setCourse(e.target.value)
              setDirty(true)
            }}
            placeholder="Asignatura"
            aria-label="Asignatura"
            style={{ width: 160 }}
          />
          <div className="seg">
            <button type="button" aria-pressed={!preview} onClick={() => setPreview(false)}>
              Editar
            </button>
            <button type="button" aria-pressed={preview} onClick={() => setPreview(true)}>
              Vista
            </button>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setBody((b) => (b.trim() ? b : ESSAY_TEMPLATE(title || undefined)))
              if (!title) setTitle('Ensayo')
              setDirty(true)
              setPreview(false)
            }}
          >
            Plantilla de ensayo
          </button>
          <button type="button" className="btn btn-sm" onClick={save} disabled={!dirty && !isNew}>
            Guardar (⌘S)
          </button>
          {sel && !isNew && (
            <>
              <a className="btn btn-ghost btn-sm" href={`/api/notes/${sel}/export.md`} download>
                Exportar .md
              </a>
              <button type="button" className="btn btn-ghost btn-sm" onClick={remove}>
                Borrar
              </button>
            </>
          )}
        </div>
        {preview ? (
          <div className="preview">
            <Markdown text={body || '_Nota vacía._'} onWikiLink={openByTitle} />
          </div>
        ) : (
          <textarea
            value={body}
            onChange={(e) => {
              setBody(e.target.value)
              setDirty(true)
            }}
            placeholder={'Texto plano o markdown ligero. Enlaza con [[título de otra nota]] o [[entidad]]. Firma: ' + SIGNATURE}
            aria-label="Cuerpo de la nota"
          />
        )}
        <div className="row wrap small muted">
          <span>{body.length} caracteres</span>
          {note && (
            <>
              <span>
                enlaces: {note.links.length ? note.links.map((l) => <button key={l} type="button" className="btn-link small" onClick={() => openByTitle(l)} style={{ marginRight: 6 }}>[[{l}]]</button>) : 'ninguno'}
              </span>
              <span>
                retroenlaces: {note.backlinks?.length ? note.backlinks.map((b) => <button key={b.id} type="button" className="btn-link small" onClick={() => setSel(b.id)} style={{ marginRight: 6 }}>{b.title}</button>) : 'ninguno'}
              </span>
              {note.linked_entities && note.linked_entities.length > 0 && <span>entidades: {note.linked_entities.map((e) => e.name).join(', ')}</span>}
              <span>actualizada {fmtDateTime(note.updated_at)}</span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewTab() {
  const { toast } = useStore()
  const [dueOnly, setDueOnly] = useState(true)
  const { data, error, loading, reload } = useAsync<{ cards: ReviewCard[]; due: number }>(() => api.cards(dueOnly), [dueOnly])
  const [idx, setIdx] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [newOpen, setNewOpen] = useState(false)
  const [draft, setDraft] = useState({ front: '', back: '' })
  const cards = data?.cards ?? []
  const card = cards[idx]
  useEffect(() => {
    setIdx(0)
    setRevealed(false)
  }, [data])

  const rate = async (rating: 1 | 2 | 3 | 4) => {
    if (!card) return
    const r = await api.reviewCard(card.id, rating)
    toast(`Próximo repaso: ${fmtDateTime(r.due_at)} (intervalo ${r.state.interval} d)`)
    if (idx + 1 < cards.length) {
      setIdx(idx + 1)
      setRevealed(false)
    } else reload()
  }
  const create = async () => {
    if (!draft.front.trim() || !draft.back.trim()) return
    await api.createCard({ front: draft.front, back: draft.back, source_ref: { kind: 'manual' } })
    setDraft({ front: '', back: '' })
    setNewOpen(false)
    reload()
  }

  return (
    <div>
      <div className="filters">
        <div className="seg">
          <button type="button" aria-pressed={dueOnly} onClick={() => setDueOnly(true)}>
            Pendientes
          </button>
          <button type="button" aria-pressed={!dueOnly} onClick={() => setDueOnly(false)}>
            Todas
          </button>
        </div>
        {data && (
          <span className="muted small">
            {data.due} pendientes · {cards.length} en la cola
          </span>
        )}
        <span className="grow" />
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNewOpen(true)}>
          Nueva tarjeta
        </button>
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} />
      {data && !card && <EmptyState title={dueOnly ? 'Nada pendiente de repasar' : 'Sin tarjetas'}>Las tarjetas se crean a mano, desde el tutor socrático o desde una nota. El planificador es FSRS-lite: 1 otra vez · 2 difícil · 3 bien · 4 fácil.</EmptyState>}
      {card && (
        <div className="review-card">
          <div className="muted small" style={{ marginBottom: 6 }}>
            tarjeta {idx + 1} de {cards.length} · repeticiones {card.fsrs_state.reps ?? 0} · facilidad {card.fsrs_state.ease ?? 2.5} · vence {fmtDateTime(card.due_at)}
          </div>
          <div className="front">{card.front}</div>
          {!revealed ? (
            <button type="button" className="btn btn-primary" onClick={() => setRevealed(true)}>
              Revelar
            </button>
          ) : (
            <>
              <div className="back">
                <Markdown text={card.back} />
              </div>
              <div className="row wrap" style={{ marginTop: 12 }}>
                <button type="button" className="btn btn-ghost" onClick={() => rate(1)}>
                  1 · Otra vez
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => rate(2)}>
                  2 · Difícil
                </button>
                <button type="button" className="btn" onClick={() => rate(3)}>
                  3 · Bien
                </button>
                <button type="button" className="btn btn-primary" onClick={() => rate(4)}>
                  4 · Fácil
                </button>
                <span className="grow" />
                <button
                  type="button"
                  className="btn-link small"
                  onClick={async () => {
                    if (window.confirm('¿Borrar la tarjeta?')) {
                      await api.deleteCard(card.id)
                      reload()
                    }
                  }}
                >
                  borrar
                </button>
              </div>
            </>
          )}
        </div>
      )}
      <Modal open={newOpen} title="Nueva tarjeta de repaso" onClose={() => setNewOpen(false)}>
        <div className="col">
          <label className="field">
            Pregunta
            <textarea rows={3} value={draft.front} onChange={(e) => setDraft({ ...draft, front: e.target.value })} />
          </label>
          <label className="field">
            Respuesta
            <textarea rows={4} value={draft.back} onChange={(e) => setDraft({ ...draft, back: e.target.value })} />
          </label>
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-primary" onClick={create} disabled={!draft.front.trim() || !draft.back.trim()}>
              Crear
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default function Taller() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'repaso' ? 'repaso' : 'notas'
  const noteId = params.get('nota')
  const startNew = params.get('nueva') === '1'
  const startNewKey = startNew ? 'nueva' : (noteId ?? 'lista')
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Taller</h1>
          <div className="sub">Segundo cerebro: notas con [[enlaces]] y retroenlaces, plantilla de ensayo con tu firma y repaso espaciado.</div>
        </div>
      </div>
      <Tabs
        tabs={[
          { id: 'notas', label: 'Notas' },
          { id: 'repaso', label: 'Repaso espaciado' },
        ]}
        value={tab}
        onChange={(t) => setParams(t === 'repaso' ? { tab: 'repaso' } : {})}
      />
      <div style={{ paddingTop: 'var(--sp-3)' }}>
        {tab === 'notas' && <NotesTab key={startNewKey} initialNoteId={noteId} startNew={startNew} />}
        {tab === 'repaso' && <ReviewTab />}
      </div>
    </div>
  )
}
