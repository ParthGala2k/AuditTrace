import { T } from '../tokens'

export default function ScanProgress({ percent, scanning, compact }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        width: compact ? 7 : 9, height: compact ? 7 : 9, borderRadius: 999, flexShrink: 0,
        background: scanning ? T.med : percent > 0 ? T.low : T.line,
        boxShadow: scanning ? `0 0 0 4px ${T.med}33` : 'none',
        animation: scanning ? 'pulse 1.2s infinite' : 'none',
        transition: 'background 0.3s',
      }} />
      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.ink2, whiteSpace: 'nowrap' }}>
        {scanning ? `scanning · ${percent}%` : percent === 100 ? 'complete' : 'idle'}
      </span>
      <div style={{
        flex: 1, height: 3, background: T.line2, borderRadius: 999,
        overflow: 'hidden', minWidth: compact ? 80 : 120,
      }}>
        <div style={{
          width: `${percent}%`, height: '100%', background: T.ink,
          borderRadius: 999, transition: 'width 300ms ease',
        }} />
      </div>
    </div>
  )
}
