import { login, logout, getInfo } from '@/api/user'
import { getToken, setToken, removeToken } from '@/utils/auth'
import { resetRouter } from '@/router'

const getDefaultState = () => {
  return {
    token: getToken(),
    name: '',
    avatar: '',
    email: '',
    is_active: false,
    is_verified: false,
    is_superuser: false
  }
}

const state = getDefaultState()

const mutations = {
  RESET_STATE: (state) => {
    Object.assign(state, getDefaultState())
  },
  SET_TOKEN: (state, token) => {
    state.token = token
  },
  SET_NAME: (state, name) => {
    state.name = name
  },
  SET_AVATAR: (state, avatar) => {
    state.avatar = avatar
  },
  SET_EMAIL: (state, email) => {
    state.email = email
  },
  SET_USER_INFO: (state, userInfo) => {
    state.email = userInfo.email
    state.name = userInfo.name
  }
}

const actions = {
  // user login
  login({ commit }, userInfo) {
    const { email, password } = userInfo
    return new Promise((resolve, reject) => {
      login({ email: email?.trim(), password: password }).then(response => {
        const res = response
        let token = null
        if (res && res.access_token) {
          token = res.access_token
        } else if (res && res.data && res.data['X-Token']) {
          token = res.data['X-Token']
        } else {
          token = getToken()
        }
        if (token) {
          commit('SET_TOKEN', token)
          setToken(token)
        }
        resolve()
      }).catch(error => {
        reject(error)
      })
    })
  },

  // get user info
  getInfo({ commit }) {
    return new Promise((resolve, reject) => {
      getInfo().then(response => {
        const res = response
        // 兼容两种响应格式：直接返回用户对象 或 {data: {...}}
        const userData = (res && res.data && res.data.email) ? res.data : res
        if (!userData || !userData.email) {
          reject('Verification failed, please Login again.')
          return
        }
        const info = {
          email: userData.email,
          name: userData.username || userData.name || ''
        }
        commit('SET_USER_INFO', info)
        commit('SET_AVATAR', 'https://wpimg.wallstcn.com/f778738c-e4f8-4870-b634-56703b4acafe.gif')
        resolve(info)
      }).catch(error => {
        reject(error)
      })
    })
  },

  // user logout
  logout({ commit, state }) {
    return new Promise((resolve, reject) => {
      logout(state.token).then(() => {
        removeToken() // must remove  token  first
        resetRouter()
        commit('RESET_STATE')
        resolve()
      }).catch(error => {
        reject(error)
      })
    })
  },

  // remove token
  resetToken({ commit }) {
    return new Promise(resolve => {
      removeToken() // must remove  token  first
      commit('RESET_STATE')
      resolve()
    })
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
}
