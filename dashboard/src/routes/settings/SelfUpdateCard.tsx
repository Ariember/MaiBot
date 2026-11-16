import { Card } from '@/components/ui/card'
import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'


import { RestartOverlay } from '@/components/restart-overlay'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { RestartProvider, useRestart } from '@/lib/restart-context'
import { markSelfUpdatePending } from '@/lib/self-update-pending'
import {
  applySelfUpdate,
  checkSelfUpdate,
  getSelfUpdateStatus,
  getSelfUpdateCustomPrefix,
  SELF_UPDATE_STATUS_EVENT,
  type SelfUpdateResult,
  type SelfUpdateStatus,
  type SelfUpdateSourceSelection,
} from '@/lib/system-api'

const SETTINGS_SELFUPDATE_BLOCKERS_LABELS: Record<string, string> = {
  "package_update_removed": "Python 包自更新已移除，请迁移到本 fork 的 GHCR 镜像部署",
  "image_updater_unavailable": "镜像更新服务未就绪，请检查 updater 容器日志",
  "image_update_busy": "镜像正在更新，请等待完成",
  "image_recovery_required": "上次更新中断或启动失败，请按部署文档恢复后再更新",
  "git_missing": "未找到 Git，无法自更新",
  "not_git_repo": "当前不是 Git 部署，请使用本 fork 的 GHCR 镜像或 Git 部署",
  "detached_head": "当前不在任何分支上（分离头指针），无法自更新",
  "unsupported_branch": "仅支持在 main 或 dev 分支上自更新",
  "dirty_worktree": "存在未提交的本地改动，请先提交或还原",
  "diverged": "本地存在 Ariember/MaiBot 分支没有的提交，无法快进更新",
  "no_dependency_tool": "本次更新包含依赖变更，但未找到可用的依赖安装方式（uv 或 pip）",
  "python_requirement_changed": "本次更新修改了 Python 版本要求，请手动更新",
}


// 更新要拉取代码并同步依赖，比普通重启慢得多：每 2 秒检查一次，最多等待约 15 分钟。
const UPDATE_HEALTH_CHECK_ATTEMPTS = 450

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function formatTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString()
}

function formatRevision(version: string, commit: string): string {
  return commit ? `${version} (${commit.replace(/^sha256:/, '').slice(0, 12)})` : version
}

/** 主程序自更新卡片：检查官方仓库的新版本，并在确认后更新、重启。 */
export function SelfUpdateCard() {

  return (
    <RestartProvider>
      <SelfUpdateCardContent />
      <RestartOverlay
        title={'正在更新麦麦'}
        description={'正在拉取新版本并同步依赖，可能需要几分钟，请不要关闭麦麦'}
      />
    </RestartProvider>
  )
}

function SelfUpdateCardContent() {
  const { toast } = useToast()
  const { triggerRestart, isRestarting } = useRestart()
  const [status, setStatus] = useState<SelfUpdateStatus | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkProgress, setCheckProgress] = useState<string[]>([])
  const [checkElapsed, setCheckElapsed] = useState(0)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false)
  const [sourceId, setSourceId] = useState<SelfUpdateSourceSelection['source_id'] | ''>('')
  const [customPrefix, setCustomPrefix] = useState(getSelfUpdateCustomPrefix)
  const [checkedSource, setCheckedSource] = useState<SelfUpdateSourceSelection | null>(null)
  const [imageRequest, setImageRequest] = useState<{ commit: string; requestedAt: number } | null>(null)

  useEffect(() => {
    if (!imageRequest) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const deadline = Date.now() + 45 * 60 * 1000
    const poll = async () => {
      try {
        const next = await getSelfUpdateStatus()
        if (cancelled) return
        const result = next.last_result
        if (result?.to_commit === imageRequest.commit && result.finished_at >= imageRequest.requestedAt) {
          setStatus(next)
          setImageRequest(null)
          setApplying(false)
          if (result.success) {
            markSelfUpdatePending(imageRequest.commit)
            await triggerRestart({ skipApiCall: true, maxAttempts: UPDATE_HEALTH_CHECK_ATTEMPTS })
          } else {
            setOperationError(result.error)
          }
          return
        }
      } catch {
        // 容器替换期间连接会断开；以执行器结果确认完成，不能把旧容器仍在线当成成功。
      }
      if (cancelled) return
      if (Date.now() >= deadline) {
        setImageRequest(null)
        setApplying(false)
        setOperationError('等待镜像更新超时，请查看 updater 日志和 docker-update-state/last_result.json，不要重复提交。')
        return
      }
      timer = setTimeout(poll, 2000)
    }
    timer = setTimeout(poll, 2000)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [imageRequest, triggerRestart])

  useEffect(() => {
    if (!checking) return
    const started = Date.now()
    const timer = window.setInterval(() => setCheckElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [checking])

  useEffect(() => {
    let cancelled = false
    let receivedCheck = false
    const handleStatus = (event: Event) => {
      receivedCheck = true
      setStatus((event as CustomEvent<SelfUpdateStatus>).detail)
      // 自动检查只提供展示状态；应用更新仍由用户选择并确认本次来源。
      setCheckedSource(null)
      setLoadError(null)
    }
    window.addEventListener(SELF_UPDATE_STATUS_EVENT, handleStatus)
    getSelfUpdateStatus()
      .then((next) => {
        if (!cancelled && !receivedCheck) setStatus(next)
      })
      .catch((error: unknown) => {
        if (!cancelled && !receivedCheck) setLoadError(errorMessage(error))
      })
    return () => {
      cancelled = true
      window.removeEventListener(SELF_UPDATE_STATUS_EVENT, handleStatus)
    }
  }, [])

  const handleCheck = async () => {
    if (!sourceId || (sourceId === 'custom' && !customPrefix.trim())) return
    const selection: SelfUpdateSourceSelection = {
      source_id: sourceId,
      ...(sourceId === 'custom' ? { custom_prefix: customPrefix.trim() } : {}),
    }
    setChecking(true)
    setCheckElapsed(0)
    setCheckProgress([])
    setOperationError(null)
    setCheckedSource(null)
    try {
      setStatus(await checkSelfUpdate(selection, true, (message) => {
        setCheckProgress((previous) => [...previous.slice(-11), message])
      }))
      setCheckedSource(selection)
      setSourceDialogOpen(false)
      setLoadError(null)
    } catch (error) {
      setOperationError(errorMessage(error))
      toast({
        title: '检查更新失败',
        description: errorMessage(error),
        variant: 'destructive',
      })
    } finally {
      setChecking(false)
    }
  }

  const handleApply = async () => {
    const targetCommit = status?.latest_commit
    if (!targetCommit || !checkedSource) return

    setApplying(true)
    setOperationError(null)
    try {
      const response = await applySelfUpdate(targetCommit, checkedSource)
      if (status.deployment_type === 'image') {
        setImageRequest({ commit: targetCommit, requestedAt: response.requested_at })
        return
      }
    } catch (error) {
      setOperationError(errorMessage(error))
      toast({
        title: '发起更新失败',
        description: errorMessage(error),
        variant: 'destructive',
      })
      setApplying(false)
      return
    }
    markSelfUpdatePending(targetCommit)
    // 后端已经登记更新并开始重启，这里只负责等待它带着新版本回来。
    await triggerRestart({ skipApiCall: true, maxAttempts: UPDATE_HEALTH_CHECK_ATTEMPTS })
  }

  const busy = checking || applying || isRestarting

  return (
    <Card className="p-4 sm:p-6" data-testid="self-update-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base sm:text-lg font-semibold">{'主程序更新'}</h3>
          {status && (
            <p className="mt-1 text-xs sm:text-sm text-muted-foreground break-all">
              {`当前版本 ${status.current_version}`}
              {status.branch && ` · ${status.branch}`}
              {status.deployment_type === 'image'
                ? ` · GHCR · ${status.current_commit?.replace(/^sha256:/, '').slice(0, 12) ?? ''}`
                : status.current_commit && ` · ${status.current_commit.slice(0, 8)}`}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setSourceId(status?.deployment_type === 'image' ? 'ghcr' : '')
            setCustomPrefix(getSelfUpdateCustomPrefix())
            setSourceDialogOpen(true)
          }}
          disabled={busy || !status?.supported}
        >
          {checking ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {checking ? '正在检查…' : '检查更新'}
        </Button>
      </div>

      <Dialog open={sourceDialogOpen} onOpenChange={(open) => { if (!checking) setSourceDialogOpen(open) }}>
        <DialogContent preventOutsideClose={checking} className="max-h-[85dvh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>选择本体更新源</DialogTitle>
            <DialogDescription>{'源码与镜像均跟随 Ariember/MaiBot；镜像从 GitHub Container Registry 下载。'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="self-update-source">更新源</Label>
              <Select value={sourceId} disabled={checking}
                onValueChange={(value: SelfUpdateSourceSelection['source_id']) => setSourceId(value)}>
                <SelectTrigger id="self-update-source"><SelectValue placeholder="请选择本次更新使用的来源" /></SelectTrigger>
                <SelectContent>
                  {status?.deployment_type === 'image' ? <>
                    <SelectItem value="ghcr">GitHub Container Registry</SelectItem>
                  </> : <>
                    <SelectItem value="github">GitHub · Ariember/MaiBot</SelectItem>
                    <SelectItem value="custom">自定义源</SelectItem>
                  </>}
                </SelectContent>
              </Select>
            </div>
            {sourceId === 'custom' && <div className="space-y-2">
              <Label htmlFor="self-update-custom-source">Git 镜像前缀</Label>
              <Input id="self-update-custom-source" value={customPrefix} disabled={checking}
                onChange={(event) => setCustomPrefix(event.target.value)}
                placeholder="https://example.com/https://github.com" />
              <p className="text-sm text-muted-foreground">只填写一个源前缀，后面会追加 /Ariember/MaiBot.git。</p>
            </div>}
          </div>
          {(checking || checkProgress.length > 0) && (
            <div role="status" className="space-y-2 text-sm">
              <p className="text-muted-foreground">
                {checking ? '正在检查更新' : operationError ? '检查未完成' : '检查完成'} · 已等待 {checkElapsed} 秒
              </p>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted/50 p-3 text-xs">
                {checkProgress.length > 0 ? checkProgress.join('\n') : '等待后端开始检查…'}
              </pre>
            </div>
          )}
          {operationError && (
            <pre role="alert" className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive select-text">
              {operationError}
            </pre>
          )}
          <DialogFooter>
            <Button variant="outline" disabled={checking} onClick={() => setSourceDialogOpen(false)}>取消</Button>
            <Button disabled={checking || !sourceId || (sourceId === 'custom' && !customPrefix.trim())} onClick={handleCheck}>
              {checking && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}检查更新
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="mt-3 space-y-3 text-xs sm:text-sm">
        {operationError && !sourceDialogOpen && (
          <pre role="alert" className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive select-text">
            {operationError}
          </pre>
        )}
        {loadError && (
          <p className="text-destructive">
            {'读取更新状态失败'}: {loadError}
          </p>
        )}
        {!status && !loadError && (
          <p className="text-muted-foreground">{'正在读取更新状态…'}</p>
        )}
        {status && !status.supported && (
          <div className="rounded-md bg-muted/50 p-3 text-muted-foreground">
            {status.blockers.map((blocker) => (
              <p key={blocker}>{SETTINGS_SELFUPDATE_BLOCKERS_LABELS[blocker]}</p>
            ))}
          </div>
        )}
        {status?.supported && status.checked_at === null && (
          <p className="text-muted-foreground">{'尚未检查更新'}</p>
        )}
        {status?.supported && status.checked_at !== null && !status.update_available && (
          <p className="flex items-center gap-2 text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
            {'已是最新版本'}
            <span>· {`检查于 ${formatTime(status.checked_at)}`}</span>
          </p>
        )}
        {status?.supported && status.update_available && (
          <AvailableUpdate status={status} busy={busy || !checkedSource} applying={applying} onApply={handleApply} />
        )}
        {status?.last_result && <LastResult result={status.last_result} />}
        {status?.supported && status.source_name && (
          <p className="text-muted-foreground break-all">
            {`更新来源：${status.source_name}`}
          </p>
        )}
      </div>
    </Card>
  )
}

interface AvailableUpdateProps {
  status: SelfUpdateStatus
  busy: boolean
  applying: boolean
  onApply: () => void
}

function AvailableUpdate({ status, busy, applying, onApply }: AvailableUpdateProps) {
  const image = status.deployment_type === 'image'
  const versionChanged =
    status.latest_version !== null && status.latest_version !== status.current_version
  const targetLabel = formatRevision(
    image ? `ghcr.io/ariember/maibot:${status.branch}` : status.latest_version ?? status.current_version,
    status.latest_commit ?? ''
  )

  return (
    <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
      <div>
        <p className="font-medium text-foreground">
          {image ? '发现新的容器镜像' : versionChanged
            ? `发现新版本 ${status.latest_version}`
            : `有 ${status.behind} 个新提交`}
        </p>
        {!image && <p className="text-muted-foreground">
          {`落后 Ariember/MaiBot 的 ${status.branch} 分支 ${status.behind} 个提交`}
        </p>}
      </div>

      {image && <p className="break-all font-mono text-xs" title={status.latest_commit ?? undefined}>{targetLabel}</p>}
      {!image && <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md bg-background/60 p-2">
        {status.commits.map((commit) => (
          <li key={commit.short_id} className="flex gap-2">
            <code className="shrink-0 text-muted-foreground">{commit.short_id}</code>
            <span className="min-w-0 break-words">{commit.summary}</span>
          </li>
        ))}
        {status.behind > status.commits.length && (
          <li className="text-muted-foreground">
            {`仅显示最近 ${status.commits.length} 个提交`}
          </li>
        )}
      </ul>}

      {status.dependencies_changed && status.dependency_tool && (
        <p className="text-muted-foreground">
          {`本次更新包含依赖变更，更新时会自动同步依赖（${status.dependency_tool}）`}
        </p>
      )}

      {status.blockers.length > 0 && (
        <div className="space-y-1 rounded-md border border-destructive/30 bg-destructive/5 p-2">
          <p className="flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {'暂时无法自动更新'}
          </p>
          <ul className="list-inside list-disc text-muted-foreground">
            {status.blockers.map((blocker) => (
              <li key={blocker}>{SETTINGS_SELFUPDATE_BLOCKERS_LABELS[blocker]}</li>
            ))}
          </ul>
          {status.dirty_files.length > 0 && (
            <p className="break-all text-muted-foreground">
              {'有改动的文件：'} {status.dirty_files.join(', ')}
            </p>
          )}
        </div>
      )}

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size="sm" disabled={busy || !status.can_apply}>
            {applying ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {'立即更新'}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader className="min-w-0">
            <AlertDialogTitle className="break-all">
              {`更新到 ${targetLabel}？`}
            </AlertDialogTitle>
            <AlertDialogDescription>{(image ? '先下载确认的镜像，再停止麦麦、备份持久数据、替换容器并检查 WebUI。新版本启动失败时会停止运行并保留现场，请按部署文档恢复备份；不会直接用旧镜像打开已迁移的数据库。' : '更新期间麦麦会离线几分钟：先停止运行，再拉取新版本、同步依赖并重新启动。拉取或依赖同步失败时会自动回滚到当前版本。建议先备份 data 目录。')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{'取消'}</AlertDialogCancel>
            <AlertDialogAction onClick={onApply}>
              {'更新并重启'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function LastResult({ result }: { result: SelfUpdateResult }) {
  const time = formatTime(result.finished_at)
  const to = formatRevision(result.to_version || '?', result.to_commit)

  if (result.success) {
    return (
      <p className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
        {`已于 ${time} 从 ${formatRevision(result.from_version, result.from_commit)} 更新到 ${to}`}
      </p>
    )
  }

  return (
    <div className="space-y-2 rounded-md border border-destructive/30 bg-destructive/5 p-3">
      <p className="flex items-center gap-2 font-medium text-destructive">
        <XCircle className="h-4 w-4 shrink-0" />
        {`${time} 更新到 ${to} 失败`}
      </p>
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-background/60 p-2 text-xs">
        {result.error}
      </pre>
      {result.rolled_back && (
        <p className="text-muted-foreground">{'已自动回滚到更新前的版本'}</p>
      )}
      {result.backup_path && <p className="break-all">{`升级前备份：${result.backup_path}`}</p>}
      {result.rollback_error && (
        <p className="text-destructive">
          {`自动回滚失败，请手动检查仓库与依赖状态：${result.rollback_error}`}
        </p>
      )}
    </div>
  )
}
