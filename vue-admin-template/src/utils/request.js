import axios from 'axios'
import { MessageBox, Message } from 'element-ui'
import store from '@/store'
import { getToken, setToken } from '@/utils/auth'
import router from '@/router'

// create an axios instance
const service = axios.create({
  baseURL: process.env.VUE_APP_BASE_API, // url = base url + request url
  withCredentials: true, // 启用凭证，允许跨域请求携带cookie
  timeout: 30000
})

// 防止重复弹出登录框
let isRelogin = false

// request interceptor
service.interceptors.request.use(
  config => {
    const token = getToken()
    
    console.log('Token 检查:', {
      exists: !!token,
      type: typeof token,
      length: token ? token.length : 0,
      value: token ? token.substring(0, 10) + '...' : null
    })
    
    if (token && typeof token === 'string') {
      config.headers['Authorization'] = `Bearer ${token}`
      console.log('请求头设置:', {
        url: config.url,
        headers: config.headers
      })
    } else {
      console.warn('警告: 未找到有效token，请求可能失败')
    }
    return config
  },
  error => {
    console.error('请求拦截器错误:', error)
    return Promise.reject(error)
  }
)

// response interceptor
service.interceptors.response.use(
  /**
   * If you want to get http information such as headers or status
   * Please return  response => response
  */

  /**
   * Determine the request status by custom code
   * Here is just an example
   * You can also judge the status by HTTP Status Code
   */
  response => {
    const res = response.data
    console.log('收到响应:', {
      url: response.config.url,
      status: response.status,
      data: res
    })

    // 如果响应成功，直接返回数据
    if (response.status >= 200 && response.status < 300) {
      // 如果是登录接口，特殊处理返回的 token
      if (response.config.url.includes('/auth/jwt/login')) {
        let token = null
        // fastapi-users 默认返回 access_token
        if (res && res.access_token) {
          token = res.access_token
        }
        // 兼容旧版后端自定义包装
        if (!token && res && res.data && res.data['X-Token']) {
          token = res.data['X-Token']
        }
        if (token) {
          setToken(token)
          console.log('Token已设置')
        } else {
          console.error('登录响应中未找到token')
        }
        return res
      }
      return res
    }

    // 错误处理
    const errMsg = res.msg || res.message || '请求错误'
    Message({
      message: errMsg,
      type: 'error',
      duration: 5 * 1000
    })

    return Promise.reject(new Error(errMsg))
  },
  error => {
    console.error('响应错误:', error)
    let message = '网络请求失败'

    const reqUrl = (error && error.config && error.config.url) ? error.config.url : ''
    // 对邮箱验证相关接口，避免全局重复弹错（由业务页面自行提示）
    const suppressGlobalMessage = reqUrl.includes('/auth/request-verify-token') || reqUrl.includes('/auth/verify')

    if (error.code === 'ECONNABORTED' && error.message.indexOf('timeout') !== -1) {
      message = '请求超时，请重试'
    } else if (error.response) {
      const { status, data } = error.response
      message = data.msg || data.message || error.message

      // 处理 404 错误
      if (status === 404) {
        router.push('/404')
      }

      // 处理 401 错误
      if (status === 401) {
        if (!isRelogin) {
          isRelogin = true
          MessageBox.confirm('您已登出，可以取消以停留在此页面，或重新登录', '确认登出', {
            confirmButtonText: '重新登录',
            cancelButtonText: '取消',
            type: 'warning'
          }).then(() => {
            store.dispatch('user/resetToken').then(() => {
              location.reload()
            })
          }).finally(() => {
            isRelogin = false
          })
        }
      }
    }

    if (!suppressGlobalMessage) {
      Message({
        message: message,
        type: 'error',
        duration: 5 * 1000
      })
    }
    return Promise.reject(new Error(message))
  }
)

export default service
