import { useEffect, useState } from 'react'
import { T, MODEL_LABELS } from '../tokens'
import { fetchEvalFpFilter, fetchEvalPlanner } from '../api'

const pct  = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`
const num  = v => v == null ? '—' : Number(v).toFixed(2)
const usd  = v => v == null ? '—' : `$${Number(v).toFixed(4)}`
const lbl  = m => MODEL_LABELS[m] || m.split('/').pop()

function colorForPct(v) {
  if (v == null) return T.mute
  if (v >= 0.9) return T.low
  if (v >= 0.75) return T.med
  return T.high
}

function colorForKappa(k) {
  if (k == null) return T.mute
  if (k >= 0.81) return T.low      // "almost perfect" (Landis & Koch)
  if (k >= 0.61) return T.med      // "substantial"
  return T.high                    // "moderate" or worse
}

function SectionHeader({ children, sub }) {
  return (
    <div style={{
      padding: '14px 20px', borderBottom: `1px solid ${T.line}`,
      background: T.paper, display: 'flex', alignItems: 'baseline', gap: 10,
    }}>
      <span style={{ fontSize: 14, fontWeight: 600 }}>{children}</span>
      {sub && (
        <span style={{ fontFamily: T.mono, fontSize: 11, color: T.mute }}>{sub}</span>
      )}
    </div>
  )
}

function StatBlock({ label, value, color, hint }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{
        fontSize: 26, fontWeight: 700, fontFamily: T.mono, letterSpacing: -1,
        color: color || T.ink,
      }}>
        {value}
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, marginTop: 2, letterSpacing: 0.4 }}>
        {label}
      </div>
      {hint && (
        <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, marginTop: 2 }}>
          {hint}
        </div>
      )}
    </div>
  )
}

function Bar({ value, color }) {
  return (
    <div style={{
      flex: 1, height: 5, background: T.line2, borderRadius: 999, overflow: 'hidden',
    }}>
      <div style={{
        width: `${(value || 0) * 100}%`, height: '100%',
        background: color || T.ink, borderRadius: 999,
      }} />
    </div>
  )
}

function FpFilterCard({ data }) {
  if (!data) return null
  const models     = data.models || []
  const byGen      = data.by_model_genuine_cls || {}
  const byFp       = data.by_model_fp_cls      || {}
  const kappa      = data.kappa                || {}
  const byTier     = data.by_tier              || {}
  const tierCounts = data.consensus_tiers      || {}

  const tierOrder  = ['HIGH', 'LIKELY', 'UNCERTAIN', 'LIKELY_FP', 'SUPPRESSED']
  const tierColor  = {
    HIGH: T.high, LIKELY: T.med, UNCERTAIN: T.mute,
    LIKELY_FP: T.med, SUPPRESSED: T.low,
  }

  return (
    <div style={{
      border: `1px solid ${T.line}`, borderRadius: 8, background: T.card, overflow: 'hidden',
    }}>
      <SectionHeader sub={
        `n=${data.dataset_size} · ${data.n_genuine} GENUINE + ${data.n_false_positive} FALSE_POSITIVE · ${models.length} models`
      }>
        FP-Filter Evaluation
      </SectionHeader>

      {/* Headline numbers */}
      <div style={{
        padding: '20px', display: 'flex', gap: 16,
        borderBottom: `1px solid ${T.line2}`,
      }}>
        <StatBlock
          label="OVERALL ACCURACY"
          value={pct(data.overall_accuracy)}
          color={colorForPct(data.overall_accuracy)}
        />
        <StatBlock
          label="FP REDUCTION"
          value={pct(data.fp_reduction_rate)}
          color={colorForPct(data.fp_reduction_rate)}
          hint="true FPs suppressed"
        />
        <StatBlock
          label="TP RETENTION"
          value={pct(data.tp_retention_rate)}
          color={colorForPct(data.tp_retention_rate)}
          hint="true GENUINE kept"
        />
      </div>

      <div style={{
        padding: '20px', display: 'grid',
        gridTemplateColumns: '1fr 1fr', gap: 24,
      }}>

        {/* Per-model GENUINE class */}
        <div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, letterSpacing: 0.8, marginBottom: 12 }}>
            PER-MODEL · GENUINE CLASS
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: T.mono, fontSize: 11 }}>
            <thead>
              <tr style={{ color: T.mute }}>
                {['Model', 'P', 'R', 'F1', 'TP', 'FP', 'FN', 'TN'].map(h => (
                  <th key={h} style={{
                    textAlign: h === 'Model' ? 'left' : 'right',
                    paddingBottom: 8, fontWeight: 500,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.map(m => {
                const s = byGen[m] || {}
                return (
                  <tr key={m} style={{ borderTop: `1px solid ${T.line2}` }}>
                    <td style={{ padding: '7px 0', color: T.ink2 }}>{lbl(m)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.precision) }}>{pct(s.precision)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.recall) }}>{pct(s.recall)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.f1), fontWeight: 600 }}>{pct(s.f1)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: T.mute }}>{s.tp ?? '—'}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: T.mute }}>{s.fp ?? '—'}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: T.mute }}>{s.fn ?? '—'}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: T.mute }}>{s.tn ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Per-model FP-detection class */}
        <div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, letterSpacing: 0.8, marginBottom: 12 }}>
            PER-MODEL · FALSE_POSITIVE CLASS
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: T.mono, fontSize: 11 }}>
            <thead>
              <tr style={{ color: T.mute }}>
                {['Model', 'P', 'R', 'F1'].map(h => (
                  <th key={h} style={{
                    textAlign: h === 'Model' ? 'left' : 'right',
                    paddingBottom: 8, fontWeight: 500,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.map(m => {
                const s = byFp[m] || {}
                return (
                  <tr key={m} style={{ borderTop: `1px solid ${T.line2}` }}>
                    <td style={{ padding: '7px 0', color: T.ink2 }}>{lbl(m)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.precision) }}>{pct(s.precision)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.recall) }}>{pct(s.recall)}</td>
                    <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(s.f1), fontWeight: 600 }}>{pct(s.f1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Cohen's kappa */}
        <div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, letterSpacing: 0.8, marginBottom: 12 }}>
            INTER-MODEL AGREEMENT · COHEN'S KAPPA
          </div>
          {Object.entries(kappa).map(([pair, k]) => (
            <div key={pair} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontFamily: T.mono, fontSize: 11, color: T.ink2 }}>{pair}</span>
                <span style={{
                  fontFamily: T.mono, fontSize: 11, color: colorForKappa(k), fontWeight: 600,
                }}>
                  κ = {num(k)}
                </span>
              </div>
              <Bar value={Math.max(0, k)} color={colorForKappa(k)} />
            </div>
          ))}
          <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, marginTop: 8 }}>
            ≥0.81 almost perfect · ≥0.61 substantial · &lt;0.61 moderate
          </div>
        </div>

        {/* Per-tier precision */}
        <div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, letterSpacing: 0.8, marginBottom: 12 }}>
            CONSENSUS TIERS · DO THEY CARRY SIGNAL?
          </div>
          {tierOrder.map(tier => {
            const t = byTier[tier]
            const c = tierCounts[tier] || 0
            if (!t || !c) return null
            return (
              <div key={tier} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontFamily: T.mono, fontSize: 11, color: T.ink2 }}>
                    {tier} <span style={{ color: T.mute }}>({c} findings)</span>
                  </span>
                  <span style={{ fontFamily: T.mono, fontSize: 11, color: T.mute }}>
                    {t.truly_genuine} genuine · {t.truly_fp} FP
                  </span>
                </div>
                <Bar value={t.genuine_pct} color={tierColor[tier] || T.ink} />
              </div>
            )
          })}
        </div>

      </div>
    </div>
  )
}

function PlannerCard({ data }) {
  if (!data || !data.length) return null
  return (
    <div style={{
      border: `1px solid ${T.line}`, borderRadius: 8, background: T.card,
      overflow: 'hidden', marginTop: 16,
    }}>
      <SectionHeader sub={`n=${data[0]?.n_cases || '—'} test cases · ${data.length} models`}>
        Planner Benchmark
      </SectionHeader>

      <div style={{ padding: 20 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: T.mono, fontSize: 11 }}>
          <thead>
            <tr style={{ color: T.mute }}>
              {['Model', 'Sev Acc', 'Type Acc', 'Targets F1', 'Latency', 'Tokens', 'Cost'].map(h => (
                <th key={h} style={{
                  textAlign: h === 'Model' ? 'left' : 'right',
                  paddingBottom: 8, fontWeight: 500,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map(row => (
              <tr key={row.model} style={{ borderTop: `1px solid ${T.line2}` }}>
                <td style={{ padding: '7px 0', color: T.ink2 }}>{lbl(row.model)}</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(row.severity_accuracy) }}>{pct(row.severity_accuracy)}</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(row.req_type_accuracy) }}>{pct(row.req_type_accuracy)}</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: colorForPct(row.avg_targets_f1) }}>{pct(row.avg_targets_f1)}</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: T.ink2 }}>{num(row.avg_latency_s)}s</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: T.mute }}>{row.total_tokens_est}</td>
                <td style={{ textAlign: 'right', padding: '7px 4px', color: T.ink2 }}>{usd(row.estimated_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ fontFamily: T.mono, fontSize: 10, color: T.mute, marginTop: 10 }}>
          Severity accuracy is intentionally noisy — ground-truth severity is subjective; type acc & targets F1 are the load-bearing metrics.
        </div>
      </div>
    </div>
  )
}

export default function EvalPanel() {
  const [fp,      setFp]      = useState(null)
  const [planner, setPlanner] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [a, b] = await Promise.all([
        fetchEvalFpFilter().catch(e => { throw new Error(`FP-filter: ${e.message}`) }),
        fetchEvalPlanner().catch(e => { throw new Error(`Planner: ${e.message}`) }),
      ])
      setFp(a)
      setPlanner(b)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading && !fp) {
    return (
      <div style={{
        padding: 24, border: `1px dashed ${T.line}`, borderRadius: 8,
        background: T.card, fontFamily: T.mono, fontSize: 12, color: T.mute,
        textAlign: 'center',
      }}>
        loading evaluation results…
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        padding: 14, borderRadius: 6, border: `1px solid ${T.high}44`,
        background: T.highBg, fontFamily: T.mono, fontSize: 12, color: T.high,
      }}>
        {error}
        <div style={{ marginTop: 6, color: T.mute }}>
          Run <code>python evaluation/eval_e2e.py</code> and <code>python evaluation/run_eval.py</code> from <code>backend/</code>, then reload.
        </div>
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Model Evaluation</div>
        <div style={{ fontFamily: T.mono, fontSize: 11, color: T.mute }}>
          how the three LLMs perform on the FP-filter and planner tasks
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={load} disabled={loading} style={{
          padding: '6px 10px', borderRadius: 6,
          border: `1px solid ${T.line}`, background: T.card,
          color: T.ink, fontFamily: T.mono, fontSize: 11,
          cursor: loading ? 'wait' : 'pointer',
        }}>
          {loading ? '⏳' : '↻'} refresh
        </button>
      </div>
      <FpFilterCard data={fp} />
      <PlannerCard  data={planner} />
    </div>
  )
}
