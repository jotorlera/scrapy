/* Tuerca, la gata. Máquina de estados con tick de 100 ms (patrón de oneko.js, código y dibujo propios).
   - Sigue al cursor cuando se aleja más de 120 px; se sienta al llegar; se lame al azar si está quieta.
   - Se duerme tras 2 minutos sin actividad (baja a dormir sobre la cinta de mercados) y se despierta al moverse.
   - Cada 3-6 minutos rueda un tornillo por el borde inferior: lo persigue y lo saca de la pantalla de un zarpazo.
   - «prrr» al pasar el ratón; un clic la manda a la esquina inferior derecha durante 1 minuto.
   - Nunca tapa un formulario: si el foco está en un campo, se mantiene a ≥ 200 px del cursor y del campo.
   Se desactiva con el ajuste `cat_enabled` y con prefers-reduced-motion. Solo su cuerpo recibe eventos. */

import { useEffect, useRef } from 'react'
import { usePrefersReducedMotion } from '../lib/hooks'
import { useStore } from '../state/store'
import './Tuerca.css'

type Pose = 'sit' | 'walk' | 'lick' | 'sleep' | 'swat'
type Eyes = 'open' | 'closed' | 'happy'

const W = 64
const H = 48
const TICK = 100
const WALK = 10
const TROT = 17
const FOLLOW_START = 120
const FOLLOW_STOP = 36
const INPUT_KEEPOUT = 200
const SLEEP_AFTER = 120_000
const CORNER_FOR = 60_000
const SCREW_MIN = 180_000
const SCREW_MAX = 360_000

interface Machine {
  x: number
  y: number
  dir: 1 | -1
  mouse: { x: number; y: number }
  lastActivity: number
  pose: Pose
  eyes: Eyes
  idleSince: number
  lickUntil: number
  sleeping: boolean
  goingToBed: boolean
  cornerUntil: number
  screw: { x: number; y: number; vx: number; rot: number; caught: boolean } | null
  nextScrewAt: number
  swatUntil: number
  bubbleUntil: number
}

function tickerHeight(): number {
  const v = getComputedStyle(document.documentElement).getPropertyValue('--ticker-h')
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 34
}

function focusedField(): HTMLElement | null {
  const el = document.activeElement as HTMLElement | null
  if (!el) return null
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable) return el
  return null
}

function CatSvg() {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
      {/* ─── Vista lateral (andar / zarpazo), mirando a la derecha ─── */}
      <g className="pose-side">
        <path className="tail" d="M12 30 Q1 27 5 15" fill="none" stroke="#000" strokeWidth="4" strokeLinecap="round" />
        <g className="body-hit">
          <rect className="leg a fur" x="15" y="33" width="5" height="12" />
          <rect className="leg b fur" x="22" y="33" width="5" height="12" />
          <rect className="leg b fur" x="33" y="33" width="5" height="12" />
          <rect className="leg a front-paw fur" x="40" y="33" width="5" height="12" />
          <ellipse className="torso fur" cx="29" cy="29" rx="17" ry="10" />
          <path d="M38 25 Q43 32 47 30" fill="none" stroke="#ffd100" strokeWidth="3.5" strokeLinecap="round" />
          <polygon className="accent" points="41,31 43.6,32.5 43.6,35.5 41,37 38.4,35.5 38.4,32.5" stroke="#000" strokeWidth="0.6" />
          <circle cx="41" cy="34" r="0.9" fill="#000" />
          <polygon className="fur" points="39,15 41,3 48,12" />
          <polygon className="fur" points="51,12 57,3 57,15" />
          <circle className="fur" cx="47" cy="21" r="10.5" />
          <polygon className="accent" points="41.5,5.5 47,11 42,13" opacity="0.6" />
          <line className="whisker" x1="54" y1="23" x2="63" y2="21" />
          <line className="whisker" x1="54" y1="24.5" x2="63" y2="26" />
          <polygon points="54.5,22 57.5,23.5 54.5,25" fill="#9a9a9a" />
          <g className="eye-open">
            <ellipse cx="50.5" cy="20" rx="2.7" ry="3.1" fill="#ffd100" />
            <ellipse cx="51" cy="20" rx="1" ry="2.6" fill="#000" />
          </g>
          <path className="eye-closed" d="M47.8 20.5 Q50.5 22.6 53.2 20.5" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
          <path className="eye-happy" d="M47.8 21 Q50.5 17.8 53.2 21" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
        </g>
      </g>

      {/* ─── Vista frontal (sentada / lamiéndose / dormida) ─── */}
      <g className="pose-sit">
        <path className="tail" d="M44 44 Q61 47 59 33" fill="none" stroke="#000" strokeWidth="4" strokeLinecap="round" />
        <g className="body-hit">
          <ellipse className="torso fur" cx="32" cy="36" rx="15" ry="11" />
          <ellipse className="fur" cx="25" cy="46" rx="5.5" ry="2.4" />
          <ellipse className="fur" cx="39" cy="46" rx="5.5" ry="2.4" />
          <g className="head-sit">
            <polygon className="fur" points="21,15 22,2 30,10" />
            <polygon className="fur" points="34,10 42,2 43,15" />
            <polygon className="accent" points="23,5 28.5,10 24,12" opacity="0.6" />
            <polygon className="accent" points="41,5 35.5,10 40,12" opacity="0.6" />
            <circle className="fur" cx="32" cy="20" r="12" />
            <line className="whisker" x1="22" y1="24" x2="11" y2="22" />
            <line className="whisker" x1="22" y1="25.5" x2="11" y2="27" />
            <line className="whisker" x1="42" y1="24" x2="53" y2="22" />
            <line className="whisker" x1="42" y1="25.5" x2="53" y2="27" />
            <polygon points="30.5,24.5 33.5,24.5 32,26.6" fill="#9a9a9a" />
            <g className="eye-open">
              <ellipse cx="27" cy="19.5" rx="2.8" ry="3.4" fill="#ffd100" />
              <ellipse cx="27" cy="19.5" rx="1" ry="3" fill="#000" />
              <ellipse cx="37" cy="19.5" rx="2.8" ry="3.4" fill="#ffd100" />
              <ellipse cx="37" cy="19.5" rx="1" ry="3" fill="#000" />
            </g>
            <g className="eye-closed">
              <path d="M24.2 20 Q27 22.4 29.8 20" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
              <path d="M34.2 20 Q37 22.4 39.8 20" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
            </g>
            <g className="eye-happy">
              <path d="M24.2 20.6 Q27 17.2 29.8 20.6" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
              <path d="M34.2 20.6 Q37 17.2 39.8 20.6" fill="none" stroke="#ffd100" strokeWidth="1.2" strokeLinecap="round" />
            </g>
          </g>
          <path d="M21 30 Q32 36.5 43 30" fill="none" stroke="#ffd100" strokeWidth="3.5" strokeLinecap="round" />
          <polygon className="accent" points="32,33 34.6,34.5 34.6,37.5 32,39 29.4,37.5 29.4,34.5" stroke="#000" strokeWidth="0.6" />
          <circle cx="32" cy="36" r="0.9" fill="#000" />
          <ellipse className="lick-paw fur" cx="40" cy="31" rx="4" ry="6" />
        </g>
        <g className="zzz" fontSize="9">
          <text x="46" y="12">z</text>
          <text x="50" y="8" fontSize="7">z</text>
          <text x="54" y="5" fontSize="6">z</text>
        </g>
      </g>
    </svg>
  )
}

function ScrewSvg() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect x="9" y="4" width="14" height="6" fill="#ffd100" stroke="#000" strokeWidth="1" />
      <rect x="14.5" y="5.5" width="3" height="3" fill="#000" />
      <path d="M12 10 L20 10 L18 27 L14 27 Z" fill="#ffd100" stroke="#000" strokeWidth="1" />
      <g stroke="#000" strokeWidth="1.2">
        <line x1="12.6" y1="14" x2="19.4" y2="14" />
        <line x1="12.9" y1="17.5" x2="19.1" y2="17.5" />
        <line x1="13.2" y1="21" x2="18.8" y2="21" />
        <line x1="13.6" y1="24.5" x2="18.4" y2="24.5" />
      </g>
    </svg>
  )
}

function TuercaBody() {
  const catRef = useRef<HTMLDivElement>(null)
  const screwRef = useRef<HTMLDivElement>(null)
  const m = useRef<Machine | null>(null)

  useEffect(() => {
    const cat = catRef.current
    const screwEl = screwRef.current
    if (!cat || !screwEl) return
    const now = Date.now()
    const st: Machine = {
      x: Math.max(16, window.innerWidth - 200),
      y: Math.max(16, window.innerHeight - tickerHeight() - H - 12),
      dir: -1,
      mouse: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
      lastActivity: now,
      pose: 'sit',
      eyes: 'open',
      idleSince: now,
      lickUntil: 0,
      sleeping: false,
      goingToBed: false,
      cornerUntil: 0,
      screw: null,
      nextScrewAt: now + SCREW_MIN + Math.random() * (SCREW_MAX - SCREW_MIN),
      swatUntil: 0,
      bubbleUntil: 0,
    }
    m.current = st

    const setPose = (p: Pose, eyes: Eyes = 'open') => {
      if (st.pose !== p) {
        st.pose = p
        cat.setAttribute('data-pose', p)
      }
      if (st.eyes !== eyes) {
        st.eyes = eyes
        cat.setAttribute('data-eyes', eyes)
      }
    }
    const render = () => {
      cat.style.transform = `translate(${Math.round(st.x)}px, ${Math.round(st.y)}px) scaleX(${st.dir})`
      cat.setAttribute('data-bubble', Date.now() < st.bubbleUntil ? 'on' : 'off')
      if (st.screw) {
        screwEl.style.display = 'block'
        screwEl.style.transform = `translate(${Math.round(st.screw.x)}px, ${Math.round(st.screw.y)}px) rotate(${Math.round(st.screw.rot)}deg)`
      } else {
        screwEl.style.display = 'none'
      }
    }
    const center = () => ({ x: st.x + W / 2, y: st.y + H - 10 })
    const clampPos = () => {
      st.x = Math.min(window.innerWidth - W - 2, Math.max(2, st.x))
      st.y = Math.min(window.innerHeight - H - 2, Math.max(2, st.y))
    }
    const stepTowards = (tx: number, ty: number, speed: number): number => {
      const c = center()
      const dx = tx - c.x
      const dy = ty - c.y
      const d = Math.hypot(dx, dy)
      if (d < 1) return 0
      const k = Math.min(1, speed / d)
      st.x += dx * k
      st.y += dy * k
      if (Math.abs(dx) > 2) st.dir = dx > 0 ? 1 : -1
      clampPos()
      return d
    }
    const stepAway = (px: number, py: number, speed: number) => {
      const c = center()
      let dx = c.x - px
      let dy = c.y - py
      const d = Math.hypot(dx, dy) || 1
      dx /= d
      dy /= d
      st.x += dx * speed
      st.y += dy * speed
      if (Math.abs(dx) > 0.2) st.dir = dx > 0 ? 1 : -1
      clampPos()
    }
    const nearestPointOfRect = (r: DOMRect, x: number, y: number) => ({ x: Math.min(Math.max(x, r.left), r.right), y: Math.min(Math.max(y, r.top), r.bottom) })

    const activity = () => {
      st.lastActivity = Date.now()
      if (st.sleeping || st.goingToBed) {
        st.sleeping = false
        st.goingToBed = false
        st.idleSince = Date.now()
        setPose('sit', 'open')
      }
    }
    const onMove = (e: MouseEvent) => {
      st.mouse = { x: e.clientX, y: e.clientY }
      activity()
    }
    const onKey = () => activity()
    const onEnter = () => {
      st.bubbleUntil = Date.now() + 1500
      cat.setAttribute('data-bubble', 'on')
    }
    const onClick = (e: MouseEvent) => {
      e.stopPropagation()
      st.cornerUntil = Date.now() + CORNER_FOR
      st.sleeping = false
      st.goingToBed = false
      st.bubbleUntil = 0
    }
    window.addEventListener('mousemove', onMove, { passive: true })
    window.addEventListener('keydown', onKey, { passive: true })
    cat.addEventListener('mouseenter', onEnter)
    cat.addEventListener('click', onClick)

    const spawnScrew = () => {
      const fromLeft = Math.random() < 0.5
      const y = window.innerHeight - tickerHeight() - 24
      st.screw = { x: fromLeft ? -24 : window.innerWidth + 2, y, vx: fromLeft ? 3.2 : -3.2, rot: 0, caught: false }
    }

    const loop = () => {
      const t = Date.now()
      const c = center()
      const field = focusedField()

      // Tornillo: aparición y rodadura
      if (!st.screw && t >= st.nextScrewAt && !st.sleeping && !document.hidden) {
        spawnScrew()
      }
      if (st.screw) {
        const s = st.screw
        s.x += s.vx
        s.rot += s.vx * 9
        if (!s.caught && (s.x < -40 || s.x > window.innerWidth + 40)) {
          st.screw = null
          st.nextScrewAt = t + SCREW_MIN + Math.random() * (SCREW_MAX - SCREW_MIN)
        } else if (s.caught && (s.x < -80 || s.x > window.innerWidth + 80)) {
          st.screw = null
          st.nextScrewAt = t + SCREW_MIN + Math.random() * (SCREW_MAX - SCREW_MIN)
        }
      }

      // Zarpazo en curso
      if (t < st.swatUntil) {
        setPose('swat', 'open')
        render()
        return
      }
      if (st.pose === 'swat' && st.screw && !st.screw.caught) {
        st.screw.caught = true
        st.screw.vx = st.dir * 42
      }

      // Persecución del tornillo (tiene prioridad sobre el cursor)
      if (st.screw && !st.screw.caught) {
        const d = stepTowards(st.screw.x + 11, st.screw.y + 16, TROT)
        if (d < 34) {
          st.swatUntil = t + 450
          setPose('swat', 'open')
        } else {
          setPose('walk', 'open')
        }
        render()
        return
      }

      // Rincón tras un clic
      if (t < st.cornerUntil) {
        const tx = window.innerWidth - W / 2 - 10
        const ty = window.innerHeight - tickerHeight() - 12
        const d = stepTowards(tx, ty, TROT)
        if (d < 8) setPose('sit', 'open')
        else setPose('walk', 'open')
        render()
        return
      }

      // Sueño tras 2 min sin actividad: baja a dormir sobre la cinta
      if (!st.sleeping && t - st.lastActivity > SLEEP_AFTER) {
        st.goingToBed = true
      }
      if (st.goingToBed) {
        const ty = window.innerHeight - tickerHeight() - 10
        const d = stepTowards(c.x, ty, WALK)
        if (d < 6) {
          st.goingToBed = false
          st.sleeping = true
          setPose('sleep', 'closed')
        } else setPose('walk', 'open')
        render()
        return
      }
      if (st.sleeping) {
        setPose('sleep', 'closed')
        render()
        return
      }

      // Zona de exclusión si hay un campo con foco
      if (field) {
        const r = field.getBoundingClientRect()
        const np = nearestPointOfRect(r, c.x, c.y)
        const dField = Math.hypot(np.x - c.x, np.y - c.y)
        const dMouse = Math.hypot(st.mouse.x - c.x, st.mouse.y - c.y)
        if (dField < INPUT_KEEPOUT - 10 || dMouse < INPUT_KEEPOUT - 10) {
          if (dField < dMouse) stepAway(np.x, np.y, WALK)
          else stepAway(st.mouse.x, st.mouse.y, WALK)
          setPose('walk', 'open')
          render()
          return
        }
        setPose('sit', 'open')
        render()
        return
      }

      // Seguir al cursor
      const dMouse = Math.hypot(st.mouse.x - c.x, st.mouse.y - c.y)
      if (st.pose === 'walk' ? dMouse > FOLLOW_STOP : dMouse > FOLLOW_START) {
        stepTowards(st.mouse.x, st.mouse.y, WALK)
        setPose('walk', 'open')
        st.idleSince = t
        st.lickUntil = 0
        render()
        return
      }

      // Quieta: sentarse y lamerse al azar
      if (t < st.lickUntil) {
        setPose('lick', 'happy')
      } else {
        if (st.pose === 'lick') st.idleSince = t
        if (t - st.idleSince > 4000 && Math.random() < 0.012) st.lickUntil = t + 2200 + Math.random() * 1500
        setPose('sit', 'open')
      }
      render()
    }

    render()
    const id = window.setInterval(loop, TICK)
    return () => {
      window.clearInterval(id)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('keydown', onKey)
      cat.removeEventListener('mouseenter', onEnter)
      cat.removeEventListener('click', onClick)
    }
  }, [])

  return (
    <>
      <div ref={catRef} className="tuerca" data-pose="sit" data-eyes="open" data-bubble="off" aria-hidden="true">
        <div className="bubble">prrr</div>
        <CatSvg />
      </div>
      <div ref={screwRef} className="tuerca-screw" style={{ display: 'none' }} aria-hidden="true">
        <ScrewSvg />
      </div>
    </>
  )
}

export function Tuerca() {
  const { settings, settingsLoaded } = useStore()
  const reduced = usePrefersReducedMotion()
  if (!settingsLoaded || !settings.cat_enabled || reduced) return null
  return <TuercaBody />
}
