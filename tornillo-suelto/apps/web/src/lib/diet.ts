/* Sesión de lectura para la DIETA.
   - `open` al empezar: solo un marcador (el motor no le imputa tiempo).
   - `read` con los segundos realmente visibles, enviado al ocultar la pestaña (visibilitychange → hidden), al
     descargar la página (pagehide) y al parar (desmontaje). Cada envío reinicia el reloj, así que ningún tramo
     se cuenta dos veces; el tiempo en segundo plano (pestaña oculta) no se cuenta.
   Sin dependencias de React para poder probarlo con jsdom. */

export interface DietRef {
  event_id?: string
  document_id?: string
}

export interface DietLogBody extends DietRef {
  action: 'open' | 'read'
  seconds?: number
}

export type DietSender = (body: DietLogBody) => void

/** Tramos por debajo de este umbral no se envían (ruido de navegación). */
export const MIN_READ_SECONDS = 3

export interface DietSessionOptions {
  send: DietSender
  /** Reloj en ms (inyectable en pruebas). */
  now?: () => number
  doc?: Document
  win?: Window
}

/** Arranca una sesión y devuelve la función de parada: envía el tramo pendiente y quita los oyentes. */
export function startDietSession(ref: DietRef, opts: DietSessionOptions): () => void {
  const now = opts.now ?? (() => Date.now())
  const doc = opts.doc ?? document
  const win = opts.win ?? window
  const base: DietRef = {}
  if (ref.event_id) base.event_id = ref.event_id
  if (ref.document_id) base.document_id = ref.document_id

  let started = now()
  let paused = false
  opts.send({ ...base, action: 'open' })

  const flush = () => {
    if (paused) return
    const seconds = Math.round((now() - started) / 1000)
    started = now()
    if (seconds >= MIN_READ_SECONDS) opts.send({ ...base, action: 'read', seconds })
  }
  const pause = () => {
    flush()
    paused = true
  }
  const resume = () => {
    paused = false
    started = now()
  }
  const onVisibility = () => {
    if (doc.visibilityState === 'hidden') pause()
    else resume()
  }

  doc.addEventListener('visibilitychange', onVisibility)
  win.addEventListener('pagehide', pause)
  win.addEventListener('pageshow', resume)

  return () => {
    flush()
    doc.removeEventListener('visibilitychange', onVisibility)
    win.removeEventListener('pagehide', pause)
    win.removeEventListener('pageshow', resume)
  }
}
