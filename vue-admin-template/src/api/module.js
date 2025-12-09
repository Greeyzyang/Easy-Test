import request from '@/utils/request'

export function getModuleList(params = {}) {
  const { page = 1, limit = 100 } = params
  return request({
    url: '/rest/v1/modules/',
    method: 'get',
    params: {
      skip: page ? (page - 1) * (limit || 10) : 0,
      limit: limit || 100,
      name: params.name,
      project_id: params.project_id
    }
  })
}

export function fetchModule(id) {
  return request({
    url: `/rest/v1/modules/${id}/`,
    method: 'get'
  })
}

export function createModule(data) {
  return request({
    url: '/rest/v1/modules/',
    method: 'post',
    data
  })
}

export function updateModule(id, data) {
  return request({
    url: `/rest/v1/modules/${id}/`,
    method: 'put',
    data
  })
}

export function deleteModule(id) {
  return request({
    url: `/rest/v1/modules/${id}/`,
    method: 'delete'
  })
}

export function fetchModulesByProject(projectId) {
  return request({
    url: `/rest/v1/projects/${projectId}/modules/`,
    method: 'get'
  })
}

// 获取模块的接口列表
export function getModuleInterfaces(moduleId) {
  return request({
    url: `/rest/v1/modules/${moduleId}/interfaces/`,
    method: 'get'
  })
}

// 获取模块的测试用例列表
export function getModuleTestcases(moduleId) {
  return request({
    url: `/rest/v1/modules/${moduleId}/testcases/`,
    method: 'get'
  })
} 