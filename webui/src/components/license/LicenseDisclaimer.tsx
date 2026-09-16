import { useTranslation } from 'react-i18next'
import { ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'

const LICENSE_KEY = 'mediacrawler_license_accepted'

// 检查是否已经接受协议
export function isLicenseAccepted(): boolean {
  return localStorage.getItem(LICENSE_KEY) === 'true'
}

// 清除协议接受状态
export function clearLicenseAccepted(): void {
  localStorage.removeItem(LICENSE_KEY)
}

interface LicenseDisclaimerProps {
  onAccept: () => void
}

export function LicenseDisclaimer({ onAccept }: LicenseDisclaimerProps) {
  const { t } = useTranslation('license')

  const handleConfirm = () => {
    localStorage.setItem(LICENSE_KEY, 'true')
    onAccept()
  }

  const handleDecline = () => {
    // 尝试关闭当前标签页（不会关闭整个浏览器，只关闭当前tab）
    try {
      // 方式1: 直接关闭当前标签页
      window.close()

      // 方式2: 将当前标签页导航到空白页
      setTimeout(() => {
        window.location.href = 'about:blank'
      }, 100)
    } catch {
      // 忽略错误
    }

    // 如果无法关闭（浏览器安全限制），显示拒绝访问页面
    setTimeout(() => {
      document.body.innerHTML = `
        <div style="
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          background: #f8fafc;
          color: #e11d48;
          font-family: Inter, system-ui, sans-serif;
          text-align: center;
          padding: 20px;
        ">
          <div style="font-size: 48px; margin-bottom: 20px;">⛔</div>
          <div style="font-size: 24px; font-weight: bold; margin-bottom: 10px;">访问已拒绝</div>
          <div style="font-size: 14px; color: #64748b;">您未同意使用条款，请关闭此窗口</div>
        </div>
      `
    }, 200)
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-[100] overflow-y-auto py-8">
      <div className="bg-cyber-bg-panel border border-cyber-border-subtle rounded-2xl shadow-2xl p-8 max-w-2xl w-full mx-4 relative">
        {/* Header with warning icon */}
        <div className="flex items-center justify-center gap-3 mb-4">
          <ShieldAlert className="w-8 h-8 text-cyber-neon-orange" />
          <h2 className="text-2xl font-semibold text-cyber-text-primary">
            {t('title')}
          </h2>
        </div>

        {/* Warning subtitle */}
        <div className="text-center mb-4">
          <span className="text-base text-cyber-text-secondary">
            {t('warning')}
          </span>
        </div>

        {/* Content box */}
        <div className="bg-cyber-bg-secondary border border-cyber-border-subtle rounded-xl p-5 mb-5">
          <ul className="space-y-3 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-cyber-neon-cyan font-bold">1.</span>
              <span className="text-cyber-text-primary">{t('content.line1')}</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyber-neon-cyan font-bold">2.</span>
              <span className="text-cyber-text-primary">{t('content.line2')}</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyber-neon-cyan font-bold">3.</span>
              <span className="text-cyber-text-primary">{t('content.line3')}</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyber-neon-cyan font-bold">4.</span>
              <span className="text-cyber-text-primary">{t('content.line4')}</span>
            </li>
          </ul>
        </div>

        {/* Action buttons */}
        <div className="flex gap-4">
          <Button
            onClick={handleDecline}
            variant="outline"
            className="flex-1"
          >
            {t('decline')}
          </Button>
          <Button
            onClick={handleConfirm}
            variant="secondary"
            className="flex-1"
          >
            {t('confirm')}
          </Button>
        </div>
      </div>
    </div>
  )
}
