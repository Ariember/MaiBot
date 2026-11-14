function getLocaleCandidates(language: string): string[] {
  const normalized = (language || 'zh').replace('-', '_')
  const base = normalized.split('_')[0]
  const candidates = [language, normalized, base]

  if (base === 'zh') candidates.push('zh_CN', 'zh-CN')
  if (base === 'en') candidates.push('en_US', 'en-US')
  if (base === 'ja') candidates.push('ja_JP', 'ja-JP')
  if (base === 'ko') candidates.push('ko_KR', 'ko-KR')

  candidates.push('zh_CN', 'zh-CN', 'zh')
  return Array.from(new Set(candidates.filter(Boolean)))
}

export function resolveLocalizedText(
  value: unknown,
  language: string,
  fallback = '',
  i18n?: Record<string, Record<string, string>>,
  key?: string
): string {
  const candidates = getLocaleCandidates(language)

  if (i18n && key) {
    for (const locale of candidates) {
      const localized = i18n[locale]?.[key]
      if (typeof localized === 'string' && localized.trim()) {
        return localized
      }
    }
  }

  if (typeof value === 'string') {
    return value || fallback
  }

  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const localizedMap = value as Record<string, unknown>
    for (const locale of candidates) {
      const localized = localizedMap[locale]
      if (typeof localized === 'string' && localized.trim()) {
        return localized
      }
    }
  }

  return fallback
}
