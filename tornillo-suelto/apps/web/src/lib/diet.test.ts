import { afterEach, describe, expect, it } from 'vitest'
import { startDietSession, type DietLogBody } from './diet'

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  document.dispatchEvent(new Event('visibilitychange'))
}

function session() {
  const sent: DietLogBody[] = []
  const clock = { t: 0 }
  const stop = startDietSession({ event_id: 'e1' }, { send: (b) => sent.push(b), now: () => clock.t })
  return { sent, clock, stop }
}

describe('startDietSession', () => {
  afterEach(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })
  })

  it('envía open como marcador y read con los segundos visibles al parar', () => {
    const { sent, clock, stop } = session()
    expect(sent).toEqual([{ event_id: 'e1', action: 'open' }])
    clock.t = 5000
    stop()
    expect(sent).toEqual([
      { event_id: 'e1', action: 'open' },
      { event_id: 'e1', action: 'read', seconds: 5 },
    ])
  })

  it('no envía read por debajo del umbral', () => {
    const { sent, clock, stop } = session()
    clock.t = 2000
    stop()
    expect(sent).toHaveLength(1)
  })

  it('pagehide envía el read pendiente y no se duplica al parar', () => {
    const { sent, clock, stop } = session()
    clock.t = 4000
    window.dispatchEvent(new Event('pagehide'))
    expect(sent[1]).toEqual({ event_id: 'e1', action: 'read', seconds: 4 })
    clock.t = 4500
    stop()
    expect(sent).toHaveLength(2)
  })

  it('hidden → visible → parar produce dos tramos cuya suma es el tiempo visible', () => {
    const { sent, clock, stop } = session()
    clock.t = 6000
    setVisibility('hidden')
    expect(sent[1]).toEqual({ event_id: 'e1', action: 'read', seconds: 6 })
    clock.t = 60000 // 54 s en segundo plano: no cuentan
    setVisibility('visible')
    expect(sent).toHaveLength(2)
    clock.t = 64000
    stop()
    expect(sent[2]).toEqual({ event_id: 'e1', action: 'read', seconds: 4 })
    const total = sent.filter((b) => b.action === 'read').reduce((a, b) => a + (b.seconds ?? 0), 0)
    expect(total).toBe(10)
  })

  it('parar mientras la pestaña sigue oculta no imputa el tiempo en segundo plano', () => {
    const { sent, clock, stop } = session()
    clock.t = 3000
    setVisibility('hidden')
    clock.t = 90000
    stop()
    expect(sent.map((b) => b.seconds)).toEqual([undefined, 3])
  })

  it('quita los oyentes al parar', () => {
    const { sent, clock, stop } = session()
    clock.t = 5000
    stop()
    clock.t = 20000
    window.dispatchEvent(new Event('pagehide'))
    setVisibility('hidden')
    expect(sent).toHaveLength(2)
  })
})
