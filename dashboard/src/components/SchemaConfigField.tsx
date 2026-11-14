import { Eye, EyeOff } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ListFieldEditor } from '@/components/ListFieldEditor'
import { Button } from '@/components/ui/button'
import { DraftNumberInput } from '@/components/ui/draft-number-input'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MultiSelect } from '@/components/ui/multi-select'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { ConfigFieldSchema, ItemFieldDefinition } from '@/lib/plugin-api'
import { resolveLocalizedText } from '@/lib/schema-config-label'

// 字段渲染组件
interface SchemaConfigFieldProps {
  field: ConfigFieldSchema
  value: unknown
  onChange: (value: unknown) => void
}

function localizeItemFields(
  itemFields: Record<string, ItemFieldDefinition> | undefined,
  language: string
): Record<string, ItemFieldDefinition> | undefined {
  if (!itemFields) return undefined

  return Object.fromEntries(
    Object.entries(itemFields).map(([fieldName, field]) => [
      fieldName,
      {
        ...field,
        label: resolveLocalizedText(field.label, language, fieldName, field.i18n, 'label'),
        placeholder:
          resolveLocalizedText(field.placeholder, language, '', field.i18n, 'placeholder') ||
          undefined,
      },
    ])
  )
}

export function SchemaConfigField({ field, value, onChange }: SchemaConfigFieldProps) {
  const fieldId = useId()
  const [showPassword, setShowPassword] = useState(false)
  const { i18n } = useTranslation()
  const language = i18n.resolvedLanguage || i18n.language || 'zh'
  const label = resolveLocalizedText(field.label, language, field.name, field.i18n, 'label')
  const hint = resolveLocalizedText(field.hint, language, '', field.i18n, 'hint')
  const placeholder = resolveLocalizedText(
    field.placeholder,
    language,
    '',
    field.i18n,
    'placeholder'
  )
  const localizedItemFields = localizeItemFields(field.item_fields, language)

  // 根据 ui_type 渲染不同的控件
  switch (field.ui_type) {
    case 'switch':
      return (
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor={fieldId}>{label}</Label>
            {hint && (
              <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
                {hint}
              </p>
            )}
          </div>
          <Switch
            id={fieldId}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
            checked={Boolean(value ?? field.default)}
            onCheckedChange={onChange}
            disabled={field.disabled}
          />
        </div>
      )

    case 'number':
      return (
        <div className="space-y-2">
          <Label htmlFor={fieldId}>{label}</Label>
          <DraftNumberInput
            id={fieldId}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
            value={value}
            defaultValue={field.default}
            onValueChange={onChange}
            min={field.min}
            max={field.max}
            step={field.step ?? 1}
            placeholder={placeholder}
            disabled={field.disabled}
          />
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'slider':
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor={fieldId}>{label}</Label>
            <span className="text-muted-foreground text-sm">
              {(value as number) ?? field.default}
            </span>
          </div>
          <Slider
            id={fieldId}
            aria-label={label}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
            value={[(value as number) ?? (field.default as number)]}
            onValueChange={(v) => onChange(v[0])}
            min={field.min ?? 0}
            max={field.max ?? 100}
            step={field.step ?? 1}
            disabled={field.disabled}
          />
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'select':
      if (field.multiple) {
        const selectedValues = Array.isArray(value)
          ? value.map((v) => String(v))
          : Array.isArray(field.default)
            ? field.default.map((v) => String(v))
            : []

        return (
          <div
            className="space-y-2"
            role="group"
            aria-labelledby={`${fieldId}-label`}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
          >
            <Label id={`${fieldId}-label`} asChild>
              <span>{label}</span>
            </Label>
            <MultiSelect
              options={(field.choices ?? []).map((choice) => ({
                label: String(choice),
                value: String(choice),
              }))}
              selected={selectedValues}
              onChange={onChange}
              placeholder={placeholder || '请选择'}
              disabled={field.disabled}
            />
            {hint && (
              <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
                {hint}
              </p>
            )}
          </div>
        )
      }

      return (
        <div className="space-y-2">
          <Label htmlFor={fieldId}>{label}</Label>
          <Select
            value={String(value ?? field.default)}
            onValueChange={onChange}
            disabled={field.disabled}
          >
            <SelectTrigger id={fieldId} aria-describedby={hint ? `${fieldId}-hint` : undefined}>
              <SelectValue placeholder={placeholder || '请选择'} />
            </SelectTrigger>
            <SelectContent>
              {field.choices?.map((choice) => (
                <SelectItem key={String(choice)} value={String(choice)}>
                  {String(choice)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'textarea':
      return (
        <div className="space-y-2">
          <Label htmlFor={fieldId}>{label}</Label>
          <Textarea
            id={fieldId}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
            value={(value as string) ?? field.default}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={field.rows ?? 3}
            disabled={field.disabled}
          />
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'password':
      return (
        <div className="space-y-2">
          <Label htmlFor={fieldId}>{label}</Label>
          <div className="relative">
            <Input
              id={fieldId}
              aria-describedby={hint ? `${fieldId}-hint` : undefined}
              type={showPassword ? 'text' : 'password'}
              value={(value as string) ?? ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={placeholder}
              disabled={field.disabled}
              className="pr-10"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-0 right-0 h-full px-3"
              aria-label={showPassword ? `隐藏${label}` : `显示${label}`}
              aria-pressed={showPassword}
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'list':
      return (
        <div
          className="space-y-2"
          role="group"
          aria-labelledby={`${fieldId}-label`}
          aria-describedby={hint ? `${fieldId}-hint` : undefined}
        >
          <Label id={`${fieldId}-label`} asChild>
            <span>{label}</span>
          </Label>
          <ListFieldEditor
            value={Array.isArray(value) ? value : Array.isArray(field.default) ? field.default : []}
            onChange={(newValue) => onChange(newValue)}
            itemType={field.item_type ?? 'string'}
            itemFields={localizedItemFields}
            minItems={field.min_items}
            maxItems={field.max_items}
            disabled={field.disabled}
            placeholder={placeholder}
          />
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )

    case 'text':
    default:
      return (
        <div className="space-y-2">
          <Label htmlFor={fieldId}>{label}</Label>
          <Input
            id={fieldId}
            aria-describedby={hint ? `${fieldId}-hint` : undefined}
            type="text"
            value={(value as string) ?? field.default ?? ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            maxLength={field.max_length}
            disabled={field.disabled}
          />
          {hint && (
            <p id={`${fieldId}-hint`} className="text-muted-foreground text-xs">
              {hint}
            </p>
          )}
        </div>
      )
  }
}
