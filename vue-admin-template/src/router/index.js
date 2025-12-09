import Vue from 'vue'
import Router from 'vue-router'

Vue.use(Router)

/* Layout */
import Layout from '@/layout'

/**
 * Note: sub-menu only appear when route children.length >= 1
 * Detail see: https://panjiachen.github.io/vue-element-admin-site/guide/essentials/router-and-nav.html
 *
 * hidden: true                   if set true, item will not show in the sidebar(default is false)
 * alwaysShow: true               if set true, will always show the root menu
 *                                if not set alwaysShow, when item has more than one children route,
 *                                it will becomes nested mode, otherwise not show the root menu
 * redirect: noRedirect           if set noRedirect will no redirect in the breadcrumb
 * name:'router-name'             the name is used by <keep-alive> (must set!!!)
 * meta : {
    roles: ['admin','editor']    control the page roles (you can set multiple roles)
    title: 'title'               the name show in sidebar and breadcrumb (recommend set)
    icon: 'svg-name'/'el-icon-x' the icon show in the sidebar
    breadcrumb: false            if set false, the item will hidden in breadcrumb(default is true)
    activeMenu: '/example/list'  if set path, the sidebar will highlight the path you set
  }
 */

/**
 * constantRoutes
 * a base page that does not have permission requirements
 * all roles can be accessed
 */
export const constantRoutes = [
  {
    path: '/login',
    component: () => import('@/views/login/index'),
    hidden: true
  },

  {
    path: '/register',
    component: () => import('@/views/login/register'),
    hidden: true
  },

  {
    path: '/forgot-password',
    component: () => import('@/views/login/forgot-password'),
    hidden: true
  },

  {
    path: '/reset-password',
    component: () => import('@/views/login/reset-password'),
    hidden: true
  },

  {
    path: '/404',
    component: () => import('@/views/404'),
    hidden: true
  },

  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [{
      path: 'dashboard',
      name: 'Dashboard',
      component: () => import('@/views/dashboard/index'),
      meta: { title: '首页', icon: 'dashboard', keepAlive: true }
    }]
  },
  {
    path: '/design',
    component: Layout,
    alwaysShow: true,
    name: 'Design',
    meta: { title: '测试设计', icon: 'el-icon-s-management' },
    children: [
      {
        path: 'projects',
        name: 'DesignProjects',
        component: () => import('@/views/projects/index'),
        meta: { title: '项目管理' }
      },
      {
        path: 'projects/create',
        name: 'DesignProjectCreate',
        component: () => import('@/views/projects/create'),
        meta: { title: '创建项目', activeMenu: '/design/projects' },
        hidden: true
      },
      {
        path: 'projects/edit/:id',
        name: 'DesignProjectEdit',
        component: () => import('@/views/projects/edit'),
        meta: { title: '编辑项目', activeMenu: '/design/projects' },
        hidden: true
      },
      {
        path: 'modules',
        name: 'DesignModules',
        component: () => import('@/views/modules/index'),
        meta: { title: '模块管理' }
      },
      {
        path: 'modules/create',
        name: 'DesignModuleCreate',
        component: () => import('@/views/modules/create'),
        meta: { title: '创建模块', activeMenu: '/design/modules' },
        hidden: true
      },
      {
        path: 'modules/edit/:id',
        name: 'DesignModuleEdit',
        component: () => import('@/views/modules/edit'),
        meta: { title: '编辑模块', activeMenu: '/design/modules' },
        hidden: true
      },
      {
        path: 'interfaces',
        name: 'DesignInterfaces',
        component: () => import('@/views/interfaces/index'),
        meta: { title: '接口管理' }
      },
      {
        path: 'interfaces/create',
        name: 'DesignInterfaceCreate',
        component: () => import('@/views/interfaces/create'),
        meta: { title: '创建接口', activeMenu: '/design/interfaces' },
        hidden: true
      },
      {
        path: 'interfaces/edit/:id',
        name: 'DesignInterfaceEdit',
        component: () => import('@/views/interfaces/edit'),
        meta: { title: '编辑接口', activeMenu: '/design/interfaces' },
        hidden: true
      },
      {
        path: 'testcases',
        name: 'DesignTestCases',
        component: () => import('@/views/testcases/index'),
        meta: { title: '测试用例' }
      },
      {
        path: 'testcases/create',
        name: 'DesignTestCaseCreate',
        component: () => import('@/views/testcases/create'),
        meta: { title: '创建用例', activeMenu: '/design/testcases' },
        hidden: true
      },
      {
        path: 'testcases/edit/:id',
        name: 'DesignTestCaseEdit',
        component: () => import('@/views/testcases/edit'),
        meta: { title: '编辑用例', activeMenu: '/design/testcases' },
        hidden: true
      },
      {
        path: 'functions',
        name: 'DesignFunctions',
        component: () => import('@/views/functions/index'),
        meta: { title: '函数管理' }
      },
      {
        path: 'functions/create',
        name: 'DesignFunctionCreate',
        component: () => import('@/views/functions/create'),
        meta: { title: '创建函数', activeMenu: '/design/functions' },
        hidden: true
      },
      {
        path: 'functions/edit/:id',
        name: 'DesignFunctionEdit',
        component: () => import('@/views/functions/edit'),
        meta: { title: '编辑函数', activeMenu: '/design/functions' },
        hidden: true
      },
      {
        path: 'variables',
        name: 'DesignVariables',
        component: () => import('@/views/variable/index.vue'),
        meta: { title: '全局变量' }
      },
      {
        path: 'variables/create',
        name: 'DesignVariableCreate',
        component: () => import('@/views/variable/create.vue'),
        meta: { title: '新建变量', activeMenu: '/design/variables' },
        hidden: true
      },
      {
        path: 'variables/edit',
        name: 'DesignVariableEdit',
        component: () => import('@/views/variable/edit.vue'),
        meta: { title: '编辑变量', activeMenu: '/design/variables' },
        hidden: true
      }
    ]
  },
  {
    path: '/execution',
    component: Layout,
    alwaysShow: true,
    name: 'Execution',
    meta: { title: '执行与报告', icon: 'el-icon-s-claim' },
    children: [
      {
        path: 'testsuites',
        name: 'ExecSuites',
        component: () => import('@/views/testsuites/index'),
        meta: { title: '测试任务' }
      },
      {
        path: 'testsuites/create',
        name: 'ExecSuiteCreate',
        component: () => import('@/views/testsuites/create'),
        meta: { title: '创建任务', activeMenu: '/execution/testsuites' },
        hidden: true
      },
      {
        path: 'testsuites/edit/:id',
        name: 'ExecSuiteEdit',
        component: () => import('@/views/testsuites/edit'),
        meta: { title: '编辑任务', activeMenu: '/execution/testsuites' },
        hidden: true
      },
      {
        path: 'testreports',
        name: 'ExecReports',
        component: () => import('@/views/testreports/index'),
        meta: { title: '测试报告' }
      },
      {
        path: 'testreports/detail/:id',
        name: 'ExecReportDetail',
        component: () => import('@/views/testreports/detail'),
        meta: { title: '报告详情', activeMenu: '/execution/testreports' },
        hidden: true
      }
    ]
  },
  {
    path: '/assistant',
    component: Layout,
    alwaysShow: true,
    name: 'Assistant',
    meta: { title: 'AI助手', icon: 'el-icon-magic-stick' },
    children: [
      {
        path: 'index',
        name: 'AIAssistant',
        component: () => import('@/views/assistant/index'),
        meta: { title: '测试用例', icon: 'el-icon-magic-stick' }
      }
      ,
      {
        path: 'kb',
        name: 'AIKnowledgeBase',
        component: () => import('@/views/assistant/kb'),
        meta: { title: '知识库', icon: 'el-icon-document' }
      }
    ]
  },

  // 404 page must be placed at the end !!!
  { path: '*', redirect: '/404', hidden: true }
]

const createRouter = () => new Router({
  // mode: 'history', // require service support
  scrollBehavior: () => ({ y: 0 }),
  routes: constantRoutes
})

const router = createRouter()

// Detail see: https://github.com/vuejs/vue-router/issues/1234#issuecomment-357941465
export function resetRouter() {
  const newRouter = createRouter()
  router.matcher = newRouter.matcher // reset router
}

export default router
