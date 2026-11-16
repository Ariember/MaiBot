import { useNavigate } from '@tanstack/react-router'
import {
  ArrowRight,
  Brain,
  Bot,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { SetupWizardLayout } from './SetupWizardLayout'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { findTemplateByBaseUrl } from '@/routes/config/providerTemplates'
import { APP_NAME } from '@/lib/version'
import { useToast } from '@/hooks/use-toast'
import { validateToken } from '@/lib/token-validator'
import type { ModelListItem } from '@/lib/config-api'
import type {
  ApiProviderSetupConfig,
  SetupStep,
  BotBasicConfig,
  ModelSetupConfig,
  PersonalityConfig,
} from './types'
import {
  ApiProviderSetupForm,
  BotBasicForm,
  CustomTokenForm,
  ModelSetupForm,
  PersonalityForm,
  PersonalityPresetSelect,
} from './StepForms'
import {
  loadBotBasicConfig,
  loadSetupStatus,
  loadPersonalityConfig,
  loadApiProviderSetupConfig,
  loadModelSetupConfig,
  saveBotBasicConfig,
  savePersonalityConfig,
  saveApiProviderSetupConfig,
  saveModelSetupConfig,
  completeSetup,
  fetchSetupModels,
  updateAccessToken,
} from './api'


export function SetupPage() {
  return <SetupPageContent />
}

// 内部实现组件
function SetupPageContent() {
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()
  const { toast } = useToast()
  const createDefaultPersonalityConfig = (): PersonalityConfig => ({
    personality: '是一个大二女大学生，现在正在上网和群友聊天。有轻微攻击性',
    behavior_style: '自然参与日常聊天，不会没话题硬找话题；先理解上下文，再决定回复或保持安静。',
    reply_style: '你的风格平淡简短。可以参考贴吧，知乎和微博的回复风格。不浮夸不长篇大论，不要过分修辞和复杂句。',
    dialogue_examples: [],
  })
  const [currentStep, setCurrentStep] = useState(0)
  const [isCompleting, setIsCompleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [requiresCustomToken, setRequiresCustomToken] = useState(false)
  const [customToken, setCustomToken] = useState('')

  // 步骤1：Bot基础信息
  const [botBasic, setBotBasic] = useState<BotBasicConfig>({
    platform: '',
    qq_account: '',
    platforms: [],
    nickname: '',
    alias_names: [],
  })

  // 步骤2：人格配置
  const [personality, setPersonality] = useState<PersonalityConfig>(() =>
    createDefaultPersonalityConfig()
  )

  // 步骤3：API 提供商配置
  const [apiProviderSetup, setApiProviderSetup] = useState<ApiProviderSetupConfig>({
    provider_name: '',
    base_url: '',
    api_key: '',
  })

  // 步骤4：基础模型配置
  const [modelSetup, setModelSetup] = useState<ModelSetupConfig>({
    planner_model_name: '',
    planner_model_identifier: '',
    planner_visual: false,
    planner_thinking: false,
    replyer_model_name: '',
    replyer_model_identifier: '',
    replyer_visual: false,
    replyer_thinking: true,
  })

  const setupSteps: SetupStep[] = [
    {
      id: 'bot-profile',
      title: '基础与人格',
      description: '',
      icon: Bot,
    },
    {
      id: 'model-setup',
      title: '模型配置',
      description: '',
      icon: Brain,
    },
  ]
  const steps: SetupStep[] = requiresCustomToken
    ? [
        {
          id: 'custom-token',
          title: '设置登录密码',
          description: '不设置的话，每次启动都会换一个随机密码。',
          icon: ShieldCheck,
        },
        ...setupSteps,
      ]
    : setupSteps

  const currentStepId = steps[currentStep]?.id
  const [availableModels, setAvailableModels] = useState<ModelListItem[]>([])
  const [modelFetchStatus, setModelFetchStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [modelFetchError, setModelFetchError] = useState('')

  // DeepSeek 的角色默认值在选择提供商后立即生效，不依赖 Key 或模型列表请求。
  useEffect(() => {
    if (findTemplateByBaseUrl(apiProviderSetup.base_url)?.id !== 'deepseek') return
    setModelSetup((previous) => ({
      ...previous,
      planner_model_identifier: 'deepseek-flash',
      planner_model_name: 'deepseek-flash',
      planner_thinking: false,
      planner_reasoning_effort: 'high',
      replyer_model_identifier: 'deepseek-flash',
      replyer_model_name: 'deepseek-flash',
      replyer_thinking: true,
      replyer_reasoning_effort: 'high',
    }))
  }, [apiProviderSetup.base_url])

  useEffect(() => {
    if (currentStepId !== 'model-setup') return
    setAvailableModels([])
    setModelFetchError('')
    if (!apiProviderSetup.base_url.trim() || !apiProviderSetup.api_key.trim()) {
      setModelFetchStatus('idle')
      return
    }

    setModelFetchStatus('loading')
    let cancelled = false
    let timer: ReturnType<typeof window.setTimeout>
    const fetchModels = async () => {
      try {
        const models = await fetchSetupModels({
          provider_name: '',
          base_url: apiProviderSetup.base_url,
          api_key: apiProviderSetup.api_key,
        })
        if (cancelled) return
        setAvailableModels(models)
        if (findTemplateByBaseUrl(apiProviderSetup.base_url)?.id === 'deepseek') {
          if (!models.some((model) => model.id === 'deepseek-flash')) {
            throw new Error('提供商返回的模型列表中没有 deepseek-flash，请检查模型列表或手动选择可用模型')
          }
        } else {
          setModelSetup((previous) => {
            const planner = models.some((model) => model.id === previous.planner_model_identifier)
              ? previous.planner_model_identifier : ''
            const replyer = models.some((model) => model.id === previous.replyer_model_identifier)
              ? previous.replyer_model_identifier : ''
            return {
              ...previous,
              planner_model_identifier: planner,
              planner_model_name: planner,
              replyer_model_identifier: replyer,
              replyer_model_name: replyer,
            }
          })
        }
        setModelFetchError('')
        setModelFetchStatus('success')
      } catch (error) {
        if (cancelled) return
        setModelFetchError(error instanceof Error ? error.message : '获取模型列表失败')
        setModelFetchStatus('error')
        // 失败后等待 1 秒再重试，避免请求重叠；重试期间保留错误状态以允许手动填写。
        timer = window.setTimeout(fetchModels, 1000)
      }
    }
    // 等待用户停止输入；切换地址或 Key 后忽略旧请求，避免串用提供商的列表。
    timer = window.setTimeout(fetchModels, 600)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [currentStepId, apiProviderSetup.base_url, apiProviderSetup.api_key])

  // 加载现有配置
  useEffect(() => {
    const loadConfigs = async () => {
      try {
        setIsLoading(true)

        // 并行加载所有配置
        const [setupStatus, bot, personality, apiProvider, model] = await Promise.all([
          loadSetupStatus(),
          loadBotBasicConfig(),
          loadPersonalityConfig(),
          loadApiProviderSetupConfig(),
          loadModelSetupConfig(),
        ])

        setRequiresCustomToken(setupStatus.requires_custom_token)
        setBotBasic(bot)
        setPersonality(personality)
        setApiProviderSetup(apiProvider)
        setModelSetup(model)
      } catch (error) {
        toast({
          title: '加载配置失败',
          description:
            error instanceof Error ? error.message : '无法加载现有配置，将使用默认值',
          variant: 'destructive',
        })
      } finally {
        setIsLoading(false)
      }
    }

    loadConfigs()
  }, [toast])

  // 保存当前步骤配置
  const saveCurrentStep = async () => {
    setIsSaving(true)
    try {
      switch (currentStepId) {
        case 'bot-profile': // Bot基础与人格
          await saveBotBasicConfig(botBasic)
          await savePersonalityConfig(personality)
          break
        case 'model-setup': // API 提供商与基础模型
          await saveApiProviderSetupConfig(apiProviderSetup)
          await saveModelSetupConfig(modelSetup, apiProviderSetup.provider_name)
          break
      }

      toast({
        title: '保存成功',
        description: `${steps[currentStep].title} 配置已保存`,
        duration: 1000,
      })
      return true
    } catch (error) {
      toast({
        title: '保存失败',
        description: error instanceof Error ? error.message : '未知错误',
        variant: 'destructive',
      })
      return false
    } finally {
      setIsSaving(false)
    }
  }

  const saveCustomToken = async () => {
    const trimmedToken = customToken.trim()
    const tokenValidation = validateToken(trimmedToken)
    if (!tokenValidation.isValid) {
      const failedRules = tokenValidation.rules
        .filter((rule) => !rule.passed)
        .map((rule) => rule.label)
        .join(', ')
      toast({
        title: '验证失败',
        description: `密码不符合要求：${failedRules}`,
        variant: 'destructive',
      })
      return false
    }

    setIsSaving(true)
    try {
      const result = await updateAccessToken(trimmedToken)
      if (!result.success) {
        toast({
          title: '保存失败',
          description: result.message,
          variant: 'destructive',
        })
        return false
      }

      toast({
        title: '密码已更新',
        description: '已自动登录，请继续完成配置。',
      })
      setCustomToken('')
      setRequiresCustomToken(false)
      return true
    } catch (error) {
      toast({
        title: '保存失败',
        description: error instanceof Error ? error.message : '未知错误',
        variant: 'destructive',
      })
      return false
    } finally {
      setIsSaving(false)
    }
  }

  // Step 1 验证
  function validateBotBasic(config: BotBasicConfig): string | null {
    if (!config.nickname.trim()) return '请输入昵称'
    return null
  }

  function validateApiProviderSetup(config: ApiProviderSetupConfig): string | null {
    if (!config.provider_name.trim()) return '请输入 API 提供商名称'
    if (!config.base_url.trim()) return '请输入 API Base URL'
    if (!config.api_key.trim()) return '请输入 API Key'
    return null
  }

  function validateModelSetup(config: ModelSetupConfig): string | null {
    if (modelFetchStatus === 'loading') return '正在获取模型列表，请稍候'
    if (modelFetchStatus === 'idle') return '请先填写 API Key 获取模型列表'
    if (modelFetchStatus === 'success' && (
      !availableModels.some((model) => model.id === config.planner_model_identifier) ||
      !availableModels.some((model) => model.id === config.replyer_model_identifier)
    )) return '请选择用于规划和回复的模型'
    if (!config.planner_model_identifier.trim()) {
      return '请输入 planner 模型标识符'
    }
    if (!config.replyer_model_identifier.trim()) {
      return '请输入 replyer 模型标识符'
    }
    if (!apiProviderSetup.provider_name.trim()) return '请输入 API 提供商名称'
    return null
  }

  const handleNext = async () => {
    if (currentStepId === 'custom-token') {
      await saveCustomToken()
      return
    }

    // Step 1 验证
    if (currentStepId === 'bot-profile') {
      const error = validateBotBasic(botBasic)
      if (error) {
        toast({
          title: '验证失败',
          description: error,
          variant: 'destructive',
        })
        return
      }
    }
    if (currentStepId === 'model-setup') {
      const error = validateApiProviderSetup(apiProviderSetup) ?? validateModelSetup(modelSetup)
      if (error) {
        toast({
          title: '验证失败',
          description: error,
          variant: 'destructive',
        })
        return
      }
    }

    // 保存当前步骤
    const saved = await saveCurrentStep()
    if (!saved) return

    // 进入下一步
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleComplete = async () => {
    setIsCompleting(true)

    try {
      const error = validateApiProviderSetup(apiProviderSetup) ?? validateModelSetup(modelSetup)
      if (error) {
        toast({
          title: '验证失败',
          description: error,
          variant: 'destructive',
        })
        setIsCompleting(false)
        return
      }

      // 1. 保存最后一步的基础模型配置
      const saved = await saveCurrentStep()
      if (!saved) {
        setIsCompleting(false)
        return
      }

      // 2. 标记设置完成
      await completeSetup()

      toast({
        title: '配置完成',
        description: `${APP_NAME} 配置已保存。先在「聊聊」发一句「你好」，试试麦麦的回复和说话风格。`,
      })

      // 3. 配置文件会被 MaiBot 热加载；完成后进入聊聊，先体验本地对话。
      navigate({ to: '/chat', search: { setupTrial: true } })
    } catch (error) {
      toast({
        title: '配置失败',
        description: error instanceof Error ? error.message : '未知错误',
        variant: 'destructive',
      })
    } finally {
      setIsCompleting(false)
    }
  }

  const handleSkip = async () => {
    try {
      await completeSetup()
      navigate({ to: '/' })
    } catch (error) {
      toast({
        title: '跳过失败',
        description: error instanceof Error ? error.message : '未知错误',
        variant: 'destructive',
      })
    }
  }

  // 渲染当前步骤的表单
  const renderStepForm = () => {
    switch (currentStepId) {
      case 'custom-token':
        return <CustomTokenForm token={customToken} onChange={setCustomToken} />
      case 'bot-profile':
        return (
          <div className="space-y-8">
            <BotBasicForm config={botBasic} onChange={setBotBasic} />
            <PersonalityForm config={personality} onChange={setPersonality} />
          </div>
        )
      case 'model-setup':
        return (
          <div className="space-y-5">
            <ApiProviderSetupForm config={apiProviderSetup} onChange={(next) => {
              if (next.base_url !== apiProviderSetup.base_url) {
                setModelSetup((previous) => ({
                  ...previous,
                  planner_model_identifier: '',
                  planner_model_name: '',
                  replyer_model_identifier: '',
                  replyer_model_name: '',
                }))
              }
              setApiProviderSetup(next)
            }} />
            <AnimatePresence initial={false}>
              {apiProviderSetup.api_key.trim() && (
                <motion.div
                  key="model-setup-fields"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: reduceMotion ? 0 : 0.2, ease: 'easeInOut' }}
                  className="overflow-hidden"
                >
                  <div className="border-border border-t-2 pt-4">
                    <ModelSetupForm
                      config={modelSetup}
                      onChange={setModelSetup}
                      models={availableModels}
                      fetchStatus={modelFetchStatus}
                      fetchError={modelFetchError}
                      providerBaseUrl={apiProviderSetup.base_url}
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="relative h-full min-h-screen overflow-x-hidden overflow-y-auto px-4">
      {/* 加载状态 */}
      {isLoading ? (
        <div className="relative z-10 flex min-h-screen flex-col items-center justify-center text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center">
            <div className="border-primary h-12 w-12 animate-spin rounded-full border-4 border-t-transparent" />
          </div>
          <p className="text-lg font-medium">{'加载中...'}</p>
          <p className="text-muted-foreground mt-2 text-sm">{'正在读取已有配置'}</p>
        </div>
      ) : (
        <SetupWizardLayout
          steps={steps}
          currentStep={currentStep}
          headerActions={currentStepId === 'bot-profile' ? (
            <PersonalityPresetSelect config={personality} onChange={setPersonality} />
          ) : undefined}
          actions={
            <>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-1"
                    disabled={isSaving || isCompleting || currentStepId === 'custom-token'}
                  >
                    {'跳过向导'}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{'确认跳过配置向导'}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {'您可以随时在 WEBUI设置中重新进入配置向导。确定要跳过吗？'}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                    <AlertDialogAction onClick={handleSkip}>
                      {'确认跳过'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              <div className="ml-auto flex items-center gap-3">
                {currentStep > 0 && (
                  <Button variant="outline" onClick={handlePrevious} disabled={isSaving}>
                    {'上一步'}
                  </Button>
                )}
                {currentStep === steps.length - 1 && currentStepId !== 'custom-token' ? (
                  <Button
                    onClick={handleComplete}
                    disabled={isCompleting || isSaving}
                    className="flex-1 sm:flex-none"
                  >
                    {isCompleting || isSaving ? (
                      <>
                        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {isSaving
                          ? '保存中...'
                          : '完成中...'}
                      </>
                    ) : (
                      <>
                        {'完成配置'}
                        <CheckCircle2 className="ml-2 h-4 w-4" strokeWidth={2} fill="none" />
                      </>
                    )}
                  </Button>
                ) : (
                  <Button
                    onClick={handleNext}
                    variant={currentStepId === 'custom-token' && !validateToken(customToken).isValid ? 'outline' : 'default'}
                    size="lg"
                    disabled={
                      isSaving ||
                      (currentStepId === 'custom-token' && !validateToken(customToken).isValid)
                    }
                    className="min-w-44"
                  >
                    {isSaving ? (
                      <>
                        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {'保存中...'}
                      </>
                    ) : (
                      <>
                        {currentStepId === 'custom-token'
                          ? '保存并继续'
                          : '下一步'}
                        <ArrowRight className="ml-2 h-4 w-4" strokeWidth={2} fill="none" />
                      </>
                    )}
                  </Button>
                )}
              </div>
            </>
          }
        >
          {/* 表单内容 */}
          {renderStepForm()}
        </SetupWizardLayout>
      )}
    </div>
  )
}
