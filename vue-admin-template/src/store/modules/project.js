import { fetchList, createProject, updateProject, deleteProject } from '@/api/project'

const state = {
  list: [],
  total: 0,
  listLoading: true
}

const mutations = {
  SET_LIST: (state, list) => {
    state.list = list
  },
  SET_TOTAL: (state, total) => {
    state.total = total
  },
  SET_LOADING: (state, loading) => {
    state.listLoading = loading
  }
}

const actions = {
  // 获取项目列表
  getList({ commit }, query) {
    commit('SET_LOADING', true)
    return new Promise((resolve, reject) => {
      fetchList(query).then(response => {
        const { data } = response
        commit('SET_LIST', data.items)
        commit('SET_TOTAL', data.total)
        commit('SET_LOADING', false)
        resolve(data)
      }).catch(error => {
        commit('SET_LOADING', false)
        reject(error)
      })
    })
  },

  // 创建项目
  createProject({ dispatch }, data) {
    return new Promise((resolve, reject) => {
      createProject(data).then(response => {
        dispatch('getList') // 刷新列表
        resolve(response)
      }).catch(error => {
        reject(error)
      })
    })
  },

  // 更新项目
  updateProject({ dispatch }, data) {
    return new Promise((resolve, reject) => {
      updateProject(data).then(response => {
        dispatch('getList') // 刷新列表
        resolve(response)
      }).catch(error => {
        reject(error)
      })
    })
  },

  // 删除项目
  deleteProject({ dispatch }, id) {
    return new Promise((resolve, reject) => {
      deleteProject(id).then(response => {
        dispatch('getList') // 刷新列表
        resolve(response)
      }).catch(error => {
        reject(error)
      })
    })
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
} 