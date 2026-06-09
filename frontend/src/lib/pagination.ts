export function lastPageOffset(total: number, limit: number) {
  if (total <= 0) return 0
  const pageSize = Math.max(1, limit)
  return Math.floor((total - 1) / pageSize) * pageSize
}
