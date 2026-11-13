import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MYLIFE_PLUGIN_ID } from '@/lib/mylife'
import { getInstalledPlugins } from '@/lib/plugin-api'

import { PluginConfigEditor } from './plugin-config'

export function MyLifePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: ['mylife', 'plugin'],
    queryFn: () => getInstalledPlugins({ includeBuiltin: true }),
    select: (plugins) => plugins.find((plugin) => plugin.id === MYLIFE_PLUGIN_ID),
  })

  if (query.isPending) return <p className="p-6" role="status">{t('pluginWebUI.loading')}</p>
  if (query.error || !query.data) {
    return (
      <div className="space-y-4 p-6">
        <Alert variant="destructive">
          <AlertDescription>{query.error?.message ?? t('mylife.unavailable')}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => void query.refetch()}>
          {t('pluginWebUI.refresh')}
        </Button>
      </div>
    )
  }

  return (
    <ScrollArea
      className="h-full max-lg:h-auto max-lg:overflow-visible max-lg:[&>[data-dashboard-scrollbar]]:hidden"
      viewportClassName="max-lg:h-auto max-lg:!overflow-visible max-lg:overscroll-auto"
      scrollbars="vertical"
    >
      <div className="px-5 pt-0 pb-4 sm:px-7 sm:pb-6 lg:px-8">
        <PluginConfigEditor
          plugin={query.data}
          initialTab={new URLSearchParams(window.location.search).get('tab') ?? undefined}
          onBack={() => void navigate({ to: '/manage' })}
        />
      </div>
    </ScrollArea>
  )
}
