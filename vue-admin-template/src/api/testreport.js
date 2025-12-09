import request from '@/utils/request'

// 获取测试报告列表
export function getTestReports(listQueryParams) {
  const params = {
    // 计算 skip，确保 page 至少为 1
    skip: Math.max((listQueryParams.page - 1) * listQueryParams.limit, 0),
    limit: listQueryParams.limit
  }

  // 添加 status 参数 (如果存在)
  if (listQueryParams.status !== undefined) {
    params.status = listQueryParams.status
  }

  // 处理 date_range 参数，转换为 start_date 和 end_date (如果存在)
  if (listQueryParams.date_range && listQueryParams.date_range.length === 2) {
    params.start_date = listQueryParams.date_range[0]
    params.end_date = listQueryParams.date_range[1]
  }
  
  // 添加 project_id 参数 (如果存在)
  if (listQueryParams.project_id !== undefined) {
    params.project_id = listQueryParams.project_id
  }

  return request({
    url: '/rest/v1/testreports/',
    method: 'get',
    params // 使用构建好的 params 对象
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
