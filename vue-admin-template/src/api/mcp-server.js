import request from '@/utils/request'

export function getMCPServerList(listQueryParams) {
  const params = listQueryParams ? {
    skip: Math.max(((listQueryParams.page || 1) - 1) * (listQueryParams.limit || 10), 0),
    limit: listQueryParams.limit || 10,
    name: listQueryParams.name
  } : {}
  return request({
    url: '/rest/v1/mcp-servers/',
    method: 'get',
    params
  })
}

export function getMCPServerDetail(id) {
  return request({
    url: `/rest/v1/mcp-servers/${id}/`,
    method: 'get'
  })
}

export function createMCPServer(data) {
  return request({
    url: '/rest/v1/mcp-servers/',
    method: 'post',
    data
  })
}

export function updateMCPServer(id, data) {
  return request({
    url: `/rest/v1/mcp-servers/${id}/`,
    method: 'put',
    data
  })
}

export function deleteMCPServer(id) {
  return request({
    url: `/rest/v1/mcp-servers/${id}/`,
    method: 'delete'
  })
}

export function toggleMCPServer(id) {
  return request({
    url: `/rest/v1/mcp-servers/${id}/toggle/`,
    method: 'patch'
  })
}
