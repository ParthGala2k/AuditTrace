import { useState } from 'react'
import { T, MODEL_LABELS } from '../tokens'
import SevChip from './SevChip'
import DiffBlock from './DiffBlock'
import { fetchFix } from '../api'

export default function IssueCard({ violation, expanded, onToggle, animDelay }) {
  const [fixState, setFixState] = useState('idle') // idle | loading | loaded | error
  const [fixData, setFixData]   = useState(null)

  const sev   = (violation.severity || 'low').toLowerCase()
  const color = sev === 'high' || sev === 'critical' ? T.high : sev === 'medium' || sev === 'med' ? T.med : T.low
  const line  = (violation.line || [0])[0]
  const file  = (violation.file || '').split('\\').pop().split('/').pop()

  async function handleToggle() {
    onToggle()
    if (!expanded && fixState === 'idle') {
      setFixState('loading')
      try {
        const data = await fetchFix({
          clauseText: violation.clause_text,
          checkId:    violation.check_id,
          resource:   violation.resource,
          filePath:   violation.file,
        })
        setFixData(data)
        setFixState('loaded')
      } catch {
        setFixState('error')
      }
    }
  }

  function copyPatch() {
    if (!fixData?.diff) return
    const patch = fixData.diff.map(l => {
      const s = l.k === 'add' ? '+' : l.k === 'del' ? '-' : ' '
      return `${s}${l.t}`
    }).join('\n')
    navigator.clipboard.writeText(patch)
  }

  const agreedLabel    = (violation.models_agreed    || []).map(m => MODEL_LABELS[m] || m.split('/').pop()).join(', ')
  const disagreedLabel = (violation.models_disagreed || []).map(m => MODEL_LABELS[m] || m.split('/').pop()).join(', ')

  return (
    <div style={{
      border: `1px solid ${expanded ? T.ink2 : T.line}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 6, background: T.card, overflow: 'hidden',
      transition: 'border-color 160ms ease',
      animation: `flyUp 380ms cubic-bezier(.2,.8,.2,1) ${animDelay}ms backwards`,
    }}>
      {/* clickable header row */}
      <div onClick={handleToggle} style={{
        padding: '14px 16px', display: 'flex', gap: 14,
        alignItems: 'flex-start', cursor: 'pointer',
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
            <SevChip level={sev} />
            <span style={{
              fontFamily: T.mono, fontSize: 10.5, color: T.mute,
              background: T.line2, padding: '2px 6px', borderRadius: 3,
            }}>
              {violation.clause_id}
            </span>
            <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.mute }}>
              {file}<span style={{ color: T.ink2 }}>:{line}</span>
            </span>
            {violation.confidence && (
              <span style={{
                fontFamily: T.mono, fontSize: 10, color: T.mute,
                border: `1px solid ${T.line}`, padding: '2px 6px', borderRadius: 3,
              }}>
                {violation.confidence}
              </span>
            )}
          </div>

          {/* title */}
          <div style={{
            fontSize: 13.5, fontWeight: 500, color: T.ink,
            lineHeight: 1.4, marginBottom: 6,
          }}>
            {violation.clause_text}
          </div>

          {/* code hint */}
          <div style={{
            fontFamily: T.mono, fontSize: 11, color: T.ink2,
            background: T.paper, border: `1px solid ${T.line2}`,
            borderRadius: 4, padding: '6px 9px',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            <span style={{ color: T.mute, marginRight: 8 }}>L{line}</span>
            {violation.check_id} · {violation.resource || violation.file}
          </div>
        </div>

        {/* right meta */}
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 4,
          alignItems: 'flex-end', flexShrink: 0,
        }}>
          <span style={{
            fontFamily: T.mono, fontSize: 10, color: T.mute,
            border: `1px solid ${T.line}`, padding: '3px 7px', borderRadius: 3,
          }}>
            {expanded ? 'collapse ▴' : 'view fix ▾'}
          </span>
          {agreedLabel && (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.low, textAlign: 'right' }}>
              ✓ {agreedLabel}
            </span>
          )}
          {disagreedLabel && (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, textAlign: 'right' }}>
              ✗ {disagreedLabel}
            </span>
          )}
        </div>
      </div>

      {/* expanded diff area */}
      {expanded && (
        <div style={{ padding: '0 14px 14px', animation: 'flyUp 240ms ease' }}>
          {fixState === 'error' ? (
            <div style={{
              padding: 12, border: `1px solid ${T.line}`, borderRadius: 6,
              fontFamily: T.mono, fontSize: 11, color: T.mute, background: T.paper,
            }}>
              Fix generation failed. Try again.
            </div>
          ) : (
            <DiffBlock
              loading={fixState === 'loading'}
              diff={fixData?.diff}
              explanation={fixData?.explanation}
              file={violation.file}
              onCopy={copyPatch}
              onPR={() => alert('PR creation coming soon')}
            />
          )}
        </div>
      )}
    </div>
  )
}
