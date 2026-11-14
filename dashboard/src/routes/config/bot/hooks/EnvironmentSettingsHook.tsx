import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronsUpDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { FieldHookComponent } from '@/lib/field-hooks'
import { backendApi } from '@/lib/http'

interface EnvironmentSettings {
  city: string
  city_id: number
  timezone: string
}

interface CityOption {
  id: number
  name: string
  admin1?: string
  admin2?: string
  country?: string
  timezone?: string
}

const commonCities = ['上海', '北京', '广州', '深圳', '杭州', '成都', '东京', '纽约']
const apiRoot = '/api/webui/config/environment'

export const EnvironmentSettingsHook: FieldHookComponent = ({ value, onChange }) => {
  const settings: EnvironmentSettings = {
    city: 'Shanghai',
    city_id: 0,
    timezone: 'Asia/Shanghai',
    ...(value as Partial<EnvironmentSettings> | undefined),
  }
  const [cityOpen, setCityOpen] = useState(false)
  const [timezoneOpen, setTimezoneOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search])

  const cities = useQuery({
    queryKey: ['environment-cities', query],
    queryFn: ({ signal }) => backendApi.get<{ cities: CityOption[] }>(`${apiRoot}/cities`, {
      query: { name: query },
      signal,
      errorMessage: '搜索城市失败',
    }),
    enabled: cityOpen && query.length >= 2,
  })
  const timezones = useQuery({
    queryKey: ['environment-timezones'],
    queryFn: ({ signal }) => backendApi.get<{ timezones: string[] }>(`${apiRoot}/timezones`, { signal }),
    enabled: timezoneOpen,
    staleTime: Infinity,
  })

  const setCityPickerOpen = (open: boolean) => {
    setCityOpen(open)
    if (open) {
      const currentCity = settings.city.split(' · ')[0] || 'Shanghai'
      setSearch(currentCity)
      setQuery(currentCity)
    }
  }

  const selectCity = (city: CityOption) => {
    onChange?.({
      ...settings,
      city: Array.from(new Set([city.name, city.admin2, city.admin1, city.country].filter(Boolean))).join(' · '),
      city_id: city.id,
      timezone: city.timezone || settings.timezone,
    })
    setCityOpen(false)
  }

  const timezoneOptions = Array.from(new Set([settings.timezone, ...(timezones.data?.timezones ?? [])]))

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle className="text-base">地区与时间</CardTitle>
        <CardDescription>设置麦麦的全局所在地和时间基准，麦日常的天气与日程使用此配置。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2" data-config-field-path="environment.city">
          <Label htmlFor="environment-city">地区 / 城市</Label>
          <Popover open={cityOpen} onOpenChange={setCityPickerOpen}>
            <PopoverTrigger asChild>
              <Button id="environment-city" type="button" variant="outline" role="combobox" aria-expanded={cityOpen} className="w-full justify-between">
                <span className="truncate">{settings.city || '选择城市'}</span>
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="max-w-[calc(100vw-2rem)] p-0" align="start" style={{ width: 'var(--radix-popover-trigger-width)' }}>
              <Command shouldFilter={false}>
                <CommandInput placeholder="搜索城市名称，至少两个字符" value={search} onValueChange={setSearch} />
                <div className="flex flex-wrap gap-1 border-b p-2">
                  {commonCities.map((city) => (
                    <Button key={city} type="button" variant="ghost" size="sm" onClick={() => { setSearch(city); setQuery(city) }}>{city}</Button>
                  ))}
                </div>
                <CommandList>
                  {search.trim().length < 2 ? <p className="p-3 text-sm text-muted-foreground">输入城市名称或选择常用城市。</p>
                    : search.trim() !== query || cities.isFetching ? <p className="p-3 text-sm text-muted-foreground">正在搜索城市…</p>
                    : cities.isError ? <div role="alert" className="p-3 text-sm text-destructive">{cities.error.message}<Button type="button" variant="ghost" size="sm" onClick={() => void cities.refetch()}>重试</Button></div>
                    : <>
                      <CommandEmpty>没有匹配的城市，请尝试其他名称。</CommandEmpty>
                      <CommandGroup>
                        {cities.data?.cities.map((city) => (
                          <CommandItem key={city.id} value={String(city.id)} onSelect={() => selectCity(city)}>
                            <Check className={`mr-2 h-4 w-4 shrink-0 ${settings.city_id === city.id ? 'opacity-100' : 'opacity-0'}`} />
                            <div>
                              <div>{city.name}</div>
                              <div className="text-xs text-muted-foreground">{Array.from(new Set([city.admin2, city.admin1, city.country, city.timezone].filter(Boolean))).join(' · ')}</div>
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </>}
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
          <p className="text-xs text-muted-foreground">选择城市后自动设置当地时区，也可在下方单独调整。</p>
        </div>
        <div className="space-y-2" data-config-field-path="environment.timezone">
          <Label htmlFor="environment-timezone">时区</Label>
          <Popover open={timezoneOpen} onOpenChange={setTimezoneOpen}>
            <PopoverTrigger asChild>
              <Button id="environment-timezone" type="button" variant="outline" role="combobox" aria-expanded={timezoneOpen} className="w-full justify-between">
                <span className="truncate">{settings.timezone}</span>
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="max-w-[calc(100vw-2rem)] p-0" align="start" style={{ width: 'var(--radix-popover-trigger-width)' }}>
              <Command>
                <CommandInput placeholder="搜索时区，如 Shanghai、Tokyo、UTC" />
                <CommandList>
                  {timezones.isFetching && <p className="p-3 text-sm text-muted-foreground">正在加载时区…</p>}
                  {timezones.isError && <div role="alert" className="p-3 text-sm text-destructive">{timezones.error.message}<Button type="button" variant="ghost" size="sm" onClick={() => void timezones.refetch()}>重试</Button></div>}
                  <CommandEmpty>没有匹配的时区。</CommandEmpty>
                  <CommandGroup>
                    {timezoneOptions.map((timezone) => (
                      <CommandItem key={timezone} value={timezone} onSelect={() => { onChange?.({ ...settings, timezone }); setTimezoneOpen(false) }}>
                        <Check className={`mr-2 h-4 w-4 shrink-0 ${settings.timezone === timezone ? 'opacity-100' : 'opacity-0'}`} />
                        {timezone}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
      </CardContent>
    </Card>
  )
}
