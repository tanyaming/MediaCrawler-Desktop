import { useTranslation } from 'react-i18next'

export function AuthorFooter() {
  const { t } = useTranslation()

  return (
    <footer className="h-10 flex-shrink-0 glass-panel border-t border-cyber-border-subtle">
      <div className="h-full px-6 flex items-center justify-between text-xs font-mono text-cyber-text-muted">
        <span>舆情采集器</span>
        <span>{t('sidebar.api', { defaultValue: 'API' })} v1.0.0</span>
      </div>
    </footer>
  )
}
