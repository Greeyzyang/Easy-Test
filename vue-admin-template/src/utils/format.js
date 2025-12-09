/**
 * 格式化日期时间
 * @param {string | Date} datetime - 要格式化的日期时间字符串或 Date 对象
 * @returns {string} 格式化后的日期时间字符串
 */
export function formatDateTime(datetime) {
  if (!datetime) return '-'
  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
} 