import type { ModelInfo } from './types'

export const MODEL_PRICE_DATE = '2026-11-07'
// shortcut: 美元仅按固定参考汇率折算；需要精确账单时应填写提供商实际人民币价格。
export const MODEL_PRICE_USD_TO_CNY = 7
export const MODEL_PRICE_FIELDS = ['price_in', 'price_out', 'cache_price_in'] as const
export type ModelPriceField = (typeof MODEL_PRICE_FIELDS)[number]
type PriceRow = readonly [id: string, input: number, output: number, cache?: number]

interface PriceGroup {
  vendor: string
  currency: 'CNY' | 'USD'
  source: string
  note: string
  models: readonly PriceRow[]
}

// 标准在线文本价格；阶梯价格取首档，缓存列只含读取价，不含写入、存储和工具费用。
export const MODEL_PRICE_CATALOG: readonly PriceGroup[] = [
  {
    vendor: '智谱 / Z.ai',
    currency: 'USD',
    source: 'https://docs.z.ai/guides/overview/pricing',
    note: 'Z.ai 国际站参考价；国内 BigModel 及中转服务请按实际报价调整。',
    models: [
      ['glm-5.3', 1.4, 4.4, 0.26],
      ['glm-5.3-flash', 0.15, 0.5, 0.03],
      ['glm-5.3-flashx', 0.37, 1.25, 0.075],
      ['glm-5.2', 1.4, 4.4, 0.26],
      ['glm-5.1', 1.4, 4.4, 0.26],
      ['glm-5', 1, 3.2, 0.2],
      ['glm-4.7', 0.6, 2.2, 0.11],
      ['glm-4.6', 0.6, 2.2, 0.11],
      ['glm-4.5', 0.6, 2.2, 0.11],
      ['glm-4.5-air', 0.2, 1.1, 0.03],
      ['glm-4.7-flash', 0, 0, 0],
      ['glm-4.5-flash', 0, 0, 0],
      ['glm-4.6v', 0.3, 0.9, 0.05],
    ],
  },
  {
    vendor: 'DeepSeek',
    currency: 'CNY',
    source: 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
    note: '高峰时段参考价；空闲时段半价，请按实际情况配置分时价格。',
    models: [
      ['deepseek-flash', 2, 8, 0.04],
      ['deepseek-v4-flash', 2, 8, 0.04],
      ['deepseek-v4-flash-vision-exp', 2, 8, 0.04],
      ['deepseek-v4-pro', 9, 27, 0.3],
    ],
  },
  {
    vendor: 'OpenAI',
    currency: 'USD',
    source: 'https://developers.openai.com/api/docs/pricing',
    note: '标准服务、短上下文价格。',
    models: [
      ['gpt-6-astra', 10, 50, 1],
      ['gpt-6.1-sol', 2, 10, 0.1],
      ['gpt-6.1-terra', 1, 5, 0.05],
      ['gpt-6-luna', 0.1, 0.5, 0.01],
      ['gpt-5.3-codex', 1.75, 14, 0.175],
    ],
  },
  {
    vendor: 'OpenAI',
    currency: 'USD',
    source: 'https://developers.openai.com/api/docs/models/gpt-4.1',
    note: 'GPT-4.1 标准文本价格。',
    models: [
      ['gpt-4.1', 2, 8, 0.5],
      ['gpt-4.1-2025-04-14', 2, 8, 0.5],
    ],
  },
  {
    vendor: 'OpenAI',
    currency: 'USD',
    source: 'https://developers.openai.com/api/docs/models/gpt-4o-mini',
    note: 'GPT-4o mini 标准文本价格。',
    models: [
      ['gpt-4o-mini', 0.15, 0.6, 0.075],
      ['gpt-4o-mini-2024-07-18', 0.15, 0.6, 0.075],
    ],
  },
  {
    vendor: 'OpenAI',
    currency: 'USD',
    source: 'https://developers.openai.com/api/docs/models/gpt-5',
    note: 'GPT-5 标准文本价格。',
    models: [['gpt-5', 1.25, 10, 0.125]],
  },
  {
    vendor: 'Anthropic',
    currency: 'USD',
    source: 'https://platform.claude.com/docs/en/about-claude/pricing',
    note: '标准服务、短上下文价格；缓存价格不含缓存写入费。',
    models: [
      ['claude-fable-5-1', 10, 50, 0.25],
      ['claude-opus-5-5', 4, 20, 0.2],
      ['claude-sonnet-5-5', 2, 10, 0.1],
      ['claude-haiku-5-5', 0.1, 0.5, 0.01],
      ['claude-opus-4-6', 5, 25, 0.5],
      ['claude-opus-4-5', 5, 25, 0.5],
      ['claude-opus-4-5-20251101', 5, 25, 0.5],
      ['claude-sonnet-4-6', 3, 15, 0.3],
      ['claude-sonnet-4-5', 3, 15, 0.3],
      ['claude-sonnet-4-5-20250929', 3, 15, 0.3],
      ['claude-haiku-4-5', 1, 5, 0.1],
      ['claude-haiku-4-5-20251001', 1, 5, 0.1],
    ],
  },
  {
    vendor: '通义千问',
    currency: 'CNY',
    source: 'https://help.aliyun.com/zh/model-studio/model-pricing',
    note: '全球部署、首档上下文参考价；缓存折扣请按服务商实际价格填写。',
    models: [
      ['qwen-flash', 0.15, 1.5],
      ['qwen-flash-2025-07-28', 0.15, 1.5],
      ['qwen3.5-flash', 0.2, 2],
      ['qwen3.5-flash-2026-02-23', 0.2, 2],
      ['qwen3.8-flash', 0.8, 2.7],
      ['qwen3.5-plus-2026-02-15', 0.8, 4.8],
    ],
  },
  {
    vendor: 'Google Gemini',
    currency: 'USD',
    source: 'https://ai.google.dev/gemini-api/docs/pricing',
    note: '付费层标准文本价格，不含音频、缓存存储及搜索工具费用。',
    models: [
      ['gemini-2.5-flash', 0.3, 2.5, 0.03],
      ['gemini-2.5-flash-lite', 0.1, 0.4, 0.01],
    ],
  },
  {
    vendor: 'Kimi / Moonshot',
    currency: 'CNY',
    source: 'https://www.kimi.com/resources/kimi-k3-1-pro-pricing',
    note: '国内 API 人民币价格，不含缓存写入费和适用税费。',
    models: [
      ['kimi-k3.1-pro', 13, 68, 1.3],
      ['kimi-k3.1-pro-highspeed', 26, 136, 1.3],
      ['kimi-k3', 20, 100, 2],
    ],
  },
  {
    vendor: 'MiniMax',
    currency: 'USD',
    source: 'https://platform.minimax.io/docs/pricing/overview',
    note: '标准服务、首档上下文价格。',
    models: [
      ['MiniMax-M3.1-Flash', 0.15, 0.6, 0.015],
      ['MiniMax-M3', 0.3, 1.2, 0.06],
    ],
  },
  {
    vendor: '通义千问',
    currency: 'CNY',
    source: 'https://help.aliyun.com/zh/model-studio/model-pricing',
    note: '北京地域文本向量价格，输出不计费。',
    models: [
      ['text-embedding-v4', 0.5, 0],
      ['text-embedding-v3', 0.5, 0],
      ['text-embedding-v2', 0.7, 0],
      ['qwen3.7-text-embedding', 0.5, 0],
      ['qwen3.7-text-embedding-flash', 0.125, 0],
    ],
  },
  {
    vendor: '豆包',
    currency: 'CNY',
    source: 'https://console.volcengine.com/ark/region%3Acn-beijing/docs/model-pricing',
    note: '输入不超过 32K 的参考价；自建推理接入点 ID 需手动填写。',
    models: [['doubao-seed-2.0-pro', 1.6, 8, 0.64]],
  },
]

export function findModelPrice(identifier: string) {
  // 仅移除明确的官方命名空间，不猜测任意中转别名或未知版本的价格。
  const id = identifier
    .trim()
    .toLowerCase()
    .replace(/^(?:models|openai|anthropic|google|deepseek|qwen|minimax)\//, '')
  for (const group of MODEL_PRICE_CATALOG) {
    const row = group.models.find(([modelId]) => modelId.toLowerCase() === id)
    if (!row) continue
    const rate = group.currency === 'USD' ? MODEL_PRICE_USD_TO_CNY : 1
    return {
      vendor: group.vendor,
      source: group.source,
      note: group.note,
      currency: group.currency,
      price_in: Number((row[1] * rate).toFixed(6)),
      price_out: Number((row[2] * rate).toFixed(6)),
      cache_price_in: Number(((row[3] ?? row[1]) * rate).toFixed(6)),
    }
  }
  return undefined
}

export function applyModelPriceDefaults(
  model: ModelInfo,
  touched: ReadonlySet<ModelPriceField>
): ModelInfo {
  const price = findModelPrice(model.model_identifier)
  const result = { ...model }
  for (const field of MODEL_PRICE_FIELDS) {
    if (!touched.has(field)) result[field] = price?.[field] ?? 0
  }
  return result
}
