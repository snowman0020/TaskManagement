// Format an ISO/UTC timestamp in Thailand time (UTC+7, Asia/Bangkok), so it
// reads the same regardless of the viewer's machine timezone.
export function formatDateTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-GB', {
    timeZone: 'Asia/Bangkok',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}
