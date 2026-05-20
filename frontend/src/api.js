const BASE = ''  // proxied by Vite to http://localhost:8000

export async function fetchPolicies() {
  const res = await fetch(`${BASE}/policies`)
  if (!res.ok) throw new Error('Failed to load policies')
  return res.json()
}

export async function fetchHistory(repoUrl) {
  const res = await fetch(`${BASE}/history?repo_url=${encodeURIComponent(repoUrl)}`)
  if (!res.ok) throw new Error('Failed to load history')
  return res.json()
}

export async function runAudit({ repoUrl, policy, models }) {
  const form = new FormData()
  form.append('repo_url', repoUrl)
  form.append('policy', policy)
  if (models && models.length) form.append('models', models.join(','))

  const res = await fetch(`${BASE}/audit`, { method: 'POST', body: form })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Audit failed (${res.status}): ${text}`)
  }
  return res.json()
}

export async function runEvaluate({ repoUrl, violations, models }) {
  const form = new FormData()
  form.append('repo_url', repoUrl)
  form.append('violations', JSON.stringify(violations))
  if (models && models.length) form.append('models', models.join(','))

  const res = await fetch(`${BASE}/evaluate`, { method: 'POST', body: form })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Evaluate failed (${res.status}): ${text}`)
  }
  return res.json()
}

export async function fetchEvalFpFilter() {
  const res = await fetch(`${BASE}/eval/fp-filter`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`FP-filter eval load failed (${res.status}): ${text}`)
  }
  return res.json()
}

export async function fetchEvalPlanner() {
  const res = await fetch(`${BASE}/eval/planner`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Planner eval load failed (${res.status}): ${text}`)
  }
  return res.json()
}

export async function fetchFix({ clauseText, checkId, resource, filePath, model }) {
  const form = new FormData()
  form.append('clause_text', clauseText)
  form.append('check_id', checkId)
  form.append('resource', resource || '')
  form.append('file_path', filePath || '')
  form.append('model', model || 'openai/gpt-4o-mini')

  const res = await fetch(`${BASE}/fix`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Fix generation failed')
  return res.json()
}
