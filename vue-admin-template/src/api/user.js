import request from '@/utils/request'

// 用户登录
export function login(data) {
  // 创建 FormData 对象
  const formData = new URLSearchParams()
  formData.append('username', data.email)
  formData.append('password', data.password)
  return request({
    url: '/auth/jwt/login',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

// 用户注册
export function register(data) {
  return request({
    url: '/auth/register',
    method: 'post',
    data
  })
}

// 请求发送邮箱验证链接
export function requestVerifyToken(email) {
  return request({
    url: '/auth/request-verify-token',
    method: 'post',
    data: { email }
  })
}

// 验证邮箱
export function verifyEmail(token) {
  return request({
    url: '/auth/verify',
    method: 'post',
    data: { token }
  })
}

// 获取用户信息
export function getInfo() {
  return request({
    url: '/users/me',
    method: 'get'
  })
}

// 更新用户信息
export function updateUserInfo(data) {
  return request({
    url: '/users/me',
    method: 'patch',
    data
  })
}

// 更新用户密码
export function updatePassword(data) {
  return request({
    url: '/users/me/password',
    method: 'patch',
    data
  })
}

// 用户登出
export function logout() {
  return request({
    url: '/auth/jwt/logout',
    method: 'post'
  })
}

// 忘记密码 - 请求重置
export function forgotPassword(email) {
  return request({
    url: '/auth/forgot-password',
    method: 'post',
    data: { email }
  })
}

// 重置密码
export function resetPassword(data) {
  return request({
    url: '/auth/reset-password',
    method: 'post',
    data
  })
}
