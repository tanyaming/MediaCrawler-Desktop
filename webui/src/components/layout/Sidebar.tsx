import { Radar, Wifi } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useCrawlerStore } from '@/store/crawlerStore'
import { useCrawlerStatus } from '@/hooks/useCrawler'
import { LanguageSwitch } from './LanguageSwitch'
import { ThemeToggle } from './ThemeToggle'

export function Sidebar() {
  const { t } = useTranslation()
  const status = useCrawlerStore((state) => state.status)

  // Poll status
  useCrawlerStatus()

  const isRunning = status === 'running'

  return (
    <header className="h-14 flex-shrink-0 glass-panel border-b border-cyber-border-subtle relative z-10">
      <div className="h-full px-4 flex items-center justify-between">
        {/* Left: Logo */}
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyber-neon-cyan to-cyber-neon-purple flex items-center justify-center shadow-sm">
            <Radar className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="font-semibold text-cyber-text-primary tracking-tight text-base">
            舆情采集器
          </span>
          {isRunning && (
            <Badge variant="running" className="text-[10px]">
              {t('status.active')}
            </Badge>
          )}
          {isRunning && (
            <span className="w-2 h-2 bg-cyber-neon-green rounded-full shadow-glow-green-sm animate-pulse-fast" />
          )}
        </div>

        {/* Right: Actions and Status */}
        <div className="flex items-center gap-3">
          {/* Theme Toggle */}
          <ThemeToggle />
          {/* Language Switch */}
          <LanguageSwitch />

          {/* Status Info */}
          <div className="hidden lg:flex items-center gap-2 text-xs">
            <span className="text-cyber-text-muted">{t('sidebar.api')}:</span>
            <span className="text-cyber-neon-cyan">v1.0.0</span>
            <div className="flex items-center gap-1.5">
              <Wifi className="w-3 h-3 text-cyber-text-secondary" />
              <span className="text-cyber-text-secondary">{t('sidebar.local')}</span>
              <span className="status-dot status-dot-online" />
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
