import request from '@/utils/request'

/**
 * 获取测试套件列表
 * @param {Object} params - 查询参数
 * @returns {Promise}
 */
export function getTestSuites(params) {
  return request({
    url: '/rest/v1/testsuites/',
    method: 'get',
    params
  })
}

/**
 * 获取单个测试套件详情
 * @param {String} id - 测试套件ID
 * @returns {Promise}
 */
export function getTestSuite(id) {
  return request({
    url: `/rest/v1/testsuites/${id}/`,
    method: 'get'
  })
}

/**
 * 创建测试套件
 * @param {Object} data - 测试套件数据
 * @returns {Promise}
 */
export function createTestSuite(data) {
  return request({
    url: '/rest/v1/testsuites/',
    method: 'post',
    data
  })
}

/**
 * 更新测试套件
 * @param {String} id - 测试套件ID
 * @param {Object} data - 更新的测试套件数据
 * @returns {Promise}
 */
export function updateTestSuite(id, data) {
  return request({
    url: `/rest/v1/testsuites/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除测试套件
 * @param {String} id - 测试套件ID
 * @returns {Promise}
 */
export function deleteTestSuite(id) {
  return request({
    url: `/rest/v1/testsuites/${id}/`,
    method: 'delete'
  })
}

/**
 * 执行测试套件
 * @param {String} id - 测试套件ID
 * @param {Object} data - 执行参数
 * @param {String} data.project_id - 项目ID
 * @param {String} data.env_name - 环境名称
 * @returns {Promise}
 */
export function executeTestSuite(id, data) {
  return request({
    url: `/rest/v1/testsuites/${id}/execute/`,
    method: 'post',
    data
  })
}

/**
 * 调度测试套件定时执行
 * @param {Object} data - 定时任务数据 (testsuite_id, cron_expression)
 * @returns {Promise}
 */
export function scheduleTestSuite(data) {
  return request({
    url: '/rest/v1/testsuites/schedule/',
    method: 'post',
    data
  })
}