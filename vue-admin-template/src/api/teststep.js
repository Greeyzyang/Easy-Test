import request from '@/utils/request'

export function createTestStep(data) {
  return request({
    url: '/rest/v1/teststeps',
    method: 'post',
    data
  })
}

export function updateTestStep(id, data) {
  return request({
    url: `/rest/v1/teststeps/${id}`,
    method: 'put',
    data
  })
}

export function deleteTestStep(id) {
  return request({
    url: `/rest/v1/teststeps/${id}`,
    method: 'delete'
  })
}

export function getTestStep(id) {
  return request({
    url: `/rest/v1/teststeps/${id}`,
    method: 'get'
  })
} 