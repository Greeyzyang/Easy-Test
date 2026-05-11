import request from '@/utils/request'

export function kbQuery(data) {
  return request({
    url: '/rest/v1/ai/kb/query/',
    method: 'post',
    data
  })
}

export function chatWithAgent(data) {
  return request({
    url: '/rest/v1/ai/chat/',
    method: 'post',
    data,
    timeout: 300000 // 为 AI 对话设置更长的超时时间（300秒 / 5分钟）
  })
}
