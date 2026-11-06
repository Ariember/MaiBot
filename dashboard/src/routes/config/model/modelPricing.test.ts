import { describe, expect, it } from 'vitest'

import {
  applyModelPriceDefaults,
  findModelPrice,
  MODEL_PRICE_CATALOG,
  MODEL_PRICE_FIELDS,
} from './modelPricing'
import type { ModelInfo } from './types'

const draft: ModelInfo = {
  model_type: 'llm',
  model_identifier: 'deepseek-flash',
  name: 'test',
  api_provider: 'test',
  price_in: 0,
  price_out: 0,
  cache_price_in: 0,
}

describe('内置模型参考价', () => {
  it('匹配大小写、空格及官方命名空间，美元统一换算为人民币', () => {
    expect(findModelPrice(' DeepSeek/DEEPSEEK-FLASH ')).toMatchObject({
      price_in: 2,
      price_out: 8,
      cache_price_in: 0.04,
    })
    expect(findModelPrice('openai/gpt-6.1-sol')).toMatchObject({
      price_in: 14,
      price_out: 70,
      cache_price_in: 0.7,
    })
    expect(findModelPrice('MiniMax-M3')).toMatchObject({
      price_in: 2.1,
      price_out: 8.4,
      cache_price_in: 0.42,
    })
  })

  it('未知模型不模糊匹配，所有未手动填写的价格归零', () => {
    for (const id of ['', 'unknown', 'deepseek-flash-custom', 'proxy/deepseek-flash']) {
      expect(findModelPrice(id)).toBeUndefined()
      expect(
        applyModelPriceDefaults({ ...draft, model_identifier: id, price_in: 99 }, new Set())
      ).toMatchObject({ price_in: 0, price_out: 0, cache_price_in: 0 })
    }
  })

  it('按字段保留用户填写，包括 0 和主动清空，不改变原对象', () => {
    const edited = { ...draft, price_in: 0, cache_price_in: null }
    expect(applyModelPriceDefaults(edited, new Set(['price_in', 'cache_price_in']))).toMatchObject({
      price_in: 0,
      price_out: 8,
      cache_price_in: null,
    })
    expect(edited).toEqual({ ...draft, price_in: 0, cache_price_in: null })
    expect(applyModelPriceDefaults(draft, new Set(MODEL_PRICE_FIELDS))).toEqual(draft)
  })

  it('价目表 ID 唯一、来源明确且价格为有限非负数', () => {
    const ids = new Set<string>()
    for (const group of MODEL_PRICE_CATALOG) {
      expect(group.source).toMatch(/^https:\/\//)
      for (const [id, ...prices] of group.models) {
        expect(ids.has(id.toLowerCase())).toBe(false)
        ids.add(id.toLowerCase())
        for (const price of prices) expect(Number.isFinite(price) && price! >= 0).toBe(true)
        expect(findModelPrice(id)).toBeDefined()
      }
    }
  })
})
