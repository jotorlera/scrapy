import { useStore } from '../../state/store'
import { Modal } from '../ui/Modal'

export const SHORTCUTS: Array<{ keys: string; desc: string; group: string }> = [
  { group: 'Navegación', keys: 'g r', desc: 'Radar' },
  { group: 'Navegación', keys: 'g e', desc: 'Eventos' },
  { group: 'Navegación', keys: 'g p', desc: 'Prisma' },
  { group: 'Navegación', keys: 'g i', desc: 'Primarias' },
  { group: 'Navegación', keys: 'g m', desc: 'Economía / Mercados' },
  { group: 'Navegación', keys: 'g g', desc: 'Geopolítica / Países' },
  { group: 'Navegación', keys: 'g o', desc: 'Actores' },
  { group: 'Navegación', keys: 'g a', desc: 'Ágora' },
  { group: 'Navegación', keys: 'g h', desc: 'Archivo' },
  { group: 'Navegación', keys: 'g t', desc: 'Taller' },
  { group: 'Navegación', keys: 'g f', desc: 'Pronósticos' },
  { group: 'Navegación', keys: 'g c', desc: 'Mando' },
  { group: 'Navegación', keys: 'g s', desc: 'Simulador' },
  { group: 'Navegación', keys: 'g b', desc: 'Brief' },
  { group: 'Navegación', keys: 'g d', desc: 'Dieta' },
  { group: 'Navegación', keys: 'g x', desc: 'Sala de máquinas' },
  { group: 'Modos', keys: '1 / 2 / 3', desc: 'ANALISTA / PENSADOR / CEO' },
  { group: 'Listas', keys: 'j / k', desc: 'Bajar / subir en la lista' },
  { group: 'Listas', keys: 'o / Enter', desc: 'Abrir el elemento activo' },
  { group: 'Acciones', keys: '⌘K / Ctrl K', desc: 'Buscar / preguntar' },
  { group: 'Acciones', keys: 'n', desc: 'Nueva nota' },
  { group: 'Acciones', keys: 'f', desc: 'Nuevo pronóstico' },
  { group: 'Acciones', keys: '[', desc: 'Plegar / abrir el panel contextual' },
  { group: 'Acciones', keys: 'Esc', desc: 'Cerrar diálogos' },
  { group: 'Acciones', keys: '?', desc: 'Esta ayuda' },
]

export function ShortcutsHelp() {
  const { helpOpen, setHelpOpen } = useStore()
  const groups = Array.from(new Set(SHORTCUTS.map((s) => s.group)))
  return (
    <Modal open={helpOpen} title="Atajos de teclado" onClose={() => setHelpOpen(false)} initialFocus={false}>
      <div className="shortcuts">
        {groups.map((g) => (
          <div key={g}>
            <div className="label" style={{ marginBottom: 6 }}>
              {g}
            </div>
            <dl>
              {SHORTCUTS.filter((s) => s.group === g).map((s) => (
                <div key={s.keys} style={{ display: 'contents' }}>
                  <dt>
                    <kbd>{s.keys}</kbd>
                  </dt>
                  <dd>{s.desc}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
      <p className="muted small" style={{ marginTop: 12 }}>
        Los atajos no actúan mientras escribes en un campo. Las secuencias «g …» esperan 900 ms a la segunda tecla.
      </p>
    </Modal>
  )
}
