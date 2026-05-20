import { T } from '../tokens'

export default function DiffBlock({ diff, explanation, file, loading, onCopy, onPR }) {
  if (loading) {
    return (
      <div style={{
        border: `1px solid ${T.line}`, borderRadius: 6,
        background: T.card, padding: 20,
        display: 'flex', alignItems: 'center', gap: 10,
        fontFamily: T.mono, fontSize: 12, color: T.mute,
        animation: 'shimmer 1.5s infinite',
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: 999, background: T.med,
          animation: 'pulse 1s infinite',
        }} />
        generating fix…
      </div>
    )
  }

  if (!diff) return null

  const dels = diff.filter(l => l.k === 'del').length
  const adds = diff.filter(l => l.k === 'add').length

  return (
    <div style={{
      border: `1px solid ${T.line}`, borderRadius: 6,
      background: T.card, overflow: 'hidden',
    }}>
      {/* diff header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 12px', borderBottom: `1px solid ${T.line2}`,
        background: T.paper, fontFamily: T.mono, fontSize: 11, color: T.ink2,
      }}>
        <span style={{ color: T.mute }}>diff</span>
        <span>{file || 'terraform'}</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: T.high }}>−{dels}</span>
        <span style={{ color: T.low }}>+{adds}</span>
      </div>

      {/* diff lines */}
      <div style={{ height: 220, overflow: 'auto' }}>
        {diff.map((line, i) => {
          const bg     = line.k === 'add' ? `${T.low}18` : line.k === 'del' ? `${T.high}12` : 'transparent'
          const sigil  = line.k === 'add' ? '+' : line.k === 'del' ? '−' : ' '
          const scolor = line.k === 'add' ? T.low : line.k === 'del' ? T.high : T.mute
          return (
            <div key={i} style={{ display: 'flex', background: bg }}>
              <div style={{
                width: 44, textAlign: 'right', padding: '0 8px',
                fontFamily: T.mono, fontSize: 12, lineHeight: '20px',
                color: T.mute, flexShrink: 0, userSelect: 'none',
              }}>
                {line.n}
              </div>
              <div style={{
                width: 18, textAlign: 'center', flexShrink: 0,
                fontFamily: T.mono, fontSize: 12, lineHeight: '20px',
                color: scolor, fontWeight: 600, userSelect: 'none',
              }}>
                {sigil}
              </div>
              <div style={{
                flex: 1, fontFamily: T.mono, fontSize: 12, lineHeight: '20px',
                color: T.ink, whiteSpace: 'pre',
              }}>
                {line.t}
              </div>
            </div>
          )
        })}
      </div>

      {/* footer */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderTop: `1px solid ${T.line2}`,
        background: T.paper,
      }}>
        {explanation && (
          <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.mute, flex: 1 }}>
            {explanation}
          </span>
        )}
        <button onClick={onCopy} style={{
          padding: '6px 12px', borderRadius: 5,
          border: `1px solid ${T.line}`, background: T.card,
          color: T.ink, fontFamily: T.mono, fontSize: 11,
          cursor: 'pointer',
        }}>
          copy patch
        </button>
        <button onClick={onPR} style={{
          padding: '6px 12px', borderRadius: 5,
          border: `1px solid ${T.ink}`, background: T.ink,
          color: T.paper, fontFamily: T.mono, fontSize: 11,
          cursor: 'pointer',
        }}>
          open PR ↗
        </button>
      </div>
    </div>
  )
}
