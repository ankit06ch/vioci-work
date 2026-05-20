import type { NodeProps } from 'reactflow'
import { Handle, Position } from 'reactflow'

export function SchemaNode({ data }: NodeProps<{ label: string }>) {
  return (
    <div style={{ userSelect: 'none' }}>
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#ff7a59', width: 6, height: 6, border: 'none' }}
      />
      <div style={{ padding: '5px 8px' }}>{data.label}</div>
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: '#ff7a59', width: 6, height: 6, border: 'none' }}
      />
    </div>
  )
}
