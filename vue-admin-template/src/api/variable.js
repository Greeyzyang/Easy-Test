import request from '@/utils/request'

// 获取全局变量列表
export function getList(params) {
  return request({
    url: '/rest/v1/variables/',
    method: 'get',
    params
  })
}

// 获取单个变量详情
export function getVariable(id) {
  return request({
    url: `/rest/v1/variables/${id}/`,
    method: 'get'
  })
}

// 创建全局变量
export function createVariable(data) {
  return request({
    url: '/rest/v1/variables/',
    method: 'post',
    data
  })
}

// 更新全局变量
export function updateVariable(id, data) {
  return request({
    url: `/rest/v1/variables/${id}/`,
    method: 'put',
    data
  })
}

// 删除全局变量
export function deleteVariable(id) {
  return request({
    url: `/rest/v1/variables/${id}/`,
    method: 'delete'
  })
} 