export const T = {
  ink:    '#0f1115',
  ink2:   '#3b3f47',
  mute:   '#6b7280',
  line:   '#d8d8d6',
  line2:  '#ebebe8',
  paper:  '#fafaf7',
  card:   '#ffffff',
  hatch:  '#f1f1ee',
  high:   '#d64545',
  med:    '#d9a441',
  low:    '#5a9e6f',
  highBg: '#fbecec',
  medBg:  '#faf3e2',
  lowBg:  '#ecf3ee',
  mono:   "'JetBrains Mono', ui-monospace, Menlo, monospace",
  sans:   "'Inter', system-ui, -apple-system, sans-serif",
}

export const AVAILABLE_MODELS = [
  'openai/gpt-4o-mini',
  'deepseek/deepseek-chat',
  'meta-llama/llama-3.1-70b-instruct',
]

export const MODEL_LABELS = {
  'openai/gpt-4o-mini':                 'GPT-4o mini',
  'openai/gpt-4o':                      'GPT-4o',
  'deepseek/deepseek-chat':             'DeepSeek V3',
  'meta-llama/llama-3.1-70b-instruct':  'Llama 3.1 70B',
}

export const SEV_COLOR = { high: '#d64545', medium: '#d9a441', low: '#5a9e6f', critical: '#d64545' }
export const SEV_BG    = { high: '#fbecec', medium: '#faf3e2', low: '#ecf3ee', critical: '#fbecec' }
export const SEV_LABEL = { high: 'HIGH', medium: 'MED', low: 'LOW', critical: 'CRIT' }
