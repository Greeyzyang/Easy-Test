import request from '@/utils/request'

export function getFunctionList(listQueryParams) {
  const params = listQueryParams ? {
    skip: Math.max(((listQueryParams.page || 1) - 1) * (listQueryParams.limit || 10), 0),
    limit: listQueryParams.limit || 10,
    name: listQueryParams.name
  } : {}
  return request({
    url: '/rest/v1/functions/',
    method: 'get',
    params
  })
}

export function getFunction(id) {
  return request({
    url: `/rest/v1/functions/${id}/`,
    method: 'get'
  })
}

export function createFunction(data) {
  return request({
    url: '/rest/v1/functions/',
    method: 'post',
    data
  })
}

export function updateFunction(id, data) {
  return request({
    url: `/rest/v1/functions/${id}/`,
    method: 'put',
    data
  })
}

export function deleteFunction(id) {
  return request({
    url: `/rest/v1/functions/${id}/`,
    method: 'delete'
  })
}

export function runFunction(data) {
  return request({
    url: '/rest/v1/functions/run/',
    method: 'post',
    data
  })
} 