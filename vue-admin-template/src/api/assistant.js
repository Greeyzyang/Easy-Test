import request from '@/utils/request'

export function startGenerationTask(data) {
  return request({
    url: '/rest/v1/ai/generate-task/',
    method: 'post',
    data
  })
}

export function getTaskStatus(taskId) {
  return request({
    url: `/rest/v1/ai/task-status/${taskId}/`,
    method: 'get'
  })
}

// 新增：下载Excel，返回blob
export function downloadTestcasesXlsx(taskId) {
  return request({
    url: `/rest/v1/ai/export-xlsx/${taskId}/`,
    method: 'get',
    responseType: 'blob'
  })
}

export function kbQuery(data) {
  return request({
    url: '/rest/v1/ai/kb/query/',
    method: 'post',
    data
  })
}
