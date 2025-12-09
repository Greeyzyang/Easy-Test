import request from '@/utils/request'


// 获取项目列表
export function getProjectList(params) {
  return request({
    url: '/rest/v1/projects/',
    method: 'get',
    params
  })
}

// 获取项目详情
export function getProjectDetail(id) {
  return request({
    url: `/rest/v1/projects/${id}/`,
    method: 'get'
  })
}

// 创建项目
export function createProject(data) {
  return request({
    url: '/rest/v1/projects/',
    method: 'post',
    data
  })
}

// 更新项目
export function updateProject(id, data) {
  return request({
    url: `/rest/v1/projects/${id}/`,
    method: 'put',
    data
  })
}

// 删除项目
export function deleteProject(id) {
  return request({
    url: `/rest/v1/projects/${id}/`,
    method: 'delete'
  })
} 