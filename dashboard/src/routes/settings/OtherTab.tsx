import { Card } from '@/components/ui/card'
import { AlertTriangle, Database, Download, HardDrive, RefreshCw, RotateCcw, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'

import { useNavigate } from '@tanstack/react-router'

import { cn } from '@/lib/utils'
import { ApiError, backendApi } from '@/lib/http'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'
import { clearLocalCache, DEFAULT_SETTINGS, exportSettings, formatBytes, getSetting, getStorageUsage, importSettings, resetAllGuidesAndNotices, resetAllNotificationStates, resetAllSettings, setSetting } from '@/lib/settings-manager'
import { logWebSocket } from '@/lib/log-websocket'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'

// 其他设置标签页
export function OtherTab() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [isResetting, setIsResetting] = useState(false)
  const [resetSetupPassword, setResetSetupPassword] = useState(false)
  const [shouldThrowError, setShouldThrowError] = useState(false)
  
  // 性能与存储设置状态
  const [logCacheSize, setLogCacheSize] = useState(() => getSetting('logCacheSize'))
  const [wsReconnectInterval, setWsReconnectInterval] = useState(() => getSetting('wsReconnectInterval'))
  const [wsMaxReconnectAttempts, setWsMaxReconnectAttempts] = useState(() => getSetting('wsMaxReconnectAttempts'))
  const [dataSyncInterval, setDataSyncInterval] = useState(() => getSetting('dataSyncInterval'))
  const [enableAvatarFetch, setEnableAvatarFetch] = useState(() => getSetting('enableAvatarFetch'))
  const [alwaysShowUpdateNotice, setAlwaysShowUpdateNotice] = useState(() => getSetting('alwaysShowUpdateNotice'))
  const [alwaysShowUpdateButton, setAlwaysShowUpdateButton] = useState(() => getSetting('alwaysShowUpdateButton'))
  const [storageUsage, setStorageUsage] = useState(() => getStorageUsage())
  
  // 导入/导出状态
  const [isExporting, setIsExporting] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 手动触发 React 错误
  if (shouldThrowError) {
    throw new Error('这是一个手动触发的测试错误，用于验证错误边界组件是否正常工作。')
  }

  // 刷新存储使用情况
  const refreshStorageUsage = () => {
    setStorageUsage(getStorageUsage())
  }

  // 处理日志缓存大小变更
  const handleLogCacheSizeChange = (value: number[]) => {
    const size = value[0]
    setLogCacheSize(size)
    setSetting('logCacheSize', size)
  }

  // 处理 WebSocket 重连间隔变更
  const handleWsReconnectIntervalChange = (value: number[]) => {
    const interval = value[0]
    setWsReconnectInterval(interval)
    setSetting('wsReconnectInterval', interval)
  }

  // 处理 WebSocket 最大重连次数变更
  const handleWsMaxReconnectAttemptsChange = (value: number[]) => {
    const attempts = value[0]
    setWsMaxReconnectAttempts(attempts)
    setSetting('wsMaxReconnectAttempts', attempts)
  }

  // 处理数据同步间隔变更
  const handleDataSyncIntervalChange = (value: number[]) => {
    const interval = value[0]
    setDataSyncInterval(interval)
    setSetting('dataSyncInterval', interval)
  }

  const handleAvatarFetchChange = (checked: boolean) => {
    setEnableAvatarFetch(checked)
    setSetting('enableAvatarFetch', checked)
  }

  const handleAlwaysShowUpdateNoticeChange = (checked: boolean) => {
    setAlwaysShowUpdateNotice(checked)
    setSetting('alwaysShowUpdateNotice', checked)
  }

  // 清除日志缓存
  const handleClearLogCache = () => {
    logWebSocket.clearLogs()
    toast({
      title: '日志已清除',
      description: '日志缓存已清空',
    })
  }

  // 清除本地缓存
  const handleClearLocalCache = () => {
    const result = clearLocalCache()
    refreshStorageUsage()
    toast({
      title: '缓存已清除',
      description: `已清除 ${result.clearedKeys.length} 项缓存数据`,
    })
  }

  // 导出设置
  const handleExportSettings = () => {
    setIsExporting(true)
    try {
      const settings = exportSettings()
      const dataStr = JSON.stringify(settings, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `maibot-webui-settings-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast({
        title: '导出成功',
        description: '设置已导出为 JSON 文件',
      })
    } catch (error) {
      console.error('导出设置失败:', error)
      toast({
        title: '导出失败',
        description: '无法导出设置',
        variant: 'destructive',
      })
    } finally {
      setIsExporting(false)
    }
  }

  // 导入设置
  const handleImportSettings = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsImporting(true)
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const settings = JSON.parse(content)
        const result = importSettings(settings)
        
        if (result.success) {
          // 刷新页面状态
          setLogCacheSize(getSetting('logCacheSize'))
          setWsReconnectInterval(getSetting('wsReconnectInterval'))
          setWsMaxReconnectAttempts(getSetting('wsMaxReconnectAttempts'))
          setDataSyncInterval(getSetting('dataSyncInterval'))
          setEnableAvatarFetch(getSetting('enableAvatarFetch'))
          setAlwaysShowUpdateNotice(getSetting('alwaysShowUpdateNotice'))
          setAlwaysShowUpdateButton(getSetting('alwaysShowUpdateButton'))
          refreshStorageUsage()
          
          toast({
            title: '导入成功',
            description: `成功导入 ${result.imported.length} 项设置` + (result.skipped.length > 0 ? `，跳过 ${result.skipped.length} 项` : ''),
          })
          
          // 提示用户刷新页面以应用所有更改
          if (result.imported.includes('theme')) {
            toast({
              title: '提示',
              description: '部分设置需要刷新页面才能完全生效',
            })
          }
        } else {
          toast({
            title: '导入失败',
            description: '没有有效的设置项可导入',
            variant: 'destructive',
          })
        }
      } catch (error) {
        console.error('导入设置失败:', error)
        toast({
          title: '导入失败',
          description: '文件格式无效',
          variant: 'destructive',
        })
      } finally {
        setIsImporting(false)
        // 清空 input，允许重复选择同一文件
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    }
    reader.readAsText(file)
  }

  // 重置所有设置
  const handleResetAllSettings = () => {
    resetAllSettings()
    // 刷新页面状态
    setLogCacheSize(DEFAULT_SETTINGS.logCacheSize)
    setWsReconnectInterval(DEFAULT_SETTINGS.wsReconnectInterval)
    setWsMaxReconnectAttempts(DEFAULT_SETTINGS.wsMaxReconnectAttempts)
    setDataSyncInterval(DEFAULT_SETTINGS.dataSyncInterval)
    setEnableAvatarFetch(DEFAULT_SETTINGS.enableAvatarFetch)
    setAlwaysShowUpdateNotice(DEFAULT_SETTINGS.alwaysShowUpdateNotice)
    setAlwaysShowUpdateButton(DEFAULT_SETTINGS.alwaysShowUpdateButton)
    refreshStorageUsage()
    toast({
      title: '已重置',
      description: '所有设置已恢复为默认值，刷新页面以应用更改',
    })
  }

  const handleResetGuidesAndNotices = () => {
    const clearedCount = resetAllGuidesAndNotices()
    refreshStorageUsage()
    toast({
      title: '引导和提示已重置',
      description: `已清除 ${clearedCount} 项状态，重新进入对应页面后生效。`,
    })
  }

  const handleResetNotificationStates = () => {
    const clearedCount = resetAllNotificationStates()
    refreshStorageUsage()
    toast({
      title: '通知状态已重置',
      description: `已清除 ${clearedCount} 项状态，重新进入对应页面后生效。`,
    })
  }

  const handleResetSetup = async () => {
    setIsResetting(true)

    try {
      // 同一个请求重置向导和可选的密码；后端会续上当前浏览器的登录 Cookie。
      const data = await backendApi.post<{ success: boolean; message?: string }>(
        '/api/webui/setup/reset',
        {
          body: { reset_password: resetSetupPassword },
          errorMessage: '无法重置配置向导，请重试。',
        }
      )

      if (data.success) {
        toast({
          title: '重置成功',
          description: (resetSetupPassword ? '密码已重置，即将进入密码设置页。' : '配置向导已重置，即将重新进入。'),
        })

        // 延迟跳转到配置向导
        setTimeout(() => {
          navigate({ to: '/setup' })
        }, 1000)
      } else {
        toast({
          title: '重置失败',
          description: data.message || '无法重置配置向导，请重试。',
          variant: 'destructive',
        })
      }
    } catch (error) {
      console.error('重置配置状态错误:', error)
      toast({
        title: '重置失败',
        // HTTP 层失败展示后端给出的错误信息；网络层失败保持原有固定文案
        description:
          error instanceof ApiError && error.status !== undefined
            ? error.message
            : '无法重置配置向导，请重试。',
        variant: 'destructive',
      })
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 展示设置 */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">
          {'展示设置'}
        </h3>
        <div className="flex items-start justify-between gap-4 rounded-lg bg-muted/50 p-3 sm:p-4">
          <div className="min-w-0 space-y-1">
            <Label htmlFor="enable-avatar-fetch" className="text-sm font-medium">
              {'获取并显示用户头像'}
            </Label>
            <p className="text-xs text-muted-foreground">
              {'关闭后，聊天页和推理过程不再请求头像接口，界面会显示默认头像。'}
            </p>
          </div>
          <Switch
            id="enable-avatar-fetch"
            checked={enableAvatarFetch}
            onCheckedChange={handleAvatarFetchChange}
            aria-label={'获取并显示用户头像'}
          />
        </div>
      </Card>

      {/* 引导与提示 */}
      <Card className="p-4 sm:p-6">
        <h3 className="mb-3 flex items-center gap-2 text-base font-semibold sm:mb-4 sm:text-lg">
          <RotateCcw className="h-5 w-5" />
          {'引导与提示'}
        </h3>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground sm:text-sm">
            {'重置所有已完成的引导和已关闭的提示，不影响其他设置或业务数据。'}
          </p>
          <Button variant="outline" onClick={handleResetGuidesAndNotices} className="shrink-0 gap-2">
            <RotateCcw className="h-4 w-4" />
            {'重置所有引导和提示'}
          </Button>
        </div>
      </Card>

      {/* 性能与存储 */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4 flex items-center gap-2">
          <Database className="h-5 w-5" />
          {'性能与存储'}
        </h3>
        <div className="space-y-4 sm:space-y-5">
          {/* 存储使用情况 */}
          <div className="rounded-lg bg-muted/50 p-3 sm:p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium flex items-center gap-2">
                <HardDrive className="h-4 w-4" />
                {'本地存储使用'}
              </span>
              <Button variant="ghost" size="sm" onClick={refreshStorageUsage} className="h-7 px-2">
                <RefreshCw className="h-3 w-3" />
              </Button>
            </div>
            <div className="text-2xl font-bold text-primary">{formatBytes(storageUsage.used)}</div>
            <p className="text-xs text-muted-foreground mt-1">{`${storageUsage.items} 个存储项`}</p>
          </div>

          {/* 日志缓存大小 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">{'日志缓存大小'}</Label>
              <span className="text-sm text-muted-foreground">{logCacheSize} {'条'}</span>
            </div>
            <Slider
              value={[logCacheSize]}
              onValueChange={handleLogCacheSizeChange}
              min={100}
              max={5000}
              step={100}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              {'控制日志查看器最多缓存的日志条数，较大的值会占用更多内存'}
            </p>
          </div>

          {/* 数据刷新间隔 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">{'首页数据刷新间隔'}</Label>
              <span className="text-sm text-muted-foreground">{dataSyncInterval} {'秒'}</span>
            </div>
            <Slider
              value={[dataSyncInterval]}
              onValueChange={handleDataSyncIntervalChange}
              min={10}
              max={120}
              step={5}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              {'控制首页统计数据的自动刷新间隔'}
            </p>
          </div>

          {/* WebSocket 重连间隔 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">{'WebSocket 重连间隔'}</Label>
              <span className="text-sm text-muted-foreground">{wsReconnectInterval / 1000} {'秒'}</span>
            </div>
            <Slider
              value={[wsReconnectInterval]}
              onValueChange={handleWsReconnectIntervalChange}
              min={1000}
              max={10000}
              step={500}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              {'日志 WebSocket 连接断开后的重连基础间隔'}
            </p>
          </div>

          {/* WebSocket 最大重连次数 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">{'WebSocket 最大重连次数'}</Label>
              <span className="text-sm text-muted-foreground">{wsMaxReconnectAttempts} {'次'}</span>
            </div>
            <Slider
              value={[wsMaxReconnectAttempts]}
              onValueChange={handleWsMaxReconnectAttemptsChange}
              min={3}
              max={30}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              {'连接失败后的最大重连尝试次数'}
            </p>
          </div>

          {/* 清理按钮 */}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={handleClearLogCache} className="gap-2">
              <Trash2 className="h-4 w-4" />
              {'清除日志缓存'}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <Trash2 className="h-4 w-4" />
                  {'清除本地缓存'}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{'确认清除本地缓存'}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {'这将清除所有本地缓存的设置和数据（不包括登录凭证）。您可能需要重新配置部分偏好设置。确定要继续吗？'}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                  <AlertDialogAction onClick={handleClearLocalCache}>
                    {'确认清除'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </Card>

      {/* 导入/导出设置 */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4 flex items-center gap-2">
          <Download className="h-5 w-5" />
          {'导入/导出设置'}
        </h3>
        <div className="space-y-4">
          <p className="text-xs sm:text-sm text-muted-foreground">
            {'导出当前的界面设置以便备份，或从之前导出的文件中恢复设置。'}
          </p>
          
          <div className="flex flex-wrap gap-2">
            <Button 
              variant="outline" 
              onClick={handleExportSettings} 
              disabled={isExporting}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              {isExporting ? '导出中...' : '导出设置'}
            </Button>
            
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleImportSettings}
              className="hidden"
            />
            <Button 
              variant="outline" 
              onClick={() => fileInputRef.current?.click()}
              disabled={isImporting}
              className="gap-2"
            >
              <Upload className="h-4 w-4" />
              {isImporting ? '导入中...' : '导入设置'}
            </Button>
          </div>

          {/* 重置所有设置 */}
          <div className="pt-2 border-t">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2 text-destructive hover:text-destructive">
                  <RotateCcw className="h-4 w-4" />
                  {'重置所有设置为默认值'}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{'确认重置所有设置'}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {'这将把所有界面设置恢复为默认值，包括主题、颜色、动画等偏好设置。此操作不会影响您的登录状态。确定要继续吗？'}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                  <AlertDialogAction onClick={handleResetAllSettings}>
                    {'确认重置'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </Card>

      {/* 配置向导 */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">{'配置向导'}</h3>
        <div className="space-y-3 sm:space-y-4">
          <div className="space-y-2">
            <p className="text-xs sm:text-sm text-muted-foreground">
              {'重新进行初次配置，可同时重置登录密码，从密码设置步骤重新开始。'}
            </p>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" disabled={isResetting} className="gap-2">
                <RotateCcw className={cn('h-4 w-4', isResetting && 'animate-spin')} />
                {'重新进行初次配置'}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{'确认重新配置'}</AlertDialogTitle>
                <AlertDialogDescription>
                  {'这将带您重新进入初次配置向导。您可以重新设置系统的基础配置项。确定要继续吗？'}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <div className="flex items-start justify-between gap-4 rounded-md border p-4">
                <div className="space-y-2">
                  <Label htmlFor="reset-setup-password">{'同时重置登录密码'}</Label>
                  <p id="reset-setup-password-description" className="text-sm text-muted-foreground">
                    {'旧密码将立即失效，其他浏览器需要重新登录。当前浏览器会保持登录并进入密码设置页；新密码保存前使用临时凭证，重启后会重新生成。'}
                  </p>
                </div>
                <Switch
                  id="reset-setup-password"
                  checked={resetSetupPassword}
                  onCheckedChange={setResetSetupPassword}
                  aria-describedby="reset-setup-password-description"
                  disabled={isResetting}
                />
              </div>
              <AlertDialogFooter>
                <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                <AlertDialogAction onClick={handleResetSetup} disabled={isResetting}>
                  {'确认重置'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </Card>

      {/* 开发者工具 */}
      <div className="rounded-lg border border-dashed border-yellow-500/50 bg-yellow-500/5 p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-yellow-500" />
          {'开发者工具'}
        </h3>
        <div className="space-y-3 sm:space-y-4">
          <div className="space-y-2">
            <p className="text-xs sm:text-sm text-muted-foreground">
              {'以下功能仅供开发调试使用，可能会导致页面崩溃或异常。'}
            </p>
          </div>
          <div className="flex items-start justify-between gap-4 rounded-lg bg-muted/50 p-3 sm:p-4">
            <div className="min-w-0 space-y-1">
              <Label htmlFor="always-show-update-notice" className="text-sm font-medium">
                {'永远显示更新日志'}
              </Label>
              <p className="text-xs text-muted-foreground">
                {'开启后，每次进入 WebUI 都会依次弹出更新内容和插件兼容性提醒。刷新页面后生效。'}
              </p>
            </div>
            <Switch
              id="always-show-update-notice"
              checked={alwaysShowUpdateNotice}
              onCheckedChange={handleAlwaysShowUpdateNoticeChange}
              aria-label={'永远显示更新日志'}
            />
          </div>
          <div className="flex items-start justify-between gap-4 rounded-lg bg-muted/50 p-3 sm:p-4">
            <div className="min-w-0 space-y-1">
              <Label htmlFor="always-show-update-button" className="text-sm font-medium">
                {'永远显示更新按钮'}
              </Label>
              <p className="text-xs text-muted-foreground">
                {'开启后，无论是否检测到更新，始终显示右上角的主程序更新按钮。立即生效。'}
              </p>
            </div>
            <Switch
              id="always-show-update-button"
              checked={alwaysShowUpdateButton}
              onCheckedChange={(checked) => {
                setAlwaysShowUpdateButton(checked)
                setSetting('alwaysShowUpdateButton', checked)
              }}
              aria-label={'永远显示更新按钮'}
            />
          </div>
          <div className="flex items-start justify-between gap-4 rounded-lg bg-muted/50 p-3 sm:p-4">
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium">{'重置所有通知状态'}</p>
              <p className="text-xs text-muted-foreground">
                {'清除资讯已读记录、首页资讯条的关闭状态，以及各页面提示的关闭记录，相关通知会重新出现。不影响已完成的引导教程。'}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={handleResetNotificationStates} className="shrink-0 gap-2">
              <RotateCcw className="h-4 w-4" />
              {'重置'}
            </Button>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" className="gap-2">
                <AlertTriangle className="h-4 w-4" />
                {'触发测试错误'}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{'确认触发错误'}</AlertDialogTitle>
                <AlertDialogDescription>
                  {'这将手动触发一个 React 错误，用于测试错误边界组件的显示效果。页面将显示错误界面，您可以通过刷新页面或点击返回首页来恢复。'}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={() => setShouldThrowError(true)}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {'确认触发'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </div>
  )
}
