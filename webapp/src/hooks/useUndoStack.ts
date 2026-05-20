import { useCallback, useRef, useState } from 'react'

const MAX_HISTORY = 60

export function useUndoStack<T>(initial: T) {
  const [present, setPresent] = useState(initial)
  const past = useRef<T[]>([])
  const future = useRef<T[]>([])
  const presentRef = useRef(initial)
  presentRef.current = present

  const replace = useCallback((next: T, resetHistory = false) => {
    if (resetHistory) {
      past.current = []
      future.current = []
    }
    setPresent(next)
    presentRef.current = next
  }, [])

  const push = useCallback((next: T) => {
    past.current.push(presentRef.current)
    if (past.current.length > MAX_HISTORY) past.current.shift()
    future.current = []
    setPresent(next)
    presentRef.current = next
  }, [])

  const undo = useCallback((): T | null => {
    if (!past.current.length) return null
    future.current.unshift(presentRef.current)
    const prev = past.current.pop()!
    setPresent(prev)
    presentRef.current = prev
    return prev
  }, [])

  const redo = useCallback((): T | null => {
    if (!future.current.length) return null
    past.current.push(presentRef.current)
    const nxt = future.current.shift()!
    setPresent(nxt)
    presentRef.current = nxt
    return nxt
  }, [])

  const [histVer, setHistVer] = useState(0)
  const bump = () => setHistVer((v) => v + 1)

  const pushWithHist = useCallback(
    (next: T) => {
      push(next)
      bump()
    },
    [push],
  )

  const undoWithHist = useCallback(() => {
    const r = undo()
    bump()
    return r
  }, [undo])

  const redoWithHist = useCallback(() => {
    const r = redo()
    bump()
    return r
  }, [redo])

  const replaceWithHist = useCallback(
    (next: T, resetHistory = false) => {
      replace(next, resetHistory)
      bump()
    },
    [replace],
  )

  void histVer

  return {
    present,
    replace: replaceWithHist,
    push: pushWithHist,
    undo: undoWithHist,
    redo: redoWithHist,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
    histVer,
  }
}
