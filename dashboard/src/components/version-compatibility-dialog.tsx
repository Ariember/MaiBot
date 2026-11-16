import { useEffect, useState, type CSSProperties } from 'react'

import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  getVersionCompatibility,
  type VersionCompatibilityResult,
} from '@/lib/version-compatibility-api'

const CONFIRM_DELAY_SECONDS = 3

function VersionValue({ value }: { value: string }) {
  return (
    <span className="font-mono text-sm font-semibold text-foreground">
      v{value}
    </span>
  )
}

export function VersionCompatibilityDialog() {
  const [compatibility, setCompatibility] = useState<VersionCompatibilityResult | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [remainingSeconds, setRemainingSeconds] = useState(CONFIRM_DELAY_SECONDS)

  useEffect(() => {
    const controller = new AbortController()

    async function checkCompatibility() {
      try {
        const result = await getVersionCompatibility(controller.signal)
        if (result.status !== 'compatible') {
          setCompatibility(result)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.warn('[VersionCompatibility] 跳过版本兼容性提示:', error)
        }
      }
    }

    void checkCompatibility()
    return () => controller.abort()
  }, [])

  const timerKey = compatibility && !dismissed ? `${compatibility.status}:${compatibility.main_program_version}` : ''
  const [seenTimerKey, setSeenTimerKey] = useState(timerKey)
  if (timerKey && seenTimerKey !== timerKey) {
    setSeenTimerKey(timerKey)
    setRemainingSeconds(CONFIRM_DELAY_SECONDS)
  }

  useEffect(() => {
    if (!compatibility || dismissed) {
      return
    }

    const timer = window.setInterval(() => {
      setRemainingSeconds((current) => {
        if (current <= 1) {
          window.clearInterval(timer)
          return 0
        }
        return current - 1
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [compatibility, dismissed])

  if (!compatibility) {
    return null
  }

  const webuiOutdated = compatibility.status === 'webui_outdated'
  const title = webuiOutdated
    ? 'WebUI 版本过低'
    : '主程序版本过低'
  const description = webuiOutdated
    ? `当前 WebUI v${compatibility.webui_version} 低于主程序要求的 v${compatibility.required_webui_version}。请更新 WebUI 静态资源包。`
    : `当前主程序 v${compatibility.main_program_version} 仅声明支持 WebUI v${compatibility.required_webui_version}，但正在运行 WebUI v${compatibility.webui_version}。请更新 MaiBot 主程序。`
  const updateTarget = webuiOutdated
    ? 'WebUI'
    : 'MaiBot 主程序'

  return (
    <Dialog
      open={!dismissed}
      onOpenChange={(open) => {
        if (!open && remainingSeconds === 0) {
          setDismissed(true)
        }
      }}
    >
      <DialogContent
        hideCloseButton
        preventOutsideClose
        style={{ '--dialog-width': '38rem' } as CSSProperties}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            {title}
          </DialogTitle>
          <DialogDescription className="leading-6">{description}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 rounded-md border bg-muted/40 p-4 sm:grid-cols-3">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              {'主程序版本'}
            </p>
            <VersionValue value={compatibility.main_program_version} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              {'当前 WebUI 版本'}
            </p>
            <VersionValue value={compatibility.webui_version} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              {'主程序要求的 WebUI 版本'}
            </p>
            <VersionValue value={compatibility.required_webui_version} />
          </div>
        </div>

        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
          <p className="font-medium">
            {`需要更新：${updateTarget}`}
          </p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {'继续使用不匹配的版本可能导致页面异常、接口不可用或配置错误。建议完成更新后再继续操作。'}
          </p>
        </div>

        <DialogFooter className="items-center gap-3 sm:justify-between sm:space-x-0">
          <p className="text-left text-xs leading-5 text-muted-foreground">
            {remainingSeconds > 0
              ? `请阅读以上提示，${remainingSeconds} 秒后可以关闭此页面。`
              : '你现在可以确认风险并继续使用。'}
          </p>
          <Button
            type="button"
            disabled={remainingSeconds > 0}
            onClick={() => setDismissed(true)}
            className="shrink-0"
          >
            {remainingSeconds > 0
              ? `${remainingSeconds} 秒后可确认`
              : '关闭提示并继续'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
