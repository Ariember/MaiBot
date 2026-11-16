import { useEffect, useRef, useState, type MouseEvent } from 'react'


import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  controlComputer, getComputerFrame, getComputerStatus,
  inputComputer, pollComputerOperation, type ComputerStatus,
} from '@/lib/computer-api'
import { cn } from '@/lib/utils'

const CHAT_COMPUTER_STATE_LABELS: Record<string, string> = {
  "connecting": "正在连接",
  "disabled": "电脑功能未启用",
  "stopped": "沙盒未运行",
  "manual": "人工接管",
  "paused": "已暂停决策",
  "resting": "休息中",
  "autonomous": "自主运行",
  "running": "操作执行中",
  "failed": "执行失败",
  "thinking": "思考中",
  "tool": "操作中",
  "idle": "空闲",
}

const CHAT_COMPUTER_OPERATION_LABELS: Record<string, string> = {
  "pause": "暂停电脑输入",
  "takeover": "接管电脑",
  "resume": "恢复运行",
  "stop": "停止沙盒",
  "restart": "重建沙盒",
}


export function ComputerDesktop() {
  const [status, setStatus] = useState<ComputerStatus | null>(null)
  const [frame, setFrame] = useState('')
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const locked = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const refresh = useRef<() => void>(() => {})

  useEffect(() => {
    const abort = new AbortController()
    controller.current = abort
    let timer: ReturnType<typeof setTimeout>
    let polling = false
    // 每次完成后再取下一帧，慢沙盒不会堆积截图请求；离开页面即停止轮询。
    const tick = async () => {
      if (polling || abort.signal.aborted) return
      polling = true
      clearTimeout(timer)
      try {
        const current = await getComputerStatus(abort.signal)
        setStatus(current)
        if (current.enabled && current.sandbox_running) {
          const image = await getComputerFrame(abort.signal)
          if (!abort.signal.aborted) setFrame(URL.createObjectURL(image))
        } else {
          setFrame('')
        }
        setConnectionError(current.error)
      } catch (cause) {
        if (!abort.signal.aborted) setConnectionError(String(cause))
      } finally {
        polling = false
        if (!abort.signal.aborted) timer = setTimeout(() => void tick(), 1000)
      }
    }
    refresh.current = () => void tick()
    void tick()
    return () => {
      abort.abort()
      clearTimeout(timer)
    }
  }, [])

  useEffect(() => () => { if (frame) URL.revokeObjectURL(frame) }, [frame])

  const run = async (action: (signal: AbortSignal) => Promise<void>) => {
    const signal = controller.current?.signal
    if (locked.current || !signal || signal.aborted) return
    locked.current = true
    setBusy(true)
    setError('')
    try {
      await action(signal)
      refresh.current()
    } catch (cause) {
      if (!signal.aborted) setError(String(cause))
    } finally {
      locked.current = false
      if (!signal.aborted) setBusy(false)
    }
  }

  const input = (actions: Record<string, unknown>[]) => run(async signal => {
    if (!status?.takeover) throw new Error('请先接管电脑')
    let result = await inputComputer(actions, signal)
    while (result.status === 'running' && !signal.aborted) {
      // 查询原操作，不重复提交键鼠输入。
      await new Promise(resolve => setTimeout(resolve, 500))
      if (signal.aborted) return
      result = await pollComputerOperation(result.operation_id, signal)
    }
    if (!result.success) throw new Error(result.error || result.capture_error || JSON.stringify(result))
  })

  const click = (event: MouseEvent<HTMLButtonElement>, button: 'left' | 'right') => {
    event.preventDefault()
    if (!status?.takeover || busy) return
    const image = event.currentTarget.querySelector('img')!
    const bounds = image.getBoundingClientRect()
    // 键盘触发按钮时没有鼠标坐标，点击画面中心。
    const keyboardClick = event.type === 'click' && event.detail === 0
    const x = keyboardClick ? bounds.left + bounds.width / 2 : event.clientX
    const y = keyboardClick ? bounds.top + bounds.height / 2 : event.clientY
    void input([{
      action: 'click', button,
      x: Math.min(image.naturalWidth - 1, Math.max(0, Math.floor((x - bounds.left) * image.naturalWidth / bounds.width))),
      y: Math.min(image.naturalHeight - 1, Math.max(0, Math.floor((y - bounds.top) * image.naturalHeight / bounds.height))),
    }])
  }

  const state = !status ? 'connecting' : !status.enabled ? 'disabled' : !status.sandbox_running ? 'stopped'
    : status.takeover ? 'manual' : status.paused ? 'paused' : !status.pending_request ? 'resting' : 'autonomous'

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4 md:p-6">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="mr-auto text-sm text-muted-foreground" role="status">
          {CHAT_COMPUTER_STATE_LABELS[state]}{status?.pending_request ? ' · 操作执行中' : ''}
        </span>
        {(['pause', 'takeover', 'resume', 'stop', 'restart'] as const).map(operation => (
          <Button key={operation} size="sm" variant="outline" disabled={busy || !status?.enabled}
            onClick={() => void run(async signal => { setStatus(await controlComputer(operation, signal)) })}>
            {CHAT_COMPUTER_OPERATION_LABELS[operation]}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={() => refresh.current()}>{'刷新画面'}</Button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">{'内部 Planner、子 Agent 和外接 Agent 共用此电脑。接管后可点击画面、右键和输入文字。接管会取消在途操作并阻止自主输入；暂停电脑输入不会中断已提交的操作。'}</p>
      {(error || connectionError) && <p role="alert" className="mb-3 whitespace-pre-wrap break-words text-sm text-destructive">{error || connectionError}</p>}
      {frame ? (
        <button type="button" disabled={!status?.takeover || busy}
          className={cn('block w-full shrink-0 overflow-hidden rounded-lg border bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary', status?.takeover && 'cursor-crosshair ring-2 ring-primary')}
          onClick={event => click(event, 'left')} onContextMenu={event => click(event, 'right')}>
          <img src={frame} alt={'电脑桌面'} draggable={false} className="block h-auto w-full" />
        </button>
      ) : <div className="flex min-h-48 items-center justify-center rounded-lg border bg-muted/30 text-sm text-muted-foreground">{CHAT_COMPUTER_STATE_LABELS[state]}</div>}
      <form className="my-3 flex flex-wrap gap-2" onSubmit={event => {
        event.preventDefault()
        if (text) void input([{ action: 'type', text }])
      }}>
        <Input className="min-w-40 flex-1" value={text} onChange={event => setText(event.target.value)}
          disabled={!status?.takeover || busy} aria-label={'接管后输入文字，支持中文'} placeholder={'接管后输入文字，支持中文'} />
        <Button type="submit" disabled={!status?.takeover || busy || !text}>{'输入文字'}</Button>
        {['ENTER', 'ESC'].map(key => <Button key={key} type="button" variant="outline" disabled={!status?.takeover || busy}
          onClick={() => void input([{ action: 'keys', keys: [key] }])}>{key === 'ENTER' ? '回车' : 'Esc'}</Button>)}
      </form>
    </section>
  )
}
