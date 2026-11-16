import { Fragment, type ReactNode } from 'react'
import { ChevronDown, RefreshCw } from 'lucide-react'


import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SectionPanel } from '@/components/ui/management'
import { OrderControls } from '@/components/ui/order-controls'
import { DataPanel, PageFrame } from '@/components/ui/surface'
import { Switch } from '@/components/ui/switch'
import { orderedWorkspaceExtensions, type WebUIExtension } from '@/lib/plugin-webui'
import { MAX_VISIBLE_PLUGIN_TABS, splitWorkspaceTabs } from '@/lib/workspace-tabs'

export interface PluginPagePreferences {
  hidden: string[]
  order: string[]
  workspaceOrder?: string[]
}

/** 正式设置与预览共用同一个受控页面，数据加载和持久化留给调用方。 */
export function PluginPagesSettings({
  extensions,
  preferences,
  loading = false,
  error,
  onRefresh,
  onPreferencesChange,
  renderPageLink,
}: {
  extensions: WebUIExtension[]
  preferences: PluginPagePreferences
  loading?: boolean
  error?: string | null
  onRefresh: () => void
  onPreferencesChange: (preferences: PluginPagePreferences) => void
  renderPageLink: (extension: WebUIExtension, page: WebUIExtension['pages'][number]) => ReactNode
}) {
  // 兼容旧版独立保存的顶栏顺序；未提供顶栏入口的插件排在后面，仍可管理。
  const workspaces = orderedWorkspaceExtensions(
    extensions,
    preferences.workspaceOrder ?? preferences.order
  )
  const workspaceIds = new Set(workspaces.map((item) => item.plugin_id))
  const sidebar = extensions
    .filter((item) => !workspaceIds.has(item.plugin_id))
    .sort((a, b) => {
      const rank = (id: string) => {
        const index = preferences.order.indexOf(id)
        return index < 0 ? preferences.order.length : index
      }
      return rank(a.plugin_id) - rank(b.plugin_id) || a.plugin_id.localeCompare(b.plugin_id)
    })
  const ordered = [...workspaces, ...sidebar]
  const { visible, overflow } = splitWorkspaceTabs(
    workspaces.filter((item) => !preferences.hidden.includes(item.plugin_id))
  )
  const move = (extension: WebUIExtension, delta: -1 | 1) => {
    const group = workspaceIds.has(extension.plugin_id) ? workspaces : sidebar
    const index = group.indexOf(extension)
    const next = [...group]
    ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
    const nextWorkspaces = group === workspaces ? next : workspaces
    const nextSidebar = group === sidebar ? next : sidebar
    onPreferencesChange({
      ...preferences,
      order: [...nextWorkspaces, ...nextSidebar].map((item) => item.plugin_id),
      workspaceOrder: nextWorkspaces.map((item) => item.plugin_id),
    })
  }
  return (
    <section
      id="webui-extensions"
      className="plugin-pages-settings"
      aria-labelledby="webui-extensions-title"
    >
      <header className="plugin-pages-heading">
        <div>
          <h2 id="webui-extensions-title">{'插件页面'}</h2>
          <p>{'决定哪些插件页面出现在顶栏、按什么顺序。只保存在当前浏览器，不影响插件权限。'}</p>
        </div>
        <Button variant="outline" disabled={loading} onClick={onRefresh}>
          <RefreshCw className={loading ? 'animate-spin' : undefined} />
          {'刷新'}
        </Button>
      </header>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <PageFrame className="p-4">
        <h3 className="text-muted-foreground mb-3 text-sm">{'顶栏预览'}</h3>
        <DataPanel className="plugin-pages-preview">
          <div className="plugin-pages-preview-tabs" aria-label={'顶栏预览'}>
            <Button variant="outline" size="sm" aria-pressed tabIndex={-1}>
              {'麦麦'}
            </Button>
            <Button variant="outline" size="sm" tabIndex={-1}>
              {'日志'}
            </Button>
            {visible.map((item) => (
              <Button
                key={item.plugin_id}
                variant="outline"
                size="sm"
                className="plugin-pages-preview-slot"
                tabIndex={-1}
              >
                {item.workspace_title ?? item.plugin_id}
              </Button>
            ))}
            {overflow.length > 0 && (
              <Button variant="outline" size="sm" tabIndex={-1}>
                {'更多'}
                <Badge variant="secondary">{overflow.length}</Badge>
              </Button>
            )}
          </div>
          <p className="text-muted-foreground text-xs">
            {`顶栏最多放 ${MAX_VISIBLE_PLUGIN_TABS} 个，其余进入「更多」`}
          </p>
        </DataPanel>
      </PageFrame>
      <SectionPanel
        title={'排序与显示'}
        description={`${ordered.length} 个插件`}
      >
        {loading && <p role="status">{'加载中…'}</p>}
        {!loading && ordered.length === 0 && (
          <p className="text-muted-foreground py-8 text-center">{'暂无数据'}</p>
        )}
        {ordered.length > 0 && (
          <DataPanel padding="none">
            <ol className="plugin-pages-list">
              {ordered.map((extension, index) => {
                const title = extension.workspace_title ?? extension.plugin_id
                const shown = !preferences.hidden.includes(extension.plugin_id)
                const isWorkspace = workspaceIds.has(extension.plugin_id)
                const group = isWorkspace ? workspaces : sidebar
                const placement = !shown
                  ? "已隐藏"
                  : visible.includes(extension)
                    ? "顶栏"
                    : isWorkspace
                      ? "更多菜单"
                      : "侧栏"
                return (
                  <Fragment key={extension.plugin_id}>
                    {(extension === overflow[0] || extension === sidebar[0]) && (
                      <li className="plugin-pages-group-label">
                        <ChevronDown size={14} />
                        {(extension === sidebar[0] ? '以下插件仅提供侧栏页面' : '以下进入「更多」菜单')}
                      </li>
                    )}
                    <li className="plugin-pages-row" data-hidden={!shown}>
                      <Badge variant="outline" className="plugin-pages-ordinal">
                        {index + 1}
                      </Badge>
                      <div className="plugin-pages-details">
                        <div className="plugin-pages-title">
                          <h3>{title}</h3>
                          <code>{extension.plugin_id}</code>
                          <Badge
                            variant={shown && visible.includes(extension) ? 'default' : 'outline'}
                          >
                            {placement}
                          </Badge>
                        </div>
                        <div className="plugin-pages-links">
                          {extension.pages.map((page) => (
                            <Fragment key={page.id}>
                              {shown ? (
                                renderPageLink(extension, page)
                              ) : (
                                <Button variant="outline" size="xs" disabled>
                                  {page.title}
                                </Button>
                              )}
                            </Fragment>
                          ))}
                        </div>
                        {extension.compatibility_error && (
                          <p className="text-destructive text-sm">
                            {extension.compatibility_error}
                          </p>
                        )}
                      </div>
                      <div className="plugin-pages-actions">
                        <OrderControls
                          label={title}
                          index={group.indexOf(extension)}
                          count={group.length}
                          upLabel={'上移'}
                          downLabel={'下移'}
                          onMove={(delta) => move(extension, delta)}
                        />
                        <label className="plugin-pages-visibility">
                          <span>{'显示'}</span>
                          <Switch
                            aria-label={`显示 ${title} 页面`}
                            checked={shown}
                            onCheckedChange={(checked) =>
                              onPreferencesChange({
                                ...preferences,
                                hidden: checked
                                  ? preferences.hidden.filter((id) => id !== extension.plugin_id)
                                  : [...preferences.hidden, extension.plugin_id],
                              })
                            }
                          />
                        </label>
                      </div>
                    </li>
                  </Fragment>
                )
              })}
            </ol>
          </DataPanel>
        )}
      </SectionPanel>
    </section>
  )
}
