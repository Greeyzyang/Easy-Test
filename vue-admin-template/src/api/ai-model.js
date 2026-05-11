import request from '@/utils/request'

export function getAIModels() {
  return request({
    url: '/rest/v1/ai-models/',
    method: 'get'
  })
}

export function createAIModel(data) {
  return request({
    url: '/rest/v1/ai-models/',
    method: 'post',
    data
  })
}

export function activateAIModel(id) {
  return request({
    url: `/rest/v1/ai-models/${id}/activate`,
    method: 'put'
  })
}

export function deactivateAIModel(id) {
  return request({
    url: `/rest/v1/ai-models/${id}/deactivate`,
    method: 'put'
  })
}

export function updateAIModel(id, data) {
  return request({
    url: `/rest/v1/ai-models/${id}`,
    method: 'put',
    data
  })
}

export function deleteAIModel(id) {
  return request({
    url: `/rest/v1/ai-models/${id}`,
    method: 'delete'
  })
}

export function testConnection(data) {
  return request({
    url: '/rest/v1/ai-models/test-connection',
    method: 'post',
    data
  })
}
