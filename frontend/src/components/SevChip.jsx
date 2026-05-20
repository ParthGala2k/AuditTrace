import { T, SEV_COLOR, SEV_BG, SEV_LABEL } from '../tokens'

export default function SevChip({ level }) {
  const sev = (level || 'low').toLowerCase().replace('critical', 'high')
  const color = SEV_COLOR[sev] || T.mute
  const bg    = SEV_BG[sev]   || T.line2
  const label = SEV_LABEL[sev] || level?.toUpperCase() || 'LOW'

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontFamily: T.mono, fontSize: 10, letterSpacing: 0.6, fontWeight: 600,
      color, background: bg, padding: '3px 7px', borderRadius: 3,
      border: `1px solid ${color}33`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: color }} />
      {label}
    </span>
  )
}
