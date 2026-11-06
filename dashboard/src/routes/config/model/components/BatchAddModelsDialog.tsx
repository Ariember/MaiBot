import { useMemo, useState } from 'react'
import { Download, Loader2, Search } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { useModelFetcher } from '../hooks/useModelFetcher'
import {
  applyModelPriceDefaults,
  MODEL_PRICE_DATE,
  MODEL_PRICE_FIELDS,
  MODEL_PRICE_USD_TO_CNY,
} from '../modelPricing'
import type { ModelInfo, ProviderConfig } from '../types'
import { ModelPriceHint } from './ModelPriceHint'

interface BatchAddModelsDialogProps {
  providers: string[]
  models: ModelInfo[]
  initialProvider: string
  getProviderConfig: (name: string) => ProviderConfig | undefined
  onSave: (models: ModelInfo[]) => Promise<boolean>
  onClose: () => void
}

const PRICE_LABELS = { price_in: '输入价格', price_out: '输出价格', cache_price_in: '缓存价格' }

export function BatchAddModelsDialog({
  providers,
  models,
  initialProvider,
  getProviderConfig,
  onSave,
  onClose,
}: BatchAddModelsDialogProps) {
  const [provider, setProvider] = useState(initialProvider)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [edits, setEdits] = useState<Record<string, Partial<ModelInfo>>>({})
  const [visibleCount, setVisibleCount] = useState(50)
  const [requested, setRequested] = useState(false)
  const [saving, setSaving] = useState(false)
  const {
    availableModels,
    fetchingModels,
    modelFetchError,
    matchedTemplate,
    fetchModelsForProvider,
    clearModels,
  } = useModelFetcher({ getProviderConfig })

  const candidates = useMemo(() => {
    const existing = new Set(
      models
        .filter((model) => model.api_provider === provider)
        .map((model) => model.model_identifier.trim())
    )
    const usedNames = new Set(models.map((model) => model.name))
    const seen = new Set<string>()
    return availableModels
      .filter((model) => {
        if (!model.id.trim() || seen.has(model.id)) return false
        seen.add(model.id)
        return true
      })
      .map((model) => {
        let name = model.id
        if (usedNames.has(name)) name = `${model.id} (${provider})`
        const baseName = name
        for (let suffix = 2; usedNames.has(name); suffix += 1) name = `${baseName} ${suffix}`
        usedNames.add(name)
        const draft = applyModelPriceDefaults(
          {
            model_identifier: model.id,
            name,
            api_provider: provider,
            model_type: /embedding|^bge-/i.test(model.id) ? 'embedding' : 'llm',
            price_in: 0,
            price_out: 0,
          },
          new Set()
        )
        return {
          model: { ...draft, ...edits[model.id] },
          exists: existing.has(model.id.trim()),
          displayName: model.name,
        }
      })
  }, [availableModels, edits, models, provider])
  const filtered = candidates.filter(({ model, displayName }) =>
    `${model.model_identifier} ${model.name} ${displayName}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
  )
  const selectable = filtered.filter(({ exists }) => !exists)
  const selectedModels = candidates
    .filter(({ model, exists }) => !exists && selected.has(model.model_identifier))
    .map(({ model }) => model)
  const allSelected =
    selectable.length > 0 && selectable.every(({ model }) => selected.has(model.model_identifier))

  const updateModel = (id: string, change: Partial<ModelInfo>) => {
    setEdits((previous) => ({ ...previous, [id]: { ...previous[id], ...change } }))
  }

  const save = async () => {
    setSaving(true)
    try {
      if (await onSave(selectedModels)) onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose()
      }}
    >
      <DialogContent className="gap-4 p-4 sm:p-6 sm:[--dialog-width:64rem]" preventOutsideClose>
        <DialogHeader>
          <DialogTitle>批量添加模型</DialogTitle>
          <DialogDescription>
            选择提供商并获取模型，勾选后可编辑名称、类型和价格。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="grid gap-2">
            <Label htmlFor="batch-provider">API 提供商</Label>
            <Select
              value={provider}
              disabled={saving}
              onValueChange={(value) => {
                clearModels()
                setProvider(value)
                setSelected(new Set())
                setEdits({})
                setSearch('')
                setVisibleCount(50)
                setRequested(false)
              }}
            >
              <SelectTrigger id="batch-provider">
                <SelectValue placeholder="选择提供商" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((name) => (
                  <SelectItem key={name} value={name}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            disabled={!provider || fetchingModels || saving}
            onClick={() => {
              setRequested(true)
              void fetchModelsForProvider(provider, true)
            }}
          >
            {fetchingModels ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {fetchingModels ? '正在获取' : '获取上游模型'}
          </Button>
        </div>
        <div className="bg-muted/30 text-muted-foreground rounded-lg border p-3 text-xs leading-relaxed">
          价格单位：¥ / 百万 token。内置参考价更新于 {MODEL_PRICE_DATE}，美元按 1 USD ≈ ¥
          {MODEL_PRICE_USD_TO_CNY} 估算。 未收录模型填
          0；手动修改的价格会保留。请核对模型类型与提供商实际报价。
        </div>
        {modelFetchError && (
          <Alert variant="destructive">
            <AlertDescription>{modelFetchError}</AlertDescription>
          </Alert>
        )}
        {availableModels.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-full min-w-0 sm:w-auto sm:flex-1">
              <Search className="text-muted-foreground absolute top-2.5 left-3 h-4 w-4" />
              <Input
                aria-label="搜索上游模型"
                placeholder="搜索模型名称或标识符"
                className="pl-9"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setVisibleCount(50)
                }}
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={saving || selectable.length === 0}
              onClick={() =>
                setSelected((previous) => {
                  const next = new Set(previous)
                  for (const { model } of selectable) {
                    if (allSelected) next.delete(model.model_identifier)
                    else next.add(model.model_identifier)
                  }
                  return next
                })
              }
            >
              {allSelected ? '取消全选' : '全选搜索结果'} ({selectable.length})
            </Button>
            <span className="text-muted-foreground text-xs">
              已存在 {candidates.filter(({ exists }) => exists).length} 个
            </span>
          </div>
        )}
        <DialogBody viewportClassName="min-h-0 flex-1 [&>div]:!block">
          <div className="space-y-3 py-1">
            {filtered.slice(0, visibleCount).map(({ model, exists }) => {
              const checked = !exists && selected.has(model.model_identifier)
              return (
                <section
                  key={model.model_identifier}
                  className={`rounded-lg border p-3 ${checked ? 'border-primary/50 bg-primary/5' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    <Checkbox
                      aria-label={`选择 ${model.model_identifier}`}
                      checked={checked}
                      disabled={exists || saving}
                      onCheckedChange={(value) =>
                        setSelected((previous) => {
                          const next = new Set(previous)
                          if (value === true) next.add(model.model_identifier)
                          else next.delete(model.model_identifier)
                          return next
                        })
                      }
                    />
                    <span className="min-w-0 flex-1 text-sm font-medium break-all">
                      {model.model_identifier}
                    </span>
                    {exists && (
                      <Badge variant="secondary" className="shrink-0">
                        已添加
                      </Badge>
                    )}
                  </div>
                  {checked && (
                    <div className="mt-4 space-y-3 sm:pl-7">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label
                          htmlFor={`batch-name-${model.model_identifier}`}
                          className="grid gap-1.5 text-xs"
                        >
                          模型名称
                          <Input
                            id={`batch-name-${model.model_identifier}`}
                            aria-label={`${model.model_identifier} 模型名称`}
                            value={model.name}
                            disabled={saving}
                            onChange={(event) =>
                              updateModel(model.model_identifier, { name: event.target.value })
                            }
                          />
                        </label>
                        <div className="grid gap-1.5">
                          <span className="text-xs">模型类型</span>
                          <Select
                            value={model.model_type}
                            disabled={saving}
                            onValueChange={(value) =>
                              updateModel(model.model_identifier, {
                                model_type: value as ModelInfo['model_type'],
                              })
                            }
                          >
                            <SelectTrigger aria-label={`${model.model_identifier} 模型类型`}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="llm">LLM 模型</SelectItem>
                              <SelectItem value="embedding">文本嵌入模型</SelectItem>
                              <SelectItem value="image_embedding">图片嵌入模型</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2 sm:gap-3">
                        {MODEL_PRICE_FIELDS.map((field) => (
                          <label
                            key={field}
                            htmlFor={`batch-${field}-${model.model_identifier}`}
                            className="grid gap-1.5 text-xs"
                          >
                            {PRICE_LABELS[field]}
                            <Input
                              id={`batch-${field}-${model.model_identifier}`}
                              aria-label={`${model.model_identifier} ${PRICE_LABELS[field]}`}
                              type="number"
                              min="0"
                              step="any"
                              disabled={saving}
                              value={model[field] ?? ''}
                              onChange={(event) =>
                                updateModel(model.model_identifier, {
                                  [field]:
                                    event.target.value === '' ? null : Number(event.target.value),
                                })
                              }
                            />
                          </label>
                        ))}
                      </div>
                      <ModelPriceHint identifier={model.model_identifier} />
                    </div>
                  )}
                </section>
              )
            })}
            {filtered.length > visibleCount && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setVisibleCount((count) => count + 50)}
              >
                显示更多（还有 {filtered.length - visibleCount} 个）
              </Button>
            )}
            {filtered.length === 0 && !modelFetchError && (
              <p role="status" className="text-muted-foreground py-10 text-center text-sm">
                {fetchingModels
                  ? '正在获取上游模型…'
                  : !providers.length
                    ? '请先添加并保存 API 提供商。'
                    : !requested
                      ? '点击“获取上游模型”开始选择。'
                      : !matchedTemplate?.modelFetcher
                        ? '该提供商暂不支持获取模型列表，请使用单个添加。'
                        : availableModels.length > 0
                          ? '没有匹配的模型。'
                          : '上游未返回可用模型，可重试或使用单个添加。'}
              </p>
            )}
          </div>
        </DialogBody>
        <DialogFooter className="grid grid-cols-2 items-center gap-2 sm:flex">
          <span className="text-muted-foreground col-span-2 mr-auto text-sm" aria-live="polite">
            已选择 {selectedModels.length} 个模型
          </span>
          <Button variant="outline" disabled={saving} onClick={onClose}>
            取消
          </Button>
          <Button
            disabled={saving || fetchingModels || selectedModels.length === 0}
            onClick={() => void save()}
          >
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}添加所选模型 (
            {selectedModels.length})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
