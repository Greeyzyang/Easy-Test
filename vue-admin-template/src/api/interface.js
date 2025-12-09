import request from '@/utils/request'

export function getInterfaceList(params) {
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
