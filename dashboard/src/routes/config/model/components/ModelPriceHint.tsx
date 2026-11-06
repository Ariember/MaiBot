import { findModelPrice, MODEL_PRICE_DATE, MODEL_PRICE_USD_TO_CNY } from '../modelPricing'

export function ModelPriceHint({ identifier }: { identifier: string }) {
  const price = findModelPrice(identifier)
  return (
    <p className="text-muted-foreground text-xs leading-relaxed">
      {price ? (
        <>
          已匹配 {price.vendor} 参考价（{MODEL_PRICE_DATE}）。{price.note}
          {price.currency === 'USD' && `美元按 1 USD ≈ ¥${MODEL_PRICE_USD_TO_CNY} 估算。`}
          <a
            href={price.source}
            target="_blank"
            rel="noreferrer"
            className="ml-1 underline underline-offset-2"
          >
            查看官方价目表
          </a>
        </>
      ) : (
        '未收录的模型默认价格为 0，请填写实际价格。'
      )}{' '}
      手动填写后不会被自动价格覆盖；中转服务请按实际报价调整。
    </p>
  )
}
