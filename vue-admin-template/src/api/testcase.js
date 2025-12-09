import request from '@/utils/request'

// 测试用例相关接口
export function getTestCases(params) {
  return request({
    url: '/rest/v1/testcases/',
    method: 'get',
    params
  })
}

export function getTestCase(id) {
  return request({
    url: `/rest/v1/testcases/${id}/`,
    method: 'get'
  })
}

export function createTestCase(data) {
  return request({
    url: '/rest/v1/testcases/',
    method: 'post',
    data
  })
}

export function updateTestCase(id, data) {
  return request({
    url: `/rest/v1/testcases/${id}/`,
    method: 'put',
    data
  })
}

export function deleteTestCase(id) {
  return request({
    url: `/rest/v1/testcases/${id}/`,
    method: 'delete'
  })
}

// 测试步骤相关接口
export function getTestSteps(params) {
  return request({
    url: '/rest/v1/teststeps/',
    method: 'get',
    params
  })
}

export function getTestStep(id) {
  return request({
    url: `/rest/v1/teststeps/${id}/`,
    method: 'get'
  })
}

export function createTestStep(data) {
  return request({
    url: '/rest/v1/teststeps/',
    method: 'post',
    data
  })
}

export function updateTestStep(id, data) {
  return request({
    url: `/rest/v1/teststeps/${id}/`,
    method: 'put',
    data
  })
}

export function deleteTestStep(id) {
  return request({
    url: `/rest/v1/teststeps/${id}/`,
    method: 'delete'
  })
}

// 测试步骤排序
export function updateStepsOrder(caseId, data) {
  return request({
    url: `/rest/v1/testcases/${caseId}/steps/reorder/`,
    method: 'put',
    data
  })
}