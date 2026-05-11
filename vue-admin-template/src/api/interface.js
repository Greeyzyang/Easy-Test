import request from '@/utils/request'

export function getInterfaceList(listQueryParams) {
  const params = {
    skip: Math.max(((listQueryParams.page || 1) - 1) * (listQueryParams.limit || 20), 0),
    limit: listQueryParams.limit || 20,
    name: listQueryParams.name,
    module_id: listQueryParams.module_id || listQueryParams.moduleId
  }
  return request({
    url: '/rest/v1/interfaces/',
    method: 'get',
    params
  })
}

export function getInterface(id) {
  return request({
    url: `/rest/v1/interfaces/${id}/`,
    method: 'get'
  })
}

export function createInterface(data) {
  return request({
    url: '/rest/v1/interfaces/',
    method: 'post',
    data
  })
}

export function updateInterface(id, data) {
  return request({
    url: `/rest/v1/interfaces/${id}/`,
    method: 'put',
    data
  })
}

export function deleteInterface(id) {
  return request({
    url: `/rest/v1/interfaces/${id}/`,
    method: 'delete'
  })
}

export function importSwagger(data) {
  return request({
    url: '/rest/v1/interfaces/import-swagger/',
    method: 'post',
    data
  })
}

export function getImportStatus(taskId) {
  return request({
    url: `/rest/v1/interfaces/import-status/${taskId}/`,
    method: 'get'
  })
}
