import { SHORTCUTS } from '../components/shell/ShortcutsHelp'
import { Level, ProvenanceChip, StatusIcon } from '../components/ui/basics'
import './screens.css'

export default function Help() {
  const groups = Array.from(new Set(SHORTCUTS.map((s) => s.group)))
  return (
    <div className="help">
      <div className="screen-head">
        <div>
          <h1>Ayuda</h1>
          <div className="sub">Atajos, niveles epistémicos y etiquetas de procedencia. Todo lo que ves tiene fuente; nada se disfraza.</div>
        </div>
      </div>

      <section className="section" style={{ marginTop: 0 }}>
        <h2>Atajos de teclado</h2>
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
      </section>

      <section className="section">
        <h2>Los cuatro niveles epistémicos</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>
                <Level level="fact" />
              </td>
              <td>Enunciado descriptivo sobre algo que ocurrió o existe. Se confirma con documento primario o con ≥ 2 fuentes independientes de tier ≤ 2.</td>
            </tr>
            <tr>
              <td>
                <Level level="data" />
              </td>
              <td>Afirmación con cifra (porcentajes, importes, recuentos). Prioridad alta de verificación; la fuente estadística manda.</td>
            </tr>
            <tr>
              <td>
                <Level level="academic" />
              </td>
              <td>Procede de una fuente académica (papers, institutos). Se cita como hallazgo, no como hecho establecido.</td>
            </tr>
            <tr>
              <td>
                <Level level="opinion" />
              </td>
              <td>Juicio, recomendación o pregunta retórica (marcadores «debería», editorial, columna). Nunca aparece en «Qué ha pasado».</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Estados de una afirmación</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>
                <StatusIcon status="confirmed" />
              </td>
              <td>Hay primaria o dos fuentes independientes que la sostienen.</td>
            </tr>
            <tr>
              <td>
                <StatusIcon status="disputed" />
              </td>
              <td>Otra fuente aporta evidencia en contra; se muestran ambas lado a lado.</td>
            </tr>
            <tr>
              <td>
                <StatusIcon status="refuted" />
              </td>
              <td>La evidencia en contra prevalece (corrección, desmentido oficial).</td>
            </tr>
            <tr>
              <td>
                <StatusIcon status="unverified" />
              </td>
              <td>Una sola fuente. Con check-worthiness ≥ 0,6 pasa a «Lo que no sabemos» como pregunta abierta.</td>
            </tr>
          </tbody>
        </table>
        <p className="muted small">Cada cambio de estado queda registrado con fecha y evidencia (claim_revision) y aparece en la cronología del evento.</p>
      </section>

      <section className="section">
        <h2>Etiquetas de procedencia</h2>
        <table className="table">
          <tbody>
            <tr>
              <td>
                <ProvenanceChip titleSource="lead_document" />
              </td>
              <td>El título del evento es el titular del documento principal (sin clave de API no se generan títulos neutros).</td>
            </tr>
            <tr>
              <td>
                <ProvenanceChip titleSource="llm" />
              </td>
              <td>El título lo redactó un modelo a partir de las afirmaciones registradas.</td>
            </tr>
            <tr>
              <td>
                <ProvenanceChip extractedBy="heuristic:v1" />
              </td>
              <td>Afirmación extraída por reglas: frases literales del titular y la entradilla; la afirmación es la cita.</td>
            </tr>
            <tr>
              <td>
                <ProvenanceChip extractedBy="claude" />
              </td>
              <td>Afirmación extraída por un modelo; la cita se ha verificado en el texto antes de guardarla (cita o descarta).</td>
            </tr>
            <tr>
              <td>
                <ProvenanceChip composedBy="compuesto por reglas" />
              </td>
              <td>Brief compuesto por cuotas y materialidad, sin modelo. «Redactado por el editor» = texto de modelo sobre esos mismos hechos.</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Puntuaciones con desglose</h2>
        <p>
          Cada puntuación lleva un icono <span className="info-btn" aria-hidden="true">i</span> que abre su desglose: la <strong>materialidad</strong> (logística sobre rasgos: cambio de estado, poder, irreversibilidad, amplitud, primaria, novedad, cobertura independiente), el <strong>índice de silencio</strong> (S = (E − O)/√E con la cuota de 30 días) y las <strong>probabilidades</strong> (usuario, ATLAS, tasa base, mercado). Ninguna caja negra.
        </p>
      </section>

      <section className="section">
        <h2>Tuerca</h2>
        <p>
          La gata sigue al cursor, se sienta cuando llega, se lame si se aburre, se duerme sobre la cinta a los dos minutos y persigue el tornillo que rueda de vez en cuando. Pasa el ratón para que ronronee; un clic la manda a la esquina un minuto. Nunca tapa un formulario. Se apaga en Ajustes o con <code>prefers-reduced-motion</code>.
        </p>
      </section>
    </div>
  )
}
