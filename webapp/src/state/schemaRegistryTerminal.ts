import { create } from 'zustand'
import type { SchemaRegistrySqlResult } from '../api/types'

export type SchemaRegistryTerminalSession = {
  sql: string
  result: SchemaRegistrySqlResult | null
  error: string | null
  updatedAt: number
}

type Store = {
  sessions: Record<string, SchemaRegistryTerminalSession>
  pushTerminalSql: (
    projectId: string,
    payload: { sql: string; result?: SchemaRegistrySqlResult | null; error?: string | null },
  ) => void
}

export const useSchemaRegistryTerminalStore = create<Store>((set) => ({
  sessions: {},
  pushTerminalSql: (projectId, { sql, result = null, error = null }) =>
    set((s) => ({
      sessions: {
        ...s.sessions,
        [projectId]: { sql, result, error, updatedAt: Date.now() },
      },
    })),
}))
