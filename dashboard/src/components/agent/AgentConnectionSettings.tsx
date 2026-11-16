

import type { FieldHookComponentProps } from '@/lib/field-hooks'

export function AgentConnectionSettings({ children, parentValues }: FieldHookComponentProps) {
  return <div className="space-y-3">
    {children}
    {parentValues?.connection === 'dsh' && <details className="rounded-lg border p-3 text-sm">
      <summary className="cursor-pointer font-medium">{'dsh 快速连接步骤'}</summary>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-muted-foreground">
        <li>{'尚未安装 dsh 时执行：'} <code className="select-all">npm install -g @deepseek-ai/dsh</code></li>
        <li>{'打开 dsh 设置模型和 API Key（已配置可跳过）：'} <code className="select-all">dsh web</code></li>
        <li>{'选择 dsh CLI 连接方式，启用并保存，然后在“独立 Agent”页面发送任务。找不到程序时，将 ACP 启动程序填写为 dsh.cmd 的绝对路径。'}</li>
      </ol>
      <p className="mt-3 text-muted-foreground">{'预设自动启动：'} <code>dsh --profile acp</code></p>
    </details>}
    {parentValues?.connection === 'dsh_desktop' && <details open className="rounded-lg border p-3 text-sm">
      <summary className="cursor-pointer font-medium">{'连接 dsh Desktop'}</summary>
      <p className="mt-3 text-muted-foreground">{'使用 Desktop 自带的 dsh 命令安装桥接插件（Desktop 0.2.1-rc.2 起）：'}</p>
      <code className="mt-2 block select-all overflow-x-auto text-xs">dsh plugin --profile desktop add https://github.com/SengokuCola/dsh-maibot-bridge/releases/download/v0.1.1/dsh-maibot-bridge-0.1.1.tgz</code>
      <p className="mt-3 text-muted-foreground">{'启动或重启 Desktop，桥接文件通常留空，模型选项留空沿用 Desktop 配置。麦麦的任务会出现在 Desktop 的“麦麦”会话中；退出麦麦不会退出 Desktop。'}</p>
    </details>}
  </div>
}

export function AgentCustomArgs({ children, parentValues }: FieldHookComponentProps) {
  return parentValues?.connection === 'custom' ? children : null
}

export function AgentACPField({ children, parentValues, fieldPath }: FieldHookComponentProps) {
  if (parentValues?.connection === 'dsh_desktop' && ['agent.acp_command', 'agent.acp_env'].includes(fieldPath)) return null
  return children
}

export function AgentDesktopField({ children, parentValues }: FieldHookComponentProps) {
  return parentValues?.connection === 'dsh_desktop' ? children : null
}
