import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

interface LearningRule extends Record<string, unknown> {
  platform: string
  item_id: string
  type: 'group' | 'private'
  use: boolean
  learn: boolean
}

interface GlobalLearningSettingsProps {
  values: Record<string, Record<string, unknown> | null>
  sections: Array<'expression' | 'jargon'>
  onChange: (section: 'expression' | 'jargon', rules: LearningRule[]) => void
}

export function GlobalLearningSettings({ values, sections, onChange }: GlobalLearningSettingsProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      {sections.flatMap((section) => {
        const value = values[section]?.learning_list
        const rules = Array.isArray(value) ? value as LearningRule[] : []
        // 与后端一致：平台和目标均为空（* 与留空等价）的第一条规则是全局默认。
        const isBlank = (value: string) => value.trim() === '' || value.trim() === '*'
        const globalIndex = rules.findIndex((rule) => isBlank(rule.platform) && isBlank(rule.item_id))
        const globalRule = globalIndex >= 0 ? rules[globalIndex] : {
          platform: '', item_id: '', type: 'group' as const, use: true, learn: true,
        }
        const label = section === 'expression' ? '表达' : '黑话'

        const updateFlag = (field: 'use' | 'learn', checked: boolean) => {
          const nextRule = { ...globalRule, [field]: checked }
          onChange(section, globalIndex >= 0
            ? rules.map((rule, index) => index === globalIndex ? nextRule : rule)
            : [nextRule, ...rules])
        }

        return (['use', 'learn'] as const).map((field) => {
          const id = `${section}-global-${field}`
          return (
            <div key={field} className="flex items-center gap-2">
              <Label htmlFor={id} className="font-normal text-muted-foreground">
                {field === 'use' ? '使用' : '学习'}{label}
              </Label>
              <Switch
                id={id}
                checked={globalRule[field]}
                onCheckedChange={(checked) => updateFlag(field, checked)}
              />
            </div>
          )
        })
      })}
    </div>
  )
}
