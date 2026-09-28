import { useMemo, useState, type ReactNode } from 'react'

export interface Column<T> {
  key: string
  label: ReactNode
  render: (row: T) => ReactNode
  num?: boolean
  sort?: (row: T) => number | string | null | undefined
  width?: number | string
  title?: string
}

/** Tabla densa con ordenación por columna y filas navegables (j/k, Enter). */
export function DataTable<T>({ rows, columns, rowKey, onRow, maxHeight, empty = 'Sin filas', initialSort, rowClass }: { rows: T[]; columns: Column<T>[]; rowKey: (r: T) => string; onRow?: (r: T) => void; maxHeight?: number | string; empty?: ReactNode; initialSort?: { key: string; dir: 'asc' | 'desc' }; rowClass?: (r: T) => string | undefined }) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(initialSort ?? null)
  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sort) return rows
    const s = col.sort
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const va = s(a)
      const vb = s(b)
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir
      return String(va).localeCompare(String(vb), 'es') * dir
    })
  }, [rows, sort, columns])
  const toggle = (key: string) => {
    setSort((s) => (s?.key === key ? (s.dir === 'desc' ? { key, dir: 'asc' } : null) : { key, dir: 'desc' }))
  }
  return (
    <div className="datatable-wrap" style={maxHeight ? ({ '--dt-max-h': typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight } as React.CSSProperties) : undefined}>
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? 'num' : undefined} style={{ width: c.width }} title={c.title}>
                {c.sort ? (
                  <button type="button" className="btn-link" style={{ color: 'inherit', font: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit' }} onClick={() => toggle(c.key)} aria-sort={sort?.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    {c.label}
                    {sort?.key === c.key ? (sort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
                  </button>
                ) : (
                  c.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="muted">
                {empty}
              </td>
            </tr>
          )}
          {sorted.map((r) => (
            <tr
              key={rowKey(r)}
              className={rowClass?.(r)}
              data-nav-item={onRow ? '' : undefined}
              tabIndex={onRow ? 0 : undefined}
              onClick={onRow ? () => onRow(r) : undefined}
              onKeyDown={
                onRow
                  ? (e) => {
                      if (e.key === 'Enter' && e.target === e.currentTarget) onRow(r)
                    }
                  : undefined
              }
            >
              {columns.map((c) => (
                <td key={c.key} className={c.num ? 'num' : undefined}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
