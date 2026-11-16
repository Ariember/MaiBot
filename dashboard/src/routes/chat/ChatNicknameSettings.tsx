import type { ReactNode } from 'react'
import { useId, useState } from 'react'


import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export function ChatNicknameSettings({
  userName,
  onUpdateUserName,
  trigger,
}: {
  userName: string
  onUpdateUserName: (name: string) => void
  trigger: ReactNode
}) {
  const inputId = useId()
  const [open, setOpen] = useState(false)
  const [draftName, setDraftName] = useState(userName)

  const save = () => {
    onUpdateUserName(draftName.trim() || '人类')
    setOpen(false)
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) setDraftName(userName)
        setOpen(nextOpen)
      }}
    >
      <PopoverTrigger asChild>
        {trigger}
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="w-64 space-y-3">
        <Label htmlFor={inputId}>{'修改昵称'}</Label>
        <Input
          id={inputId}
          value={draftName}
          maxLength={64}
          placeholder={'输入昵称'}
          onChange={(event) => setDraftName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
              event.preventDefault()
              save()
            }
          }}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
            {'取消'}
          </Button>
          <Button type="button" size="sm" onClick={save}>
            {'保存'}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
