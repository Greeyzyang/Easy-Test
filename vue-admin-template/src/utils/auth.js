import Cookies from 'js-cookie'

const TokenKey = 'X-Token'

export function getToken() {
  try {
    const token = localStorage.getItem(TokenKey)
    console.log('获取 token:', token ? '成功' : '未找到')
    return token
  } catch (error) {
    console.error('获取 token 时出错:', error)
    return null
  }
}

export function setToken(token) {
  try {
    if (!token) {
      console.warn('尝试保存空 token')
      return null
    }
    localStorage.setItem(TokenKey, token)
    console.log('Token 已保存')
    return token
  } catch (error) {
    console.error('保存 token 时出错:', error)
    return null
  }
}

export function removeToken() {
  try {
    localStorage.removeItem(TokenKey)
    console.log('Token 已移除')
    return true
  } catch (error) {
    console.error('移除 token 时出错:', error)
    return false
  }
}

