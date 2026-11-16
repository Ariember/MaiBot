import { ArrowRight } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { validateToken } from '@/lib/token-validator'
import { CustomTokenForm } from '@/routes/setup/StepForms'
import { SetupWizardLayout } from '@/routes/setup/SetupWizardLayout'


function PasswordSetupPreview() {
  const [token, setToken] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const steps = [
    { id: 'custom-token', title: '设置登录密码', description: '不设置的话，每次启动都会换一个随机密码。', label: '登录密码' },
    { id: 'bot-profile', title: '基础与人格', description: '' },
    { id: 'model-setup', title: '模型配置', description: '' },
  ]
  return (
    <div className="min-h-screen px-4">
      <SetupWizardLayout
        steps={steps}
        currentStep={0}
        actions={
          <>
            <Button variant="ghost" disabled className="px-1">
              {'跳过向导'}
            </Button>
            <Button
              size="lg"
              variant={validateToken(token).isValid ? 'default' : 'outline'}
              className="min-w-44"
              disabled={!validateToken(token).isValid}
              onClick={() => setSubmitted(true)}
            >
              {'保存并继续'}
              <ArrowRight />
            </Button>
            {submitted && (
              <p role="status" className="text-muted-foreground w-full text-sm">
                校验通过。此处仅为预览，不保存密码。
              </p>
            )}
          </>
        }
      >
        <CustomTokenForm
          token={token}
          onChange={(value) => {
            setToken(value)
            setSubmitted(false)
          }}
        />
      </SetupWizardLayout>
    </div>
  )
}

export function SetupReview() {
  return (
    <>
      <PasswordSetupPreview />
    </>
  )
}
