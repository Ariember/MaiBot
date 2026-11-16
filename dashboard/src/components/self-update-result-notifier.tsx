import { useEffect } from 'react'


import { useToast } from '@/hooks/use-toast'
import { takeSelfUpdatePending } from '@/lib/self-update-pending'
import { getSelfUpdateStatus } from '@/lib/system-api'

/**
 * 自更新重启完成后，提示这一次更新是成功还是已回滚。
 * 只有本页面发起过更新时才会请求后端。
 */
export function SelfUpdateResultNotifier() {
  const { toast } = useToast()

  useEffect(() => {
    const commit = takeSelfUpdatePending()
    if (commit === null) return

    getSelfUpdateStatus()
      .then((status) => {
        const result = status.last_result
        if (result === null || result.to_commit !== commit) return
        if (result.success) {
          toast({
            title: '更新完成',
            description: `已更新到 ${result.to_version}`,
          })
        } else {
          toast({
            title: '更新失败',
            description: '更新失败，详情见「设置 → 关于」',
            variant: 'destructive',
            duration: 20000,
          })
        }
      })
      .catch((error: unknown) => {
        console.error('读取自更新结果失败', error)
      })
  }, [toast])

  return null
}
