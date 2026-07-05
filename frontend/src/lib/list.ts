// Split a comma- or newline-separated string into a trimmed, non-empty list.
// Replaces the per-view `parseList` / `toStringList` helpers.
export function parseList(text: string): string[] {
  return text
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}
