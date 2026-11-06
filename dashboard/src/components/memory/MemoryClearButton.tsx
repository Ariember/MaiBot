import { Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { clearAllMemory } from '@/lib/memory-api'

export function MemoryClearButton() {
  const [step, setStep] = useState<'warning' | 'confirm' | null>(null)
  const [confirmation, setConfirmation] = useState('')
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState('')

  const clearMemory = async () => {
    if (clearing || confirmation !== '清空全部记忆') return
    setClearing(true)
    setError('')
    try {
      const result = await clearAllMemory(confirmation)
      if (!result.success) throw new Error(result.error || '清空失败，请重试')
      // 重载整个控制台，清除各标签页中的旧记录、预览和查询缓存。
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : '清空失败，请重试')
      setClearing(false)
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/40 p-4">
        <div>
          <p className="font-medium text-destructive">清空全部长期记忆</p>
          <p className="text-sm text-muted-foreground">恢复为空白记忆，永久删除所有会话的记忆，无法从回收站恢复。</p>
        </div>
        <Button variant="destructive" onClick={() => {
          setConfirmation('')
          setError('')
          setStep('warning')
        }}>
          <Trash2 className="mr-2 h-4 w-4" />
          清空全部记忆
        </Button>
      </div>
      <Dialog key={step} open={step !== null} onOpenChange={(open) => {
        if (!open && !clearing) setStep(null)
      }}>
        <DialogContent hideCloseButton={clearing}>
          <DialogHeader>
            <DialogTitle>{step === 'warning' ? '清空全部长期记忆？' : '最后确认：永久清空全部记忆'}</DialogTitle>
            <DialogDescription>
              {step === 'warning'
                ? '此操作影响所有会话，不受当前筛选条件限制。文字记忆、人物画像、图片记忆、情景、图谱、回收站及导入记录和暂存文件都会被永久清除。'
                : '这是不可撤销的操作，不会保留可恢复的删除记录。请先自行导出需要保留的记忆，再输入“清空全部记忆”确认。'}
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            聊天原始记录和机器人配置会保留。清空后记忆功能继续运行，后续聊天可产生新记忆。
          </p>
          {step === 'confirm' && (
            <div className="space-y-2">
              <Label htmlFor="clear-memory-confirmation">输入“清空全部记忆”</Label>
              <Input id="clear-memory-confirmation" value={confirmation} disabled={clearing}
                autoComplete="off" onChange={(event) => setConfirmation(event.target.value)} />
            </div>
          )}
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          {clearing && <p role="status" className="text-sm text-muted-foreground">正在停止记忆任务并清空数据，请勿重复操作。完成后页面会自动刷新。</p>}
          <DialogFooter>
            <Button variant="outline" disabled={clearing} onClick={() => setStep(null)}>取消</Button>
            {step === 'warning' ? (
              <Button variant="destructive" onClick={() => setStep('confirm')}>我已了解风险，继续</Button>
            ) : (
              <Button variant="destructive" disabled={clearing || confirmation !== '清空全部记忆'} onClick={() => void clearMemory()}>
                {clearing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {clearing ? '正在清空…' : '永久清空全部记忆'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
