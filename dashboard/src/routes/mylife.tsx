import { useQuery } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import {
  Brain,
  Check,
  ChevronDown,
  Globe,
  Heart,
  Loader2,
  Save,
  Settings2,
  Users,
} from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CodeEditor } from '@/components/CodeEditor'
import { SchemaConfigField } from '@/components/SchemaConfigField'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { SwitchField } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'
import { MYLIFE_PLUGIN_ID } from '@/lib/mylife'
import {
  getPluginConfigBundle,
  resetPluginConfig,
  updatePluginConfig,
  updatePluginConfigRaw,
} from '@/lib/plugin-api'
import type { ConfigFieldSchema, ConfigSectionSchema, PluginConfigBundle } from '@/lib/plugin-api'
import { refreshPluginWebUI } from '@/lib/plugin-webui'
import { resolveLocalizedText } from '@/lib/schema-config-label'
import { cn } from '@/lib/utils'

const settingGroups = [
  { id: 'general', icon: Settings2, sections: ['environment', 'plugin'] },
  { id: 'private', icon: Heart, sections: ['users', 'proactive'] },
  { id: 'group', icon: Users, sections: ['group'] },
  { id: 'memory', icon: Brain, sections: ['memory'] },
  { id: 'network', icon: Globe, sections: ['network'] },
  { id: 'models', icon: Settings2, sections: ['models', 'usage'] },
]

const commonFields: Record<string, string[]> = {
  plugin: ['admin_user_ids'],
  environment: ['weather_refresh_minutes'],
  users: ['profiles'],
  proactive: ['enabled', 'work_start', 'work_end', 'recent_user_silence_minutes'],
  group: [
    'profiles',
    'gate_enabled',
    'reply_probability',
    'work_start',
    'work_end',
    'relay_enabled',
  ],
  memory: ['enabled', 'important_dates_enabled', 'date_reminder_lead_days'],
  network: [
    'enabled',
    'tool_enabled',
    'news_enabled',
    'news_sources',
    'news_daily_max',
    'search_enabled',
    'search_daily_max',
    'proactive_share_enabled',
  ],
  models: ['fast_task', 'reasoning_task', 'max_output_tokens'],
  usage: ['enabled', 'retention_days'],
}

function MyLifeSection({
  name,
  section,
  values,
  onChange,
}: {
  name: string
  section: ConfigSectionSchema
  values: Record<string, unknown>
  onChange: (field: string, value: unknown) => void
}) {
  const { t, i18n } = useTranslation()
  const language = i18n.resolvedLanguage || i18n.language || 'zh'
  const fields = Object.entries(section.fields)
    .filter(([, field]) => !field.hidden)
    .sort(([, a], [, b]) => a.order - b.order)
  const basic = fields.filter(([key]) => commonFields[name]?.includes(key))
  const advanced = fields.filter(([key]) => !commonFields[name]?.includes(key))
  const renderFields = (entries: [string, ConfigFieldSchema][]) => (
    <div className="grid min-w-0 gap-x-6 gap-y-6 md:grid-cols-2">
      {entries.map(([key, field]) => (
        <div
          key={key}
          className={cn(
            'min-w-0',
            ['list', 'textarea', 'slider'].includes(field.ui_type) && 'md:col-span-2'
          )}
        >
          <SchemaConfigField
            field={field}
            value={values[key]}
            onChange={(value) => onChange(key, value)}
          />
        </div>
      ))}
    </div>
  )
  return (
    <Card className="min-w-0">
      <CardHeader className="border-border/50 border-b">
        <CardTitle className="text-base">
          {name === 'plugin'
            ? t('mylife.administrators')
            : resolveLocalizedText(section.title, language, name, section.i18n, 'title')}
        </CardTitle>
        <CardDescription>
          {name === 'plugin'
            ? t('mylife.administratorsHint')
            : resolveLocalizedText(section.description, language, '', section.i18n, 'description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 pt-5">
        {basic.length > 0 && renderFields(basic)}
        {advanced.length > 0 && (
          <Collapsible className={cn(basic.length > 0 && 'border-border/50 border-t pt-4')}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="group text-muted-foreground -ml-2 gap-2">
                <ChevronDown
                  className="h-4 w-4 transition-transform group-data-[state=open]:rotate-180"
                  aria-hidden="true"
                />
                {t('mylife.advanced')}
                <Badge variant="secondary">{advanced.length}</Badge>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-5">{renderFields(advanced)}</CollapsibleContent>
          </Collapsible>
        )}
      </CardContent>
    </Card>
  )
}

function MyLifeSettings({ bundle }: { bundle: PluginConfigBundle }) {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [baseline, setBaseline] = useState(bundle)
  const [config, setConfig] = useState(bundle.config)
  const [rawConfig, setRawConfig] = useState(bundle.rawConfig)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [resetOpen, setResetOpen] = useState(false)
  const [activeTab, setActiveTab] = useState(() => {
    const tab = new URLSearchParams(window.location.search).get('tab')
    return (
      settingGroups.find((group) => group.id === tab || group.sections.includes(tab ?? ''))?.id ??
      'general'
    )
  })
  const repairMode = Boolean(baseline.configError)
  const activeGroup = settingGroups.find((group) => group.id === activeTab) ?? settingGroups[0]
  const hasChanges = repairMode
    ? rawConfig !== baseline.rawConfig
    : JSON.stringify(config) !== JSON.stringify(baseline.config)
  const blocker = useBlocker({
    shouldBlockFn: () => hasChanges || saving,
    enableBeforeUnload: hasChanges || saving,
    withResolver: true,
  })

  function changeField(section: string, field: string, value: unknown) {
    setConfig((current) => ({
      ...current,
      [section]: { ...(current[section] as Record<string, unknown>), [field]: value },
    }))
  }

  function changeTab(tab: string) {
    setActiveTab(tab)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', tab)
    window.history.replaceState(window.history.state, '', url)
  }

  function applyBundle(next: PluginConfigBundle) {
    setBaseline(next)
    setConfig(next.config)
    setRawConfig(next.rawConfig)
  }

  async function save(): Promise<boolean> {
    setSaving(true)
    setSaveError('')
    try {
      if (repairMode) {
        await updatePluginConfigRaw(MYLIFE_PLUGIN_ID, rawConfig)
        applyBundle(await getPluginConfigBundle(MYLIFE_PLUGIN_ID))
      } else {
        await updatePluginConfig(MYLIFE_PLUGIN_ID, config)
        setBaseline((current) => ({ ...current, config }))
      }
      toast({ title: t('mylife.saveSuccess'), description: t('mylife.saveSuccessHint') })
      void refreshPluginWebUI(true)
      return true
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : t('mylife.saveError'))
      return false
    } finally {
      setSaving(false)
    }
  }

  async function reset() {
    setSaving(true)
    setSaveError('')
    try {
      await resetPluginConfig(MYLIFE_PLUGIN_ID)
      applyBundle(await getPluginConfigBundle(MYLIFE_PLUGIN_ID))
      setResetOpen(false)
      toast({ title: t('mylife.resetSuccess') })
      void refreshPluginWebUI(true)
    } catch (error) {
      setResetOpen(false)
      setSaveError(error instanceof Error ? error.message : t('mylife.resetError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ScrollArea
      className="h-full min-w-0 max-lg:h-auto max-lg:overflow-visible max-lg:[&>[data-dashboard-scrollbar]]:hidden"
      viewportClassName="max-lg:h-auto max-lg:!overflow-visible max-lg:overscroll-auto"
      scrollbars="vertical"
    >
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
        <h1 className="sr-only">{t('mylife.title')}</h1>
        <header
          data-config-section-navigation="true"
          className="bg-background sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 py-2"
        >
          {!repairMode && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  disabled={saving}
                  className="gap-2 bg-none! text-base font-semibold"
                  aria-label={t('mylife.chooseGroup')}
                >
                  {t(`mylife.groups.${activeGroup.id}.title`)}
                  <ChevronDown className="h-4 w-4" aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="min-w-52 space-y-1 p-2">
                {settingGroups.map(({ id, icon: Icon }) => (
                  <DropdownMenuItem
                    key={id}
                    onSelect={() => changeTab(id)}
                    className="cursor-pointer gap-2 px-3 py-2 text-base"
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    {t(`mylife.groups.${id}.title`)}
                    {activeTab === id && <Check className="ml-auto h-4 w-4" aria-hidden="true" />}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto">
            <span className="text-muted-foreground mr-auto text-xs sm:mr-2" role="status">
              {t(hasChanges ? 'mylife.unsaved' : 'mylife.saved')}
            </span>
            {!repairMode && (
              <>
                <SwitchField
                  id="mylife-enabled"
                  label={t('mylife.enable')}
                  aria-describedby="mylife-enable-hint"
                  checked={Boolean((config.plugin as Record<string, unknown>)?.enabled)}
                  onCheckedChange={(enabled) => changeField('plugin', 'enabled', enabled)}
                  disabled={saving}
                />
                <p id="mylife-enable-hint" className="sr-only">
                  {t('mylife.enableHint')}
                </p>
              </>
            )}
            <Button
              variant="outline"
              disabled={!hasChanges || saving}
              onClick={() => {
                applyBundle(baseline)
                setSaveError('')
              }}
            >
              {t('mylife.discard')}
            </Button>
            <Button disabled={!hasChanges || saving} onClick={() => void save()}>
              {saving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              {t(saving ? 'mylife.saving' : 'mylife.save')}
            </Button>
          </div>
        </header>
        {saveError && (
          <Alert variant="destructive">
            <AlertDescription>{saveError}</AlertDescription>
          </Alert>
        )}
        {repairMode ? (
          <div className="space-y-4">
            <Alert variant="destructive">
              <AlertTitle>{t('mylife.repair')}</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{baseline.configError}</p>
                <p>{t('mylife.repairHint')}</p>
              </AlertDescription>
            </Alert>
            <CodeEditor
              language="toml"
              value={rawConfig}
              onChange={setRawConfig}
              readOnly={saving}
              height="60vh"
            />
          </div>
        ) : (
          <fieldset disabled={saving} className="min-w-0 space-y-6">
            <section
              aria-label={t(`mylife.groups.${activeGroup.id}.title`)}
              className="min-w-0 space-y-5"
            >
              <div className="space-y-1">
                <h2 className="text-lg font-semibold">
                  {t(`mylife.groups.${activeGroup.id}.title`)}
                </h2>
                <p className="text-muted-foreground text-sm">
                  {t(`mylife.groups.${activeGroup.id}.description`)}
                </p>
              </div>
              {activeGroup.sections.map((name) => {
                const section = baseline.schema?.sections[name]
                return (
                  section && (
                    <MyLifeSection
                      key={name}
                      name={name}
                      section={section}
                      values={(config[name] as Record<string, unknown>) ?? {}}
                      onChange={(field, value) => changeField(name, field, value)}
                    />
                  )
                )
              })}
              {activeGroup.id === 'general' && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  onClick={() => setResetOpen(true)}
                >
                  {t('mylife.reset')}
                </Button>
              )}
            </section>
          </fieldset>
        )}
      </div>
      <Dialog
        open={blocker.status === 'blocked'}
        onOpenChange={(open) => {
          if (!open && !saving) blocker.reset?.()
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('mylife.leaveTitle')}</DialogTitle>
            <DialogDescription>{t('mylife.leaveHint')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={saving} onClick={() => blocker.reset?.()}>
              {t('mylife.cancel')}
            </Button>
            <Button variant="outline" disabled={saving} onClick={() => blocker.proceed?.()}>
              {t('mylife.leave')}
            </Button>
            <Button
              disabled={saving}
              onClick={async () => {
                if (await save()) blocker.proceed?.()
              }}
            >
              {t('mylife.saveAndLeave')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={resetOpen}
        onOpenChange={(open) => {
          if (!saving) setResetOpen(open)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('mylife.resetTitle')}</DialogTitle>
            <DialogDescription>{t('mylife.resetHint')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={saving} onClick={() => setResetOpen(false)}>
              {t('mylife.cancel')}
            </Button>
            <Button variant="destructive" disabled={saving} onClick={() => void reset()}>
              {t('mylife.reset')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ScrollArea>
  )
}

export function MyLifePage() {
  const { t } = useTranslation()
  const query = useQuery({
    queryKey: ['mylife', 'config'],
    queryFn: () => getPluginConfigBundle(MYLIFE_PLUGIN_ID),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  if (query.isPending || !query.isFetchedAfterMount)
    return (
      <p className="p-6" role="status">
        {t('mylife.loading')}
      </p>
    )
  if (query.error) {
    return (
      <div className="space-y-4 p-6">
        <Alert variant="destructive">
          <AlertTitle>{t('mylife.loadError')}</AlertTitle>
          <AlertDescription>{query.error.message}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => void query.refetch()}>
          {t('mylife.retry')}
        </Button>
      </div>
    )
  }
  return <MyLifeSettings bundle={query.data} />
}
