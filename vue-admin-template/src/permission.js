import router from './router'
import store from './store'
import { Message } from 'element-ui'
import NProgress from 'nprogress' // progress bar
import 'nprogress/nprogress.css' // progress bar style
import { getToken } from '@/utils/auth'
import getPageTitle from '@/utils/get-page-title'

NProgress.configure({ showSpinner: false }) // NProgress Configuration

const whiteList = ['/login', '/register', '/forgot-password', '/reset-password', '/404'] // 不需要重定向的白名单

router.beforeEach(async(to, from, next) => {
  // start progress bar
  NProgress.start()

  // set page title
  document.title = getPageTitle(to.meta.title)

  const hasToken = !!getToken()

  if (hasToken) {
    if (to.path === '/login') {
      // if is logged in, redirect to the home page
      next({ path: '/' })
      NProgress.done()
    } else {
      // determine whether the user has obtained his permission roles through getInfo
      const hasGetUserInfo = store.getters.name
      if (hasGetUserInfo) {
        next()
      } else {
        try {
          // get user info
          await store.dispatch('user/getInfo')
          next()
        } catch (error) {
          // remove token and go to login page to re-login
          await store.dispatch('user/resetToken')
          Message.error(error || 'Has Error')
          next(`/login?redirect=${to.path}`)
          NProgress.done()
        }
      }
    }
  } else {
    // 无本地token时，尝试通过Cookie获取用户信息（fastapi-users cookie 认证）
    if (whiteList.indexOf(to.path) !== -1) {
      next()
    } else {
      try {
        await store.dispatch('user/getInfo')
        next()
      } catch (error) {
        next(`/login?redirect=${to.path}`)
        NProgress.done()
      }
    }
  }
})

router.afterEach(() => {
  // finish progress bar
  NProgress.done()
})
