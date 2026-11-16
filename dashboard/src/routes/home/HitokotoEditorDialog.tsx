import type { CSSProperties } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'


import { Button } from '@/components/ui/button'
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { generateId } from '@/lib/id'

import type { CustomHitokoto, HitokotoSettings } from './hooks/useMaibotVersion'

interface HitokotoEditorDialogProps {
  initialSettings: HitokotoSettings
  onOpenChange: (open: boolean) => void
  onSave: (settings: HitokotoSettings) => Promise<void>
}

function createCustomHitokoto(): CustomHitokoto {
  return {
    id: generateId(),
    content: '',
    source: '',
  }
}

export function HitokotoEditorDialog({
  initialSettings,
  onOpenChange,
  onSave,
}: HitokotoEditorDialogProps) {
  const [settings, setSettings] = useState<HitokotoSettings>(() => ({
    defaultEnabled: initialSettings.defaultEnabled,
    customItems: initialSettings.customItems.map((item) => ({ ...item })),
  }))
  const [isSaving, setIsSaving] = useState(false)

  const updateItem = (id: string, patch: Partial<CustomHitokoto>) => {
    setSettings((current) => ({
      ...current,
      customItems: current.customItems.map((item) =>
        item.id === id ? { ...item, ...patch } : item
      ),
    }))
  }

  const removeItem = (id: string) => {
    setSettings((current) => ({
      ...current,
      customItems: current.customItems.filter((item) => item.id !== id),
    }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onSave(settings)
      onOpenChange(false)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent style={{ '--dialog-width': '44rem' } as CSSProperties}>
        <DialogHeader>
          <DialogTitle>{'编辑一言'}</DialogTitle>
          <DialogDescription>{'管理首页展示的一言来源与自定义内容。'}</DialogDescription>
        </DialogHeader>
        <DialogBody viewportClassName="max-h-[62vh]">
          <div className="space-y-5 pr-1">
            <div className="bg-muted/25 flex items-center justify-between gap-4 rounded-lg border p-4">
              <div className="min-w-0">
                <div className="font-semibold">{'使用默认一言'}</div>
                <div className="text-muted-foreground mt-1 text-sm">
                  {'开启后会从一言接口获取内容，并与自定义内容轮换展示。'}
                </div>
              </div>
              <Switch
                checked={settings.defaultEnabled}
                onCheckedChange={(checked) =>
                  setSettings((current) => ({ ...current, defaultEnabled: checked }))
                }
                aria-label={'使用默认一言'}
              />
            </div>

            <section className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{'自定义内容'}</h3>
                  <p className="text-muted-foreground mt-0.5 text-sm">
                    {'可添加多条内容，出处可以留空。'}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 gap-1.5"
                  onClick={() =>
                    setSettings((current) => ({
                      ...current,
                      customItems: [...current.customItems, createCustomHitokoto()],
                    }))
                  }
                >
                  <Plus className="h-4 w-4" />
                  {'新增内容'}
                </Button>
              </div>

              {settings.customItems.length === 0 ? (
                <button
                  type="button"
                  className="text-muted-foreground hover:border-primary/35 hover:bg-accent/20 flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-sm transition-colors"
                  onClick={() =>
                    setSettings((current) => ({
                      ...current,
                      customItems: [createCustomHitokoto()],
                    }))
                  }
                >
                  <Plus className="h-5 w-5" />
                  <span>{'还没有自定义内容，点击添加第一条'}</span>
                </button>
              ) : (
                <div className="space-y-3">
                  {settings.customItems.map((item, index) => (
                    <div key={item.id} className="rounded-lg border p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-muted-foreground text-xs font-semibold">
                          {`内容 ${index + 1}`}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-muted-foreground hover:text-destructive h-7 w-7"
                          aria-label={`删除内容 ${index + 1}`}
                          onClick={() => removeItem(item.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <Textarea
                        value={item.content}
                        minHeight={72}
                        maxHeight={160}
                        placeholder={'输入想在首页展示的内容'}
                        aria-label={`内容 ${index + 1} 正文`}
                        onChange={(event) => updateItem(item.id, { content: event.target.value })}
                      />
                      <Input
                        value={item.source}
                        className="mt-2"
                        placeholder={'出处（可选）'}
                        aria-label={`内容 ${index + 1} 出处`}
                        onChange={(event) => updateItem(item.id, { source: event.target.value })}
                      />
                    </div>
                  ))}
                </div>
              )}

              {!settings.defaultEnabled && settings.customItems.length === 0 && (
                <p className="text-muted-foreground rounded-lg border border-dashed px-3 py-2 text-xs">
                  {'默认一言已停用且自定义列表为空，首页一言区域将保持留白。'}
                </p>
              )}
            </section>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={isSaving} onClick={() => onOpenChange(false)}>
            {'取消'}
          </Button>
          <Button disabled={isSaving} onClick={() => void handleSave()}>
            {isSaving ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
