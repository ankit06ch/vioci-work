import type { PartAnnotation } from '../api/types'
import {
  attachedStandardFields,
  availablePresetsToAttach,
  clearStandardField,
  customDataPoints,
  newDataPointId,
  patchStandardField,
  presetForKey,
  readStandardFieldValue,
  type CustomDataPoint,
  type StandardFieldKey,
  withAttachedField,
  withoutAttachedField,
} from '../lib/partDataFields'

type Props = {
  part: PartAnnotation
  onChange: (patch: Partial<PartAnnotation>) => void
  onExtraChange: (extra: Record<string, unknown>) => void
}

export function PartDataFieldsEditor({ part, onChange, onExtraChange }: Props) {
  const attached = attachedStandardFields(part)
  const available = availablePresetsToAttach(part)
  const custom = customDataPoints(part)

  const attachPreset = (key: StandardFieldKey) => {
    onExtraChange(withAttachedField(part, key))
  }

  const detachPreset = (key: StandardFieldKey) => {
    onExtraChange(withoutAttachedField(part, key))
    onChange(clearStandardField(key))
  }

  const setCustom = (rows: CustomDataPoint[]) => {
    onExtraChange({ ...part.extra, dataPoints: rows })
  }

  return (
    <div className="part-data-fields">
      <div className="part-data-fields-head">
        <span className="part-data-fields-title">Data</span>
        {available.length > 0 ? (
          <div className="part-data-add-row">
            <select
              className="auth-input part-data-add-select"
              defaultValue=""
              onChange={(e) => {
                const key = e.target.value as StandardFieldKey
                if (!key) return
                attachPreset(key)
                e.target.value = ''
              }}
            >
              <option value="">+ Attach field…</option>
              {available.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                  {p.unit ? ` (${p.unit})` : ''}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>

      {attached.length === 0 && custom.length === 0 ? (
        <p className="muted part-data-empty">
          No data yet. Attach Mass, dimensions, power, or add custom data points below.
        </p>
      ) : null}

      <ul className="part-data-attached-list">
        {attached.map((key) => {
          const preset = presetForKey(key)
          const label = preset.unit ? `${preset.label} (${preset.unit})` : preset.label
          return (
            <li key={key} className="part-data-row">
              <label className="part-data-row-label">{label}</label>
              <div className="part-data-row-inputs">
                {preset.valueType === 'textarea' ? (
                  <textarea
                    className="input-msg part-data-value"
                    rows={2}
                    value={readStandardFieldValue(part, key)}
                    onChange={(e) => onChange(patchStandardField(key, e.target.value))}
                  />
                ) : (
                  <input
                    className="auth-input part-data-value"
                    type={preset.valueType === 'number' ? 'number' : 'text'}
                    step={preset.valueType === 'number' ? 'any' : undefined}
                    value={readStandardFieldValue(part, key)}
                    placeholder={preset.valueType === 'number' ? '—' : ''}
                    onChange={(e) => onChange(patchStandardField(key, e.target.value))}
                  />
                )}
                <button
                  type="button"
                  className="btn btn-ghost part-data-remove"
                  title="Remove field"
                  aria-label={`Remove ${preset.label}`}
                  onClick={() => detachPreset(key)}
                >
                  ×
                </button>
              </div>
            </li>
          )
        })}
      </ul>

      <div className="part-data-custom">
        <span className="part-data-custom-title muted">Custom data points</span>
        <ul className="part-data-custom-list">
          {custom.map((row, i) => (
            <li key={row.id} className="part-data-custom-row">
              <input
                className="auth-input"
                placeholder="Label"
                value={row.label}
                onChange={(e) => {
                  const next = [...custom]
                  next[i] = { ...row, label: e.target.value }
                  setCustom(next)
                }}
              />
              <input
                className="auth-input"
                placeholder="Value"
                value={row.value}
                onChange={(e) => {
                  const next = [...custom]
                  next[i] = { ...row, value: e.target.value }
                  setCustom(next)
                }}
              />
              <input
                className="auth-input part-data-unit"
                placeholder="Unit"
                value={row.unit}
                onChange={(e) => {
                  const next = [...custom]
                  next[i] = { ...row, unit: e.target.value }
                  setCustom(next)
                }}
              />
              <button
                type="button"
                className="btn btn-ghost part-data-remove"
                aria-label="Remove data point"
                onClick={() => setCustom(custom.filter((r) => r.id !== row.id))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="btn btn-ghost part-data-add-custom"
          onClick={() =>
            setCustom([
              ...custom,
              { id: newDataPointId(), label: '', value: '', unit: '' },
            ])
          }
        >
          + Add data point
        </button>
      </div>
    </div>
  )
}
