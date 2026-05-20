import { create } from 'zustand'
import type { Diagram } from '../api/types'

type SelStore = {
  selectedNodeId: string | null
  diagram: Diagram | null
  setSelected: (id: string | null) => void
  setDiagram: (d: Diagram | null) => void
}

export const useSelectionStore = create<SelStore>((set) => ({
  selectedNodeId: null,
  diagram: null,
  setSelected: (id) => set({ selectedNodeId: id }),
  setDiagram: (d) => set({ diagram: d }),
}))
