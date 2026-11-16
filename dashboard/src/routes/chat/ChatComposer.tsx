import { ImagePlus, Paperclip, Send, X } from 'lucide-react'
import { useRef } from 'react'


import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { UserEmojiItem } from '@/lib/user-emoji-api'
import { MessageComposerFrame } from '@/components/ui/conversation'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

import type { ChatImageAttachment } from './types'
import { ChatUserIdentity } from './ChatUserIdentity'
import { UserEmojiManager } from './UserEmojiManager'

interface ChatComposerProps {
  files?: Array<{ file_ref: string; name: string }>
  onAddFiles?: (files: FileList) => void
  onRemoveFile?: (ref: string) => void
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onAddImages: (files: FileList) => void
  onRemoveImage: (id: string) => void
  onSendEmoji: (item: UserEmojiItem) => Promise<void>
  disabled: boolean
  images: ChatImageAttachment[]
  isConnected: boolean
  userId: string
  userName: string
  userAvatarVersion?: number
  isUploadingUserAvatar: boolean
  onUpdateUserAvatar: (file: File) => Promise<void>
  onUpdateUserName: (name: string) => void
}

/**
 * 聊天输入区：自适应高度的输入框 + 独立工具栏，带快捷键提示。
 */
export function ChatComposer({
  files = [],
  onAddFiles,
  onRemoveFile,
  value,
  onChange,
  onSend,
  onAddImages,
  onRemoveImage,
  onSendEmoji,
  disabled,
  images,
  isConnected,
  userId,
  userName,
  userAvatarVersion,
  isUploadingUserAvatar,
  onUpdateUserAvatar,
  onUpdateUserName,
}: ChatComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (!disabled) onSend()
    }
  }

  const canSend = !disabled && (value.trim().length > 0 || images.length > 0 || files.length > 0)

  return (
    <MessageComposerFrame
      attachments={
        images.length > 0 && (
          <div className="flex gap-2 overflow-x-auto p-3">
            {images.map((image) => (
              <div key={image.id} className="relative h-16 w-16 shrink-0">
                <img
                  src={image.data_url}
                  alt={image.name || '图片'}
                  className="h-full w-full object-cover"
                />
                <Button
                  type="button"
                  size="icon-xs"
                  variant="outline"
                  className="absolute top-0 right-0"
                  aria-label={'移除图片'}
                  onClick={() => onRemoveImage(image.id)}
                >
                  <X />
                </Button>
              </div>
            ))}
          </div>
        )
      }
      tools={
        <>
          {onAddFiles && <>
            <input ref={attachmentInputRef} className="hidden" type="file" multiple disabled={disabled}
              onChange={e => { if (e.target.files) onAddFiles(e.target.files); e.currentTarget.value = '' }} />
            <Button type="button" size="icon-sm" variant="ghost" disabled={disabled} aria-label={'上传文件'}
              title={'上传文件'} onClick={() => attachmentInputRef.current?.click()}><Paperclip /></Button>
            {files.map(file => <Button key={file.file_ref} type="button" variant="outline" size="sm"
              onClick={() => onRemoveFile?.(file.file_ref)} title={'移除待发送附件（原件仍保存在文件管理中）'}>
              <span className="max-w-32 truncate">{file.name}</span><X />
            </Button>)}
          </>}
          <input
            ref={fileInputRef}
            className="hidden"
            type="file"
            accept="image/*"
            multiple
            disabled={!isConnected}
            onChange={(e) => {
              if (e.target.files) onAddImages(e.target.files)
              e.currentTarget.value = ''
            }}
          />
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            disabled={!isConnected}
            aria-label={'添加图片'}
            title={'添加图片'}
            onClick={() => fileInputRef.current?.click()}
          >
            <ImagePlus />
          </Button>
          <UserEmojiManager disabled={!isConnected} userId={userId} onSendEmoji={onSendEmoji} />
          <Popover>
            <PopoverTrigger asChild>
              <Button type="button" variant="outline" size="sm">
                以「{userName}」发送
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-auto">
              <ChatUserIdentity
                userId={userId}
                userName={userName}
                userAvatarVersion={userAvatarVersion}
                isUploadingUserAvatar={isUploadingUserAvatar}
                onUpdateUserAvatar={onUpdateUserAvatar}
                onUpdateUserName={onUpdateUserName}
              />
            </PopoverContent>
          </Popover>
        </>
      }
      hint={'Enter 发送 · Shift + Enter 换行'}
      submit={
        <Button
          type="button"
          size="sm"
          disabled={!canSend}
          onClick={onSend}
          aria-label={'发送消息'}
        >
          <Send />
          {'发送消息'}
        </Button>
      }
    >
      <Textarea
        aria-label={'输入消息...'}
        autoResize
        variant="composer"
        disabled={!isConnected}
        maxHeight={160}
        minHeight={56}
        placeholder={isConnected ? '输入消息...' : '等待连接...'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
    </MessageComposerFrame>
  )
}
