type Tab = {
  id: string
  label: string
  closable?: boolean
}

type Props = {
  tabs: Tab[]
  activeId: string
  onSelect: (id: string) => void
  onClose?: (id: string) => void
  className?: string
}

export function ClosableTabBar({ tabs, activeId, onSelect, onClose, className = '' }: Props) {
  return (
    <div className={`closable-tab-bar ${className}`.trim()} role="tablist">
      {tabs.map((tab) => {
        const active = tab.id === activeId
        return (
          <div key={tab.id} className={`closable-tab-wrap ${active ? 'closable-tab-wrap-active' : ''}`}>
            <button
              type="button"
              role="tab"
              aria-selected={active}
              className={`closable-tab ${active ? 'closable-tab-active' : ''}`}
              onClick={() => onSelect(tab.id)}
            >
              {tab.label}
            </button>
            {tab.closable && onClose ? (
              <button
                type="button"
                className="closable-tab-close"
                aria-label={`Close ${tab.label}`}
                onClick={(e) => {
                  e.stopPropagation()
                  onClose(tab.id)
                }}
              >
                ×
              </button>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
