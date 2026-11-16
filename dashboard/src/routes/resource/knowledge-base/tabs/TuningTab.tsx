import { useMemo, useState } from 'react'

import { ChevronRight, FileText, ListTree, MoreHorizontal, Sparkles } from 'lucide-react'


import { CodeEditor } from '@/components/CodeEditor'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TabsContent } from '@/components/ui/tabs'

import type { UseMemoryTuningResult } from '../hooks/useMemoryTuning'
import { formatImportTime, getImportStatusVariant } from '../utils'

const MEMORY_TUNING_PARAMETERS_LABELS: Record<string, string> = {
  "retrieval_top_k": "初步查找数量",
  "retrieval_top_k_paragraphs": "段落查找数量",
  "retrieval_top_k_relations": "关系查找数量",
  "retrieval_top_k_final": "最终展示数量",
  "retrieval_alpha": "段落和关系侧重",
  "retrieval_enable_ppr": "关系图辅助排序",
  "retrieval_ppr_alpha": "关系图扩展强度",
  "retrieval_ppr_timeout_seconds": "关系图处理上限",
  "retrieval_search_smart_fallback_enabled": "找不到时自动补查",
  "retrieval_sparse_enabled": "关键词查找",
  "retrieval_sparse_mode": "关键词查找方式",
  "retrieval_sparse_candidate_k": "关键词段落查找数量",
  "retrieval_sparse_relation_candidate_k": "关键词关系查找数量",
  "retrieval_fusion_method": "结果合并方式",
  "retrieval_fusion_rrf_k": "结果合并稳定度",
  "retrieval_fusion_vector_weight": "语义查找侧重",
  "retrieval_fusion_bm25_weight": "关键词查找侧重",
  "retrieval_vector_pools_mode": "语义搜索方式",
  "retrieval_vector_pools_paragraph_top_k": "段落语义查找数量",
  "retrieval_vector_pools_graph_top_k": "关系图语义查找数量",
  "retrieval_vector_pools_graph_expand_paragraph_k": "关系图补充段落数",
  "retrieval_vector_pools_relation_expand_per_hit": "每次命中补充关系数",
  "retrieval_vector_pools_entity_expand_per_hit": "每次命中补充实体数",
  "retrieval_vector_pools_relation_evidence_weight": "关系证据侧重",
  "retrieval_vector_pools_entity_evidence_weight": "实体证据侧重",
  "threshold_percentile": "自动筛选强度",
  "threshold_min_results": "最少展示数量",
  "threshold_min_threshold": "最低筛选线",
  "threshold_max_threshold": "最高筛选线",
}

const MEMORY_TUNING_STATUS_LABELS: Record<string, string> = {
  "completed": "已完成",
  "running": "运行中",
  "queued": "排队中",
  "failed": "失败",
  "cancelled": "已取消",
}


export interface TuningTabProps {
  tuning: UseMemoryTuningResult
}

type SnapshotViewMode = 'summary' | 'toml'

interface SnapshotEntry {
  path: string
  rawValue: unknown
}

interface SnapshotDiffEntry {
  path: string
  label: string
  runtime: string
  persistable: string
}

interface ReadableSnapshotEntry {
  path: string
  label: string
  value: string
}

interface TuningEvaluationSummary {
  baselineScore?: number
  bestScore?: number
  scoreDelta?: number
  holdoutCaseCount?: number
  reason: string
  recommended: boolean
  hasEvaluation: boolean
  baselineMetrics: Record<string, unknown>
  bestMetrics: Record<string, unknown>
  deltas: Record<string, unknown>
}

const PARAMETER_ORDER = [
  'retrieval.top_k',
  'retrieval.top_k_paragraphs',
  'retrieval.top_k_relations',
  'retrieval.top_k_final',
  'retrieval.alpha',
  'retrieval.enable_ppr',
  'retrieval.ppr_alpha',
  'retrieval.ppr_timeout_seconds',
  'retrieval.search.smart_fallback.enabled',
  'retrieval.sparse.enabled',
  'retrieval.sparse.mode',
  'retrieval.sparse.candidate_k',
  'retrieval.sparse.relation_candidate_k',
  'retrieval.fusion.method',
  'retrieval.fusion.rrf_k',
  'retrieval.fusion.vector_weight',
  'retrieval.fusion.bm25_weight',
  'retrieval.vector_pools.mode',
  'retrieval.vector_pools.paragraph_top_k',
  'retrieval.vector_pools.graph_top_k',
  'retrieval.vector_pools.graph_expand_paragraph_k',
  'retrieval.vector_pools.relation_expand_per_hit',
  'retrieval.vector_pools.entity_expand_per_hit',
  'retrieval.vector_pools.relation_evidence_weight',
  'retrieval.vector_pools.entity_evidence_weight',
  'threshold.percentile',
  'threshold.min_results',
  'threshold.min_threshold',
  'threshold.max_threshold',
]

const RESULT_METRICS = [
  { key: 'precision_at_1', label: "首条命中率", format: 'percent' },
  { key: 'hit_at_k', label: "前 K 条命中率", format: 'percent' },
  { key: 'empty_rate', label: "无结果比例", format: 'percent' },
  { key: 'avg_elapsed_ms', label: "平均响应时间", format: 'ms' },
] as const

const PARAMETER_KEYS = Object.fromEntries(
  PARAMETER_ORDER.map((path) => [path, path.replaceAll('.', '_')]),
) as Record<string, string>

const VALUE_LABELS: Record<string, Record<string, string>> = {
  'retrieval.sparse.mode': {
    auto: "自动",
    always: "始终启用",
    off: "关闭",
  },
  'retrieval.fusion.method': {
    weighted_rrf: "综合排序",
    rrf: "排序整合",
    alpha_legacy: "旧版综合排序",
  },
  'retrieval.vector_pools.mode': {
    single: "单路语义搜索",
    dual: "双路语义搜索",
  },
}

const TUNING_REASON_LABELS: Record<string, string> = {
  holdout_empty: "独立样本不足，无法验证调优结果。",
  holdout_online_like_validation_failed: "独立样本和实际搜索效果验证未通过。",
}

function formatSnapshotValue(
  value: unknown,
  path?: string,
): string {
  if (value === null) {
    return 'null'
  }
  if (value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? '启用' : '关闭'
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : '-'
  }
  if (typeof value === 'string') {
    const valueLabel = path ? VALUE_LABELS[path]?.[value] : undefined
    if (valueLabel) {
      return valueLabel
    }
    return value || '""'
  }
  return JSON.stringify(value)
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function numberFrom(value: unknown): number | undefined {
  const numberValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numberValue) ? numberValue : undefined
}

function formatResultValue(value: number | undefined, format: 'number' | 'percent' | 'ms'): string {
  if (value === undefined) {
    return '-'
  }
  if (format === 'percent') {
    return `${(value * 100).toFixed(1)}%`
  }
  if (format === 'ms') {
    return `${value.toFixed(0)} ms`
  }
  return value.toFixed(3)
}

function formatTuningReason(
  reason: string,
): string {
  const normalized = reason.trim()
  if (!normalized) {
    return ''
  }

  const reasonLabel = TUNING_REASON_LABELS[normalized]
  if (reasonLabel) {
    return reasonLabel
  }
  return `${normalized}`
}

function formatResultDelta(value: number | undefined, format: 'number' | 'percent' | 'ms'): string {
  if (value === undefined) {
    return ''
  }
  const prefix = value > 0 ? '+' : ''
  if (format === 'percent') {
    return `${prefix}${(value * 100).toFixed(1)}%`
  }
  if (format === 'ms') {
    return `${prefix}${value.toFixed(0)} ms`
  }
  return `${prefix}${value.toFixed(3)}`
}

function isTuningTaskRecommended(task: Record<string, unknown>): boolean {
  const validation = asRecord(task.validation_summary)
  return validation.recommended === true || task.recommended === true
}

function getTuningEvaluationSummary(task: Record<string, unknown> | undefined): TuningEvaluationSummary | null {
  if (!task) {
    return null
  }

  const validation = asRecord(task.validation_summary)
  const onlineLike = asRecord(validation.online_like)
  const stable = asRecord(validation.stable)
  const evaluationMode = Object.keys(onlineLike).length > 0 ? onlineLike : stable
  const baselineEval = asRecord(evaluationMode.baseline)
  const bestEval = asRecord(evaluationMode.best)
  const baselineMetrics = asRecord(baselineEval.metrics)
  const bestMetrics = asRecord(bestEval.metrics)
  const deltas = asRecord(validation.deltas)
  const baselineScore = numberFrom(baselineEval.score)
  const bestScore = numberFrom(bestEval.score) ?? numberFrom(task.best_score)
  const directScoreDelta = numberFrom(deltas.score)
  const scoreDelta = directScoreDelta ?? (
    baselineScore !== undefined && bestScore !== undefined ? bestScore - baselineScore : undefined
  )
  const holdoutCaseCount = numberFrom(validation.holdout_case_count)
  const recommended = isTuningTaskRecommended(task)
  const hasEvaluation = baselineScore !== undefined
    || bestScore !== undefined
    || Object.keys(baselineMetrics).length > 0
    || Object.keys(bestMetrics).length > 0
    || Object.keys(deltas).length > 0

  return {
    baselineScore,
    bestScore,
    scoreDelta,
    holdoutCaseCount,
    reason: String(validation.reason ?? task.error ?? ''),
    recommended,
    hasEvaluation,
    baselineMetrics,
    bestMetrics,
    deltas,
  }
}

function collectSnapshotEntries(value: unknown, prefix = ''): SnapshotEntry[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return prefix ? [{ path: prefix, rawValue: value }] : []
  }

  return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => {
    const nextPath = prefix ? `${prefix}.${key}` : key
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return collectSnapshotEntries(item, nextPath)
    }
    return [{ path: nextPath, rawValue: item }]
  })
}

function buildReadableSnapshotEntries(
  entries: SnapshotEntry[],
): { readableEntries: ReadableSnapshotEntry[], technicalCount: number } {
  const entryMap = new Map(entries.map((entry) => [entry.path, entry.rawValue]))
  const readableEntries = PARAMETER_ORDER
    .filter((path) => entryMap.has(path))
    .map((path) => ({
      path,
      label: MEMORY_TUNING_PARAMETERS_LABELS[PARAMETER_KEYS[path]],
      value: formatSnapshotValue(entryMap.get(path), path),
    }))
  const technicalCount = entries.filter((entry) => !PARAMETER_KEYS[entry.path]).length

  return { readableEntries, technicalCount }
}

function buildSnapshotDiff(
  runtimeEntries: SnapshotEntry[],
  persistableEntries: SnapshotEntry[],
): { readableDiffs: SnapshotDiffEntry[], technicalDiffCount: number } {
  const runtimeMap = new Map(runtimeEntries.map((entry) => [entry.path, entry.rawValue]))
  const persistableMap = new Map(persistableEntries.map((entry) => [entry.path, entry.rawValue]))
  const allPaths = Array.from(new Set([...runtimeMap.keys(), ...persistableMap.keys()])).sort()
  const diffPaths = allPaths.filter((path) => {
    const runtimeValue = formatSnapshotValue(runtimeMap.get(path), path)
    const persistableValue = formatSnapshotValue(persistableMap.get(path), path)
    return runtimeValue !== persistableValue
  })
  const readableDiffs = diffPaths
    .filter((path) => PARAMETER_KEYS[path])
    .map((path) => ({
      path,
      label: MEMORY_TUNING_PARAMETERS_LABELS[PARAMETER_KEYS[path]],
      runtime: formatSnapshotValue(runtimeMap.get(path), path),
      persistable: formatSnapshotValue(persistableMap.get(path), path),
    }))
  const technicalDiffCount = diffPaths.length - readableDiffs.length

  return { readableDiffs, technicalDiffCount }
}

function SnapshotSummarySection({
  title,
  description,
  entries,
  technicalCount,
  technicalNote,
  emptyText,
}: {
  title: string
  description: string
  entries: ReadableSnapshotEntry[]
  technicalCount: number
  technicalNote: string
  emptyText: string
}) {
  return (
    <section className="space-y-3 rounded-md border bg-muted/15 p-4">
      <div>
        <div className="text-sm font-medium">{title}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      {entries.length > 0 ? (
        <div className="grid gap-2 md:grid-cols-2">
          {entries.map((entry) => (
            <div key={entry.path} className="min-w-0 rounded-md border bg-background px-3 py-2">
              <div className="text-xs leading-5 text-muted-foreground">{entry.label}</div>
              <div className="break-all text-sm leading-6">{entry.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">{emptyText}</div>
      )}
      {technicalCount > 0 ? (
        <div className="rounded-md border border-dashed bg-background/60 p-3 text-xs text-muted-foreground">
          {technicalNote}
        </div>
      ) : null}
    </section>
  )
}

function SnapshotResultCard({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="min-w-0 rounded-md border bg-muted/15 p-4">
      <div className="text-sm font-medium">{title}</div>
      <div className="mt-2 text-sm leading-6 text-muted-foreground">{description}</div>
    </div>
  )
}

function TuningResultMetricRow({
  label,
  baseline,
  best,
  delta,
  format,
}: {
  label: string
  baseline?: number
  best?: number
  delta?: number
  format: 'percent' | 'ms'
}) {
  return (
    <div className="grid gap-2 rounded-md border bg-background px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto]">
      <div className="text-sm font-medium">{label}</div>
      <div className="text-sm leading-6 text-muted-foreground sm:text-right">
        {formatResultValue(baseline, format)}
        <span className="mx-1.5">→</span>
        {formatResultValue(best, format)}
        {delta !== undefined ? (
          <span className="ml-2 text-xs">Δ {formatResultDelta(delta, format)}</span>
        ) : null}
      </div>
    </div>
  )
}

function TuningResultOverview({
  task,
}: {
  task?: Record<string, unknown>
}) {
  if (!task) {
    return (
      <section className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
        {'暂无调优结果。创建并完成任务后，这里会显示评估结果。'}
      </section>
    )
  }

  const status = String(task.status ?? '-')
  const statusLabel = (MEMORY_TUNING_STATUS_LABELS[status] ?? status)
  const reasonText = formatTuningReason(String(task.error ?? ''))
  const evaluation = getTuningEvaluationSummary(task)
  const isCompleted = status === 'completed'
  const progress = numberFrom(task.progress)
  const roundsDone = numberFrom(task.rounds_done)
  const roundsTotal = numberFrom(task.rounds_total)

  if (!isCompleted || !evaluation?.hasEvaluation) {
    return (
      <section className="space-y-3">
        <div className="grid gap-3 md:grid-cols-3">
          <SnapshotResultCard
            title={'任务状态'}
            description={statusLabel}
          />
          <SnapshotResultCard
            title={'任务进度'}
            description={progress !== undefined ? `${Math.round(progress)}%` : '-'}
          />
          <SnapshotResultCard
            title={'已尝试次数'}
            description={roundsDone !== undefined && roundsTotal !== undefined ? `${roundsDone}/${roundsTotal}` : '-'}
          />
        </div>
        {reasonText ? (
          <div className="rounded-md border border-dashed bg-background/60 p-3 text-xs text-muted-foreground">
            {`失败原因：${reasonText}`}
          </div>
        ) : null}
      </section>
    )
  }

  const scoreText = evaluation.baselineScore !== undefined || evaluation.bestScore !== undefined
    ? `${formatResultValue(evaluation.baselineScore, 'number')} → ${formatResultValue(evaluation.bestScore, 'number')}${evaluation.scoreDelta !== undefined ? ` · Δ ${formatResultDelta(evaluation.scoreDelta, 'number')}` : ''}`
    : '-'
  const validationText = evaluation.holdoutCaseCount !== undefined
    ? `${evaluation.recommended ? '通过' : '未通过'}，${evaluation.holdoutCaseCount} 个样本`
    : evaluation.recommended ? '通过' : '未通过'
  const metricRows = RESULT_METRICS.map((metric) => {
    const baseline = numberFrom(evaluation.baselineMetrics[metric.key])
    const best = numberFrom(evaluation.bestMetrics[metric.key])
    const delta = numberFrom(evaluation.deltas[metric.key]) ?? (
      baseline !== undefined && best !== undefined ? best - baseline : undefined
    )
    return { ...metric, baseline, best, delta }
  }).filter((metric) => metric.baseline !== undefined || metric.best !== undefined || metric.delta !== undefined)

  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <SnapshotResultCard
          title={'应用建议'}
          description={evaluation.recommended ? '验证通过，建议应用。' : '验证未通过，不建议应用。'}
        />
        <SnapshotResultCard
          title={'综合评分'}
          description={scoreText}
        />
        <SnapshotResultCard
          title={'独立样本验证'}
          description={validationText}
        />
      </div>
      {metricRows.length > 0 ? (
        <div className="space-y-2 rounded-md border bg-muted/15 p-4">
          <div>
            <div className="text-sm font-medium">{'关键结果'}</div>
            <div className="text-xs text-muted-foreground">{'展示调优前后的效果变化。'}</div>
          </div>
          <div className="grid gap-2 xl:grid-cols-2">
            {metricRows.map((metric) => (
              <TuningResultMetricRow
                key={metric.key}
                label={metric.label}
                baseline={metric.baseline}
                best={metric.best}
                delta={metric.delta}
                format={metric.format}
              />
            ))}
          </div>
        </div>
      ) : null}
      {!evaluation.recommended && evaluation.reason ? (
        <div className="rounded-md border border-dashed bg-background/60 p-3 text-xs text-muted-foreground">
          {`原因：${formatTuningReason(evaluation.reason)}`}
        </div>
      ) : null}
    </section>
  )
}

function TuningTaskListCard({
  tasks,
  applyBestTask,
}: {
  tasks: UseMemoryTuningResult['tuningTasks']
  applyBestTask: UseMemoryTuningResult['applyBestTask']
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{'最近调优记录'}</CardTitle>
        <CardDescription>{'每次调优的执行结果'}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {tasks.length > 0 ? (
          <div className="space-y-2" role="list">
            {tasks.map((task, index) => {
              const taskId = String(task.task_id ?? '')
              const status = String(task.status ?? '-')
              const recommended = isTuningTaskRecommended(task)
              const canApply = Boolean(task.task_id) && status === 'completed' && recommended
              const statusLabel = (MEMORY_TUNING_STATUS_LABELS[status] ?? status)
              return (
                <div
                  key={taskId || `tuning-task-${index}`}
                  className="space-y-3 rounded-md border bg-muted/20 p-3 transition-colors hover:bg-muted/30"
                  role="listitem"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="break-all font-mono text-xs leading-5">{taskId || '-'}</div>
                      <div className="text-xs text-muted-foreground">
                        {formatImportTime(Number(task.updated_at ?? task.created_at ?? 0))}
                      </div>
                    </div>
                    <Badge variant={getImportStatusVariant(status)}>{statusLabel}</Badge>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <Badge variant={recommended ? 'secondary' : 'outline'}>
                      {recommended ? '推荐' : '不建议应用'}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void applyBestTask(taskId)}
                      disabled={!canApply}
                    >
                      {'应用推荐结果'}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
            {'暂无调优记录'}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function TuningTab({ tuning }: TuningTabProps) {
  const {
    tuningObjective,
    setTuningObjective,
    tuningIntensity,
    setTuningIntensity,
    tuningSampleSize,
    setTuningSampleSize,
    tuningTopKEval,
    setTuningTopKEval,
    persistBestProfile,
    setPersistBestProfile,
    submitTuningTask,
    creatingTuning,
    tuningProfile,
    tuningProfileToml,
    tuningTasks,
    applyBestTask,
  } = tuning
  const [snapshotViewMode, setSnapshotViewMode] = useState<SnapshotViewMode>('summary')
  const runtimeEntries = useMemo(() => collectSnapshotEntries(tuningProfile.runtime), [tuningProfile.runtime])
  const persistableEntries = useMemo(() => collectSnapshotEntries(tuningProfile.persistable), [tuningProfile.persistable])
  const { readableEntries: readableRuntimeEntries, technicalCount: runtimeTechnicalCount } = useMemo(
    () => buildReadableSnapshotEntries(runtimeEntries),
    [runtimeEntries],
  )
  const { readableEntries: readablePersistableEntries, technicalCount: persistableTechnicalCount } = useMemo(
    () => buildReadableSnapshotEntries(persistableEntries),
    [persistableEntries],
  )
  const { readableDiffs, technicalDiffCount } = useMemo(
    () => buildSnapshotDiff(runtimeEntries, persistableEntries),
    [persistableEntries, runtimeEntries],
  )
  const resultTask = useMemo(
    () => tuningTasks.find((task) => String(task.status ?? '') === 'completed') ?? tuningTasks[0],
    [tuningTasks],
  )
  const runtimeResultText = runtimeEntries.length > 0
    ? '调优结果已经用于当前记忆搜索。'
    : '暂时没有正在使用的结果。'
  const persistableResultText = persistableEntries.length > 0
    ? '这组结果可按需保存为默认设置。'
    : '暂时没有可保存结果。'
  const hasConfigDiff = readableDiffs.length + technicalDiffCount > 0
  const diffResultText = hasConfigDiff
    ? '当前使用的设置与可保存设置存在差异，展开详情可查看。'
    : '当前使用的设置与可保存设置一致。'
  const isSummaryView = snapshotViewMode === 'summary'
  const toggleSnapshotView = () => setSnapshotViewMode(isSummaryView ? 'toml' : 'summary')
  const SnapshotToggleIcon = isSummaryView ? FileText : ListTree

  return (
    <TabsContent value="tuning" className="space-y-4">
      <div className="grid items-start gap-4 xl:grid-cols-[360px_minmax(0,1fr)] 2xl:grid-cols-[400px_minmax(0,1fr)]">
        <div className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                {'记忆搜索调优'}
              </CardTitle>
              <CardDescription>{'评估并改善记忆搜索效果'}</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-2">
              <Button className="min-w-0 flex-1" onClick={() => void submitTuningTask()} disabled={creatingTuning}>
                <Sparkles className="mr-2 h-4 w-4" />
                {'开始调优'}
              </Button>
              <Dialog>
                <DialogTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="shrink-0"
                    aria-label={'调优参数'}
                    title={'调优参数'}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
                  <DialogHeader>
                    <DialogTitle>{'调优参数'}</DialogTitle>
                    <DialogDescription>{'这些设置只影响下一次调优任务，一般保持默认即可。'}</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-5">
                    <section className="space-y-3">
                      <div className="text-sm font-medium">{'调优策略'}</div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="tuning-objective">{'优化目标'}</Label>
                          <Select value={tuningObjective} onValueChange={setTuningObjective}>
                            <SelectTrigger id="tuning-objective"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="precision_priority">{'优先准确率'}</SelectItem>
                              <SelectItem value="balanced">{'准确率与召回平衡'}</SelectItem>
                              <SelectItem value="recall_priority">{'优先召回率'}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="tuning-intensity">{'评估强度'}</Label>
                          <Select value={tuningIntensity} onValueChange={setTuningIntensity}>
                            <SelectTrigger id="tuning-intensity"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="quick">{'快速'}</SelectItem>
                              <SelectItem value="standard">{'标准'}</SelectItem>
                              <SelectItem value="deep">{'深入'}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </section>
                    <section className="space-y-3 border-t pt-4">
                      <div className="text-sm font-medium">{'评估范围'}</div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="tuning-sample-size">{'样本量'}</Label>
                          <Input
                            id="tuning-sample-size"
                            type="number"
                            value={tuningSampleSize}
                            onChange={(event) => setTuningSampleSize(event.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="tuning-top-k-eval">{'每次评估查看数量'}</Label>
                          <Input
                            id="tuning-top-k-eval"
                            type="number"
                            value={tuningTopKEval}
                            onChange={(event) => setTuningTopKEval(event.target.value)}
                          />
                        </div>
                      </div>
                    </section>
                    <div className="flex items-center gap-3 border-t pt-4">
                      <Checkbox
                        id="persist-best-profile"
                        checked={persistBestProfile}
                        onCheckedChange={(checked) => setPersistBestProfile(checked === true)}
                      />
                      <Label htmlFor="persist-best-profile">{'同时保存为默认设置'}</Label>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </CardContent>
          </Card>
        </div>

        <div className="min-w-0 space-y-4">
          <Card className="min-w-0 self-start">
            <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>{'当前调优结果'}</CardTitle>
                <CardDescription>
                  {isSummaryView ? '默认展示最近完成任务的评估结果，设置细节放在详情里。' : '面向排查的高级配置内容。'}
                </CardDescription>
              </div>
              {!isSummaryView ? (
                <Button type="button" variant="outline" size="sm" className="w-full sm:w-auto" onClick={toggleSnapshotView}>
                  <SnapshotToggleIcon className="h-4 w-4" />
                  {'返回结果摘要'}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {snapshotViewMode === 'summary' ? (
                <>
                  <TuningResultOverview task={resultTask} />

                  <details className="group overflow-hidden rounded-md border bg-background">
                    <summary className="flex cursor-pointer list-none flex-col gap-1 px-4 py-3 text-sm font-medium outline-none transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring sm:flex-row sm:items-center [&::-webkit-details-marker]:hidden">
                      <span className="flex min-w-0 items-center gap-2">
                        <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                        <span>{'设置详情'}</span>
                      </span>
                      <span className="text-xs font-normal text-muted-foreground sm:ml-auto">
                        {'排查时查看'}
                      </span>
                    </summary>
                    <div className="border-t">
                      <section className="grid gap-3 p-4 md:grid-cols-3">
                        <SnapshotResultCard
                          title={'当前使用中'}
                          description={runtimeResultText}
                        />
                        <SnapshotResultCard
                          title={'可保存设置'}
                          description={persistableResultText}
                        />
                        <SnapshotResultCard
                          title={'差异项'}
                          description={diffResultText}
                        />
                      </section>
                      <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                        <div className="text-sm font-medium">{'参数明细'}</div>
                        <Button type="button" variant="ghost" size="sm" onClick={toggleSnapshotView}>
                          <FileText className="h-4 w-4" />
                          {'查看高级配置'}
                        </Button>
                      </div>
                      <div className="max-h-[30vh] overflow-y-auto overscroll-contain border-t px-4 py-4 pr-3">
                        <div className="space-y-4">
                          <SnapshotSummarySection
                            title={'当前使用中'}
                            description={'已经用于当前记忆搜索的设置。'}
                            entries={readableRuntimeEntries}
                            technicalCount={runtimeTechnicalCount}
                            technicalNote={`另有 ${runtimeTechnicalCount} 个高级项目未在摘要中展示，可切到高级配置查看。`}
                            emptyText={'暂无数据'}
                          />
                          <SnapshotSummarySection
                            title={'可保存设置'}
                            description={'保存为默认设置时会保留的内容。'}
                            entries={readablePersistableEntries}
                            technicalCount={persistableTechnicalCount}
                            technicalNote={`另有 ${persistableTechnicalCount} 个高级项目未在摘要中展示，可切到高级配置查看。`}
                            emptyText={'暂无数据'}
                          />
                          <section className="space-y-3 rounded-md border bg-background p-4">
                            <div>
                              <div className="text-sm font-medium">{'差异项'}</div>
                              <div className="text-xs text-muted-foreground">{'当前使用的设置和可保存设置不一致的项目。'}</div>
                            </div>
                            {readableDiffs.length > 0 ? (
                              <div className="space-y-2">
                                {readableDiffs.map((entry) => (
                                  <div key={entry.path} className="grid gap-2 rounded-md border bg-background p-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                                    <div className="text-xs leading-5 text-muted-foreground lg:col-span-2">{entry.label}</div>
                                    <div className="min-w-0">
                                      <div className="text-[11px] text-muted-foreground">{'当前使用'}</div>
                                      <div className="break-all text-sm leading-6">{entry.runtime}</div>
                                    </div>
                                    <div className="min-w-0">
                                      <div className="text-[11px] text-muted-foreground">{'保存后'}</div>
                                      <div className="break-all text-sm leading-6">{entry.persistable}</div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                                {'两份配置当前没有差异。'}
                              </div>
                            )}
                            {technicalDiffCount > 0 ? (
                              <div className="rounded-md border border-dashed bg-background/60 p-3 text-xs text-muted-foreground">
                                {`另有 ${technicalDiffCount} 个高级差异未在摘要中展示，可切到高级配置查看。`}
                              </div>
                            ) : null}
                          </section>
                        </div>
                      </div>
                    </div>
                  </details>
                </>
              ) : (
                <CodeEditor
                  value={tuningProfileToml}
                  language="toml"
                  readOnly
                  height="640px"
                />
              )}
            </CardContent>
          </Card>

          <TuningTaskListCard tasks={tuningTasks} applyBestTask={applyBestTask} />
        </div>
      </div>
    </TabsContent>
  )
}
