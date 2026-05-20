export type TerminalIntent =
  | { type: 'launch' }
  | { type: 'simulate' }
  | { type: 'annotations' }
  | { type: 'dynamic'; label: string }
  | { type: 'copilot' }

export function detectTerminalIntent(text: string): TerminalIntent {
  const lower = text.toLowerCase().trim()

  if (
    /\b(launch|falcon|electron|starship|vulcan|ariane|rocket|fairing|envelope|compat)\b/.test(
      lower,
    )
  ) {
    return { type: 'launch' }
  }
  if (/\b(simulate|simulation|sweep|engine|analytic|ngspice)\b/.test(lower)) {
    return { type: 'simulate' }
  }
  if (
    /\b(annotate|annotation|part mass|component mass|vector|weight|dimensions|size)\b/.test(
      lower,
    )
  ) {
    return { type: 'annotations' }
  }
  if (/\b(compare|analyze|assess|evaluate|risk)\b/.test(lower)) {
    const short = text.slice(0, 36).trim() || 'Analysis'
    return { type: 'dynamic', label: short.length > 28 ? `${short.slice(0, 28)}…` : short }
  }
  return { type: 'copilot' }
}
