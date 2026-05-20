import { useEffect, useId, useRef, useState } from 'react'

type Tab = {
  id: string
  label: string
  closable?: boolean
}

export type TabAddOption = {
  id: string
  label: string
  hint?: string
}

type Props = {
  tabs: Tab[]
  activeId: string
  onSelect: (id: string) => void
  onClose?: (id: string) => void
  className?: string
  draggable?: boolean
  draggingTabId?: string | null
  onTabDragStart?: (tabId: string) => void
  onTabDragEnd?: () => void
  addOptions?: TabAddOption[]
  onAddTab?: (tabId: string) => void
}

export function ClosableTabBar({
  tabs,
  activeId,
  onSelect,
  onClose,
  className = '',
  draggable,
  draggingTabId,
  onTabDragStart,
  onTabDragEnd,
  addOptions = [],
  onAddTab,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuOpen])

  const showAdd = addOptions.length > 0 && onAddTab

  return (
    <div ref={rootRef} className={`closable-tab-bar ${className}`.trim()} role="tablist">
      {tabs.map((tab) => {
        const active = tab.id === activeId
        const isDragging = draggingTabId === tab.id
        const closable = tab.closable !== false && onClose
        return (
          <div
            key={tab.id}
            className={`closable-tab-wrap ${active ? 'closable-tab-wrap-active' : ''} ${isDragging ? 'closable-tab-wrap--dragging' : ''}`}
            draggable={draggable}
            onDragStart={(e) => {
              if (!draggable) return
              if ((e.target as HTMLElement).closest('.closable-tab-close, .closable-tab-add-btn')) {
                e.preventDefault()
                return
              }
              e.dataTransfer.setData('text/vioci-tab', tab.id)
              e.dataTransfer.effectAllowed = 'move'
              onTabDragStart?.(tab.id)
            }}
            onDragEnd={() => onTabDragEnd?.()}
          >
            <button
              type="button"
              role="tab"
              aria-selected={active}
              className={`closable-tab ${active ? 'closable-tab-active' : ''} ${draggable ? 'closable-tab-draggable' : ''}`}
              onClick={() => onSelect(tab.id)}
            >
              <span className="closable-tab-grip" aria-hidden>
                ⠿
              </span>
              <span className="closable-tab-label">{tab.label}</span>
            </button>
            {closable ? (
              <button
                type="button"
                className="closable-tab-close"
                draggable={false}
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

      {showAdd ? (
        <div className="closable-tab-add">
          <button
            type="button"
            className="closable-tab-add-btn"
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-controls={menuId}
            title="Add tab"
            onClick={() => setMenuOpen((o) => !o)}
          >
            +
          </button>
          {menuOpen ? (
            <ul id={menuId} className="closable-tab-add-menu" role="menu">
              {addOptions.map((opt) => (
                <li key={opt.id} role="none">
                  <button
                    type="button"
                    role="menuitem"
                    className="closable-tab-add-item"
                    onClick={() => {
                      onAddTab(opt.id)
                      setMenuOpen(false)
                    }}
                  >
                    <span className="closable-tab-add-item-label">{opt.label}</span>
                    {opt.hint ? (
                      <span className="closable-tab-add-item-hint muted">{opt.hint}</span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
