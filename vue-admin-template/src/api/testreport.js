import request from '@/utils/request'

// 获取测试报告列表
export function getTestReports(listQueryParams) {
  const params = listQueryParams ? {
    skip: Math.max(((listQueryParams.page || 1) - 1) * (listQueryParams.limit || 10), 0),
    limit: listQueryParams.limit || 10,
    status: listQueryParams.status,
    project_id: listQueryParams.project_id
  } : {}

  // 处理 date_range 参数，转换为 start_date 和 end_date (如果存在)
  if (listQueryParams && listQueryParams.date_range && listQueryParams.date_range.length === 2) {
    params.start_date = listQueryParams.date_range[0]
    params.end_date = listQueryParams.date_range[1]
  }

  return request({
    url: '/rest/v1/testreports/',
    method: 'get',
    params
  })
}

// 获取测试报告详情
export function getTestReportDetail(id) {
  return request({
    url: `/rest/v1/testreports/${id}/`,
    method: 'get'
  })
}

// 删除测试报告
export function deleteTestReport(id) {
  return request({
    url: `/rest/v1/testreports/${id}/`,
    method: 'delete'
  })
}

// 导出测试报告
export function exportTestReport(id) {
  return request({
    url: `/rest/v1/testreports/${id}/export/`,
    method: 'get',
    responseType: 'blob'
  })
}
