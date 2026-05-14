import request from '@/utils/request'

export function listTencentDocsSheets(fileId) {
  return request({
    url: '/rest/v1/tencent-docs/sheets/',
    method: 'get',
    params: { file_id: fileId }
  })
}

export function convertTestcases(data) {
  return request({
    url: '/rest/v1/tencent-docs/convert/testcases/',
    method: 'post',
    data
  })
}
