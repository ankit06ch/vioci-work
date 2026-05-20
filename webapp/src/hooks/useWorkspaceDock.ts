import { useCallback, useEffect, useState } from 'react'
import {
  applyLayoutPreset,
  closeTabInLayout,
  defaultDockLayout,
  loadDockLayout,
  mergeOpenTabsIntoLayout,
  moveTabToLeaf,
  openTabInLayout,
  saveDockLayout,
  setLeafActive,
  type DockEdge,
  type DockNode,
  type LayoutPreset,
} from '../lib/workspaceDock'

export function useWorkspaceDock(projectId: string, openTabIds: string[]) {
  const [layout, setLayout] = useState<DockNode>(() =>
    projectId ? loadDockLayout(projectId, openTabIds) : defaultDockLayout(openTabIds),
  )

  useEffect(() => {
    if (!projectId) return
    setLayout(loadDockLayout(projectId, openTabIds))
  }, [projectId])

  useEffect(() => {
    if (!projectId) return
    saveDockLayout(projectId, layout)
  }, [projectId, layout])

  useEffect(() => {
    setLayout((prev) => mergeOpenTabsIntoLayout(prev, openTabIds))
  }, [openTabIds.join(',')])

  const selectTab = useCallback((leafId: string, tabId: string) => {
    setLayout((prev) => setLeafActive(prev, leafId, tabId))
  }, [])

  const closeTab = useCallback((tabId: string) => {
    setLayout((prev) => closeTabInLayout(prev, tabId))
  }, [])

  const moveTab = useCallback((tabId: string, targetLeafId: string, edge: DockEdge) => {
    setLayout((prev) => moveTabToLeaf(prev, tabId, targetLeafId, edge))
  }, [])

  const applyPreset = useCallback(
    (preset: LayoutPreset) => {
      setLayout(applyLayoutPreset(preset, openTabIds))
    },
    [openTabIds],
  )

  const openTabInDock = useCallback(
    (
      tabId: string,
      options?: { leafId?: string; label?: string; focusContentPane?: boolean },
    ) => {
      setLayout((prev) => openTabInLayout(prev, tabId, options).layout)
    },
    [],
  )

  const openTabWithMessage = useCallback(
    (
      tabId: string,
      options?: { leafId?: string; label?: string; focusContentPane?: boolean },
    ) => {
      const result = openTabInLayout(layout, tabId, options)
      setLayout(result.layout)
      return result.message
    },
    [layout],
  )

  return {
    layout,
    setLayout,
    selectTab,
    closeTab,
    moveTab,
    applyPreset,
    openTabInDock,
    openTabWithMessage,
  }
}
