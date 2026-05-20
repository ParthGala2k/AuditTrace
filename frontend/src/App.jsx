import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { T, AVAILABLE_MODELS, MODEL_LABELS } from './tokens'
import ScanProgress from './components/ScanProgress'
import IssueCard from './components/IssueCard'
import EvalPanel from './components/EvalPanel'
import { fetchPolicies, runAudit } from './api'

// ─── small shared primitives ────────────────────────────────────────────────

function Btn({ children, primary, onClick, disabled, mono }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '9px 16px', borderRadius: 6, cursor: disabled ? 'not-allowed' : 'pointer',
      border: `1px solid ${primary ? T.ink : T.line}`,
      background: primary ? (disabled ? T.ink2 : T.ink) : T.card,
      color: primary ? T.paper : disabled ? T.mute : T.ink,
      fontFamily: mono ? T.mono : T.sans, fontSize: 12, fontWeight: 500,
      opacity: disabled ? 0.6 : 1, transition: 'opacity 0.15s',
      display: 'inline-flex', alignItems: 'center', gap: 6,
    }}>{children}</button>
  )
}

function Field({ label, value, onChange, placeholder, mono }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{
        fontFamily: T.sans, fontSize: 11, color: T.mute,
        textTransform: 'uppercase', letterSpacing: 0.8,
      }}>{label}</div>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          padding: '10px 12px', borderRadius: 6, border: `1px solid ${T.line}`,
          background: T.card, color: T.ink, fontFamily: mono ? T.mono : T.sans,
          fontSize: 13, outline: 'none', width: '100%',
        }}
        onFocus={e  => e.target.style.borderColor = T.ink2}
        onBlur={e   => e.target.style.borderColor = T.line}
      />
    </div>
  )
}

// ─── Sticky header ───────────────────────────────────────────────────────────

function Header({ compact, repoUrl, setRepoUrl, policy, setPolicy, policies,
                  selectedModels, toggleModel, scanning, percent,
                  onRun, onCancel, canRun }) {
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 10,
      background: T.paper, borderBottom: `1px solid ${T.line}`,
      transition: 'all 220ms ease',
    }}>
      {/* app chrome */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: compact ? '8px 48px' : '12px 48px',
        background: T.card, borderBottom: `1px solid ${T.line}`,
        transition: 'padding 220ms ease',
      }}>
        {/* logo mark */}
        <div style={{
          width: compact ? 22 : 30, height: compact ? 22 : 30,
          borderRadius: 6, border: `2px solid ${T.ink}`, flexShrink: 0,
          background: `linear-gradient(135deg, ${T.ink} 0 50%, transparent 50%)`,
          transition: 'all 220ms ease',
        }} />
        <div style={{
          fontWeight: 700, fontSize: compact ? 14 : 18, letterSpacing: -0.4,
          transition: 'font-size 220ms ease',
        }}>
          AuditTrace
        </div>
        <div style={{ fontFamily: T.mono, fontSize: compact ? 11 : 13, color: T.mute }}>/scan</div>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: T.mono, fontSize: 13, color: T.mute, cursor: 'pointer', marginRight: 8 }}>history</span>
        <span style={{ fontFamily: T.mono, fontSize: 13, color: T.mute, cursor: 'pointer' }}>settings</span>
      </div>

      {(
        /* full config form — title hides on scroll, form stays sticky */
        <div style={{ padding: '0 48px 20px' }}>
          {/* title — only visible when not scrolled */}
          <div style={{
            overflow: 'hidden',
            maxHeight: compact ? 0 : 100,
            opacity: compact ? 0 : 1,
            marginBottom: compact ? 0 : 18,
            paddingTop: compact ? 0 : 24,
            transition: 'max-height 220ms ease, opacity 180ms ease, margin-bottom 220ms ease, padding-top 220ms ease',
          }}>
            <div style={{
              fontFamily: T.mono, fontSize: 11, color: T.mute,
              marginBottom: 4, letterSpacing: 0.6,
            }}>NEW SCAN</div>
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.5, marginBottom: 4 }}>
              Audit a repository
            </div>
            <div style={{ fontSize: 13, color: T.mute, maxWidth: 520 }}>
              Point AuditTrace at a GitHub repo, pick the models, choose a compliance spec.
              Findings stream in below as they're discovered.
            </div>
          </div>

          <div style={{
            background: T.card, border: `1px solid ${T.line}`,
            borderRadius: 8, padding: 20,
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
          }}>
            {/* repo url */}
            <div style={{ gridColumn: '1 / -1' }}>
              <Field
                label="Repository URL"
                value={repoUrl}
                onChange={setRepoUrl}
                placeholder="https://github.com/owner/repo"
                mono
              />
            </div>

            {/* models */}
            <div>
              <div style={{
                fontFamily: T.sans, fontSize: 11, color: T.mute,
                textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8,
              }}>
                LLM Models · {selectedModels.length} selected
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {AVAILABLE_MODELS.map(m => {
                  const on = selectedModels.includes(m)
                  return (
                    <span key={m} onClick={() => toggleModel(m)} style={{
                      padding: '7px 11px', borderRadius: 999, cursor: 'pointer',
                      border: `1px solid ${on ? T.ink : T.line}`,
                      background: on ? T.ink : T.card,
                      color: on ? T.paper : T.ink2,
                      fontFamily: T.sans, fontSize: 12,
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      transition: 'all 140ms ease',
                      userSelect: 'none',
                    }}>
                      <span style={{
                        width: 10, height: 10, borderRadius: 2,
                        border: `1.5px solid ${on ? T.paper : T.line}`,
                        background: on ? T.paper : 'transparent',
                      }} />
                      {MODEL_LABELS[m] || m.split('/').pop()}
                    </span>
                  )
                })}
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 10.5, color: T.mute, marginTop: 8 }}>
                click to toggle · all selected by default
              </div>
            </div>

            {/* spec */}
            <div>
              <div style={{
                fontFamily: T.sans, fontSize: 11, color: T.mute,
                textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6,
              }}>
                Compliance Spec
              </div>
              <select
                value={policy}
                onChange={e => setPolicy(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 6,
                  border: `1px solid ${T.line}`, background: T.card,
                  color: T.ink, fontFamily: T.sans, fontSize: 13,
                  outline: 'none', cursor: 'pointer',
                }}
              >
                <option value="">Select a spec…</option>
                {policies.map(p => (
                  <option key={p.name} value={p.name}>
                    {p.name} ({p.requirement_count} rules)
                  </option>
                ))}
              </select>
            </div>

            {/* run bar */}
            <div style={{
              gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 12,
              paddingTop: 14, borderTop: `1px dashed ${T.line}`,
            }}>
              <div style={{ flex: 1 }}>
                <ScanProgress percent={percent} scanning={scanning} />
              </div>
              {scanning
                ? <Btn mono onClick={onCancel}>cancel</Btn>
                : <Btn mono primary onClick={onRun} disabled={!canRun}>▶ run scan</Btn>
              }
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── App ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [repoUrl, setRepoUrl]         = useState('')
  const [policy, setPolicy]           = useState('')
  const [policies, setPolicies]       = useState([])
  const [selectedModels, setSelected] = useState(AVAILABLE_MODELS)
  const [scanning, setScanning]       = useState(false)
  const [percent, setPercent]         = useState(0)
  const [violations, setViolations]   = useState([])
  const [report, setReport]           = useState(null)
  const [error, setError]             = useState(null)
  const [expandedId, setExpandedId]   = useState(null)
  const [showEval, setShowEval]       = useState(false)
  const [filterSev, setFilterSev]     = useState('all')
  const [search, setSearch]           = useState('')
  const [compact, setCompact]         = useState(false)

  const scrollRef     = useRef(null)
  const savedScroll   = useRef(0)
  const cancelledRef  = useRef(false)

  // load policies on mount
  useEffect(() => {
    fetchPolicies()
      .then(setPolicies)
      .catch(() => {})
  }, [])

  // sticky header scroll detection
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const fn = () => {
      savedScroll.current = el.scrollTop
      setCompact(el.scrollTop > 80)
    }
    el.addEventListener('scroll', fn, { passive: true })
    return () => el.removeEventListener('scroll', fn)
  }, [])

  // restore scroll position after re-renders
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (el && savedScroll.current && el.scrollTop !== savedScroll.current) {
      el.scrollTop = savedScroll.current
    }
  })

  function toggleModel(m) {
    setSelected(s =>
      s.includes(m) ? s.filter(x => x !== m) : [...s, m]
    )
  }

  async function handleRun() {
    if (!repoUrl || !policy || selectedModels.length === 0) return
    cancelledRef.current = false
    setScanning(true)
    setPercent(10)
    setViolations([])
    setReport(null)
    setError(null)
    setExpandedId(null)

    // fake progress ticks while waiting
    const interval = setInterval(() => {
      setPercent(p => Math.min(90, p + Math.floor(Math.random() * 8 + 3)))
    }, 2000)

    try {
      const result = await runAudit({ repoUrl, policy, models: selectedModels })
      clearInterval(interval)
      if (cancelledRef.current) return
      setPercent(100)
      setReport(result)
      setViolations(result.violations || [])
    } catch (err) {
      clearInterval(interval)
      setError(err.message)
    } finally {
      setScanning(false)
    }
  }

  function handleCancel() {
    cancelledRef.current = true
    setScanning(false)
    setPercent(0)
  }

  function handleExport() {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = Object.assign(document.createElement('a'), { href: url, download: 'audittrace-report.json' })
    a.click()
    URL.revokeObjectURL(url)
  }

  const filtered = violations.filter(v => {
    const sev = (v.severity || '').toLowerCase()
    const matchSev = filterSev === 'all' || sev === filterSev ||
      (filterSev === 'high' && sev === 'critical')
    const matchSearch = !search || [v.clause_id, v.clause_text, v.file, v.check_id]
      .some(s => (s || '').toLowerCase().includes(search.toLowerCase()))
    return matchSev && matchSearch
  })

  const counts = {
    high:   violations.filter(v => ['high','critical'].includes((v.severity||'').toLowerCase())).length,
    medium: violations.filter(v => (v.severity||'').toLowerCase() === 'medium').length,
    low:    violations.filter(v => (v.severity||'').toLowerCase() === 'low').length,
  }

  const canRun = !!repoUrl && !!policy && selectedModels.length > 0 && !scanning

  return (
    <div style={{
      width: '100%', height: '100%',
      background: T.paper, fontFamily: T.sans, color: T.ink,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto' }}>
        <Header
          compact={compact}
          repoUrl={repoUrl} setRepoUrl={setRepoUrl}
          policy={policy}   setPolicy={setPolicy}
          policies={policies}
          selectedModels={selectedModels} toggleModel={toggleModel}
          scanning={scanning} percent={percent}
          onRun={handleRun} onCancel={handleCancel}
          canRun={canRun}
        />

        <div style={{ padding: '20px 48px 80px' }}>

          {/* error banner */}
          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 6, marginBottom: 16,
              border: `1px solid ${T.high}44`, background: T.highBg,
              fontFamily: T.mono, fontSize: 12, color: T.high,
            }}>
              {error}
            </div>
          )}

          {/* results header */}
          {(violations.length > 0 || scanning) && (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14,
              }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Findings</div>
                <div style={{ fontFamily: T.mono, fontSize: 11, color: T.mute }}>
                  {violations.length} total
                  {counts.high > 0 && <span style={{ color: T.high }}> · {counts.high} high</span>}
                  {counts.medium > 0 && <span style={{ color: T.med }}> · {counts.medium} med</span>}
                  {counts.low > 0 && <span style={{ color: T.low }}> · {counts.low} low</span>}
                </div>
                {report && (
                  <div style={{ fontFamily: T.mono, fontSize: 11, color: T.mute }}>
                    · compliance score{' '}
                    <span style={{
                      color: report.compliance_score > 80 ? T.low
                           : report.compliance_score > 50 ? T.med : T.high,
                      fontWeight: 600,
                    }}>
                      {report.compliance_score}%
                    </span>
                    {report.version && (
                      <span style={{ color: T.mute }}> · v{report.version}</span>
                    )}
                  </div>
                )}
                <div style={{ flex: 1 }} />

                {/* severity filter pills */}
                <div style={{
                  display: 'flex', gap: 2, fontFamily: T.mono, fontSize: 11,
                  border: `1px solid ${T.line}`, borderRadius: 999,
                  padding: 3, background: T.card,
                }}>
                  {['all', 'high', 'medium', 'low'].map(s => (
                    <span key={s} onClick={() => setFilterSev(s)} style={{
                      padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                      background: filterSev === s ? T.ink : 'transparent',
                      color: filterSev === s ? T.paper : T.mute,
                      transition: 'all 140ms', userSelect: 'none',
                    }}>{s}</span>
                  ))}
                </div>

                <button onClick={() => setShowEval(v => !v)} style={{
                  padding: '7px 12px', borderRadius: 6,
                  border: `1px solid ${showEval ? T.ink : T.line}`,
                  background: showEval ? T.ink : T.card,
                  color: showEval ? T.paper : T.ink,
                  fontFamily: T.mono, fontSize: 11, cursor: 'pointer',
                }}>
                  📊 {showEval ? 'hide eval' : 'show eval'}
                </button>
                <button onClick={handleExport} style={{
                  padding: '7px 12px', borderRadius: 6,
                  border: `1px solid ${T.line}`, background: T.card,
                  color: T.ink, fontFamily: T.mono, fontSize: 11, cursor: 'pointer',
                }}>
                  ↓ export
                </button>
              </div>

              {/* search bar */}
              <div style={{
                flex: 1, border: `1px solid ${T.line}`, borderRadius: 6,
                padding: '8px 12px', background: T.card,
                fontFamily: T.mono, fontSize: 12, color: T.mute,
                marginBottom: 16,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span>⌕</span>
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="filter findings… (file, clause, check ID)"
                  style={{
                    flex: 1, border: 'none', outline: 'none',
                    background: 'transparent', fontFamily: T.mono,
                    fontSize: 12, color: T.ink,
                  }}
                />
              </div>
            </>
          )}

          {/* issue cards — newest on top */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...filtered].reverse().map((v, idx) => {
              const id = `${v.clause_id}|${v.check_id}|${v.file}|${(v.line||[0])[0]}`
              return (
                <IssueCard
                  key={id}
                  violation={v}
                  expanded={expandedId === id}
                  onToggle={() => setExpandedId(expandedId === id ? null : id)}
                  animDelay={idx * 50}
                />
              )
            })}

            {/* scanning shimmer placeholder */}
            {scanning && (
              <div style={{
                border: `1px dashed ${T.line}`, borderRadius: 6, padding: 14,
                background: T.card, display: 'flex', alignItems: 'center', gap: 10,
                fontFamily: T.mono, fontSize: 12, color: T.mute,
                animation: 'shimmer 1.6s infinite',
              }}>
                <span style={{
                  width: 10, height: 10, borderRadius: 999, background: T.med,
                  animation: 'pulse 1s infinite',
                }} />
                analyzing repository · awaiting findings…
              </div>
            )}

            {/* empty state */}
            {!scanning && violations.length === 0 && !error && (
              <div style={{
                padding: '60px 0', textAlign: 'center',
                fontFamily: T.mono, fontSize: 13, color: T.mute,
              }}>
                {report
                  ? '✓ No violations found for the selected spec'
                  : 'Configure a repository and spec above, then run the scan'}
                <div style={{ marginTop: 14 }}>
                  <button onClick={() => setShowEval(v => !v)} style={{
                    padding: '7px 12px', borderRadius: 6,
                    border: `1px solid ${showEval ? T.ink : T.line}`,
                    background: showEval ? T.ink : T.card,
                    color: showEval ? T.paper : T.ink,
                    fontFamily: T.mono, fontSize: 11, cursor: 'pointer',
                  }}>
                    📊 {showEval ? 'hide model evaluation' : 'view model evaluation'}
                  </button>
                </div>
              </div>
            )}
          </div>
          {showEval && (
            <div style={{ marginTop: 32, animation: 'flyUp 400ms ease' }}>
              <EvalPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
