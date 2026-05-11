import request from '@/utils/request'

export function getPerformanceTestList(params) {
  const query = {
    skip: Math.max(((params.page || 1) - 1) * (params.limit || 10), 0),
    limit: params.limit || 10,
    name: params.name,
    project_id: params.project_id
  }
  return request({
    url: '/rest/v1/performance-tests/',
    method: 'get',
    params: query
  })
}

export function getPerformanceTest(id) {
  return request({
    url: `/rest/v1/performance-tests/${id}/`,
    method: 'get'
  })
}

export function createPerformanceTest(data) {
  return request({
    url: '/rest/v1/performance-tests/',
    method: 'post',
    data
  })
}

export function updatePerformanceTest(id, data) {
  return request({
    url: `/rest/v1/performance-tests/${id}/`,
    method: 'put',
    data
  })
}

export function deletePerformanceTest(id) {
  return request({
    url: `/rest/v1/performance-tests/${id}/`,
    method: 'delete'
  })
}

export function executePerformanceTest(id) {
  return request({
    url: `/rest/v1/performance-tests/${id}/execute/`,
    method: 'post'
  })
}

export function stopPerformanceTest(id) {
  return request({
    url: `/rest/v1/performance-tests/${id}/stop/`,
    method: 'post'
  })
}

export function getPerformanceTestReports(performanceTestId, params) {
  const query = {
    skip: Math.max(((params.page || 1) - 1) * (params.limit || 10), 0),
    limit: params.limit || 10
  }
  return request({
    url: `/rest/v1/performance-tests/${performanceTestId}/reports/`,
    method: 'get',
    params: query
  })
}

export function getPerformanceTestReport(reportId) {
  return request({
    url: `/rest/v1/performance-tests/reports/${reportId}/`,
    method: 'get'
  })
}
