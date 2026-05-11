import request from '@/utils/request'

export function getDashboardMetrics() {
  return request({
    url: '/rest/v1/metrics/dashboard',
    method: 'get'
  })
}

export function getJiraBugDistribution(projectKey, startDate, endDate, fixVersions = []) {
  const params = { project_key: projectKey, start_date: startDate, end_date: endDate, fix_versions: fixVersions }
  const paramsSerializer = (p) => {
    const parts = []
    Object.keys(p).forEach((key) => {
      const val = p[key]
      if (val === undefined || val === null || (Array.isArray(val) && val.length === 0)) return
      if (Array.isArray(val)) {
        val.forEach(v => parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`))
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
      }
    })
    return parts.join('&')
  }
  return request({
    url: '/rest/v1/metrics/jira/bug-distribution',
    method: 'get',
    params,
    paramsSerializer,
    timeout: 60000
  })
}

export function getJiraMemberEfficiency(projectKey, fixVersions = [], startDate = null, endDate = null) {
  const params = {
    project_key: projectKey,
    fix_versions: fixVersions,
    start_date: startDate,
    end_date: endDate
  }
  const paramsSerializer = (p) => {
    const parts = []
    Object.keys(p).forEach((key) => {
      const val = p[key]
      if (val === undefined || val === null || (Array.isArray(val) && val.length === 0)) return
      if (Array.isArray(val)) {
        val.forEach(v => parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`))
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
      }
    })
    return parts.join('&')
  }
  return request({
    url: '/rest/v1/metrics/jira/member-efficiency',
    method: 'get',
    params,
    paramsSerializer,
    timeout: 60000
  })
}

export function getJiraFixVersions(projectKey) {
  return request({
    url: '/rest/v1/metrics/jira/fix-versions',
    method: 'get',
    params: { project_key: projectKey }
  })
}

export function getJiraVersionTrend(projectKey, fixVersions = []) {
  const params = { project_key: projectKey, fix_versions: fixVersions }
  const paramsSerializer = (p) => {
    const parts = []
    Object.keys(p).forEach((key) => {
      const val = p[key]
      if (val === undefined || val === null || (Array.isArray(val) && val.length === 0)) return
      if (Array.isArray(val)) {
        val.forEach(v => parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`))
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
      }
    })
    return parts.join('&')
  }
  return request({
    url: '/rest/v1/metrics/jira/version-trend',
    method: 'get',
    params,
    paramsSerializer,
    timeout: 60000
  })
}
