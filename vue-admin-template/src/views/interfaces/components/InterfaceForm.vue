<template>
  <el-form ref="form" :model="form" :rules="rules" label-width="100px">
    <p class="tip">基础信息</p>
    <el-row :gutter="40">
      <el-col :span="18">
        <el-form-item label="接口请求" prop="url">
          <el-input v-model="form.url" placeholder="请输入接口地址" size="small">
            <el-select v-model="form.method" slot="prepend" style="width: 100px" size="small">
              <el-option
                v-for="method in methodOptions"
                :key="method"
                :label="method"
                :value="method"
                :class="method.toLowerCase()"
              />
            </el-select>
          </el-input>
        </el-form-item>
      </el-col>
    </el-row>

    <el-row :gutter="40">
      <el-col :span="10">
        <el-form-item label="接口名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入接口名称" size="small" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="所属模块" prop="moduleId">
          <el-select v-model="form.moduleId" placeholder="请选择模块" size="small" style="width: 100%">
            <el-option
              v-for="module in moduleOptions"
              :key="module.id"
              :label="module.name"
              :value="module.id"
            />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="6">
        <el-form-item label="版本" prop="version">
          <el-input v-model="form.version" placeholder="请输入版本号" size="small">
            <template slot="prepend">v</template>
          </el-input>
        </el-form-item>
      </el-col>
    </el-row>

    <el-row :gutter="40">
      <el-col :span="24">
        <el-form-item label="接口描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="请输入接口描述"
            size="small"
          />
        </el-form-item>
      </el-col>
    </el-row>

    <p class="tip">请求参数</p>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="请求头" name="headers">
        <div class="param-section">
          <param-table
            :params="headersList"
            @add="addParam('headers')"
            @remove="removeParam($event, 'headers')"
            title="请求头"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="请求体" name="body">
        <div class="body-section">
          <div class="body-header">
            <el-radio-group v-model="form.request_type" size="small">
              <el-radio-button label="JSON">JSON</el-radio-button>
              <el-radio-button label="FORM">表单</el-radio-button>
              <el-radio-button label="FILE">文件</el-radio-button>
            </el-radio-group>
            <div class="body-tools" v-if="form.request_type === 'JSON'">
              <el-button type="text" @click="formatJSON" icon="el-icon-magic-stick" size="small">格式化</el-button>
              <el-button type="text" @click="clearBody" icon="el-icon-delete" size="small">清空</el-button>
            </div>
          </div>
          
          <div v-if="form.request_type === 'JSON'" class="json-editor">
            <el-input
              v-model="form.body"
              type="textarea"
              :rows="12"
              placeholder="请输入JSON格式的请求体"
              class="body-input"
            />
          </div>

          <div v-else-if="form.request_type === 'FORM'" class="form-editor">
            <param-table
              :params="formParamsList"
              @add="addFormParam"
              @remove="removeFormParam"
              title="表单参数"
              :show-type="true"
            />
          </div>

          <div v-else class="file-upload">
            <el-upload
              class="upload-demo"
              action="#"
              :auto-upload="false"
              :on-change="handleFileChange"
              :file-list="fileList"
            >
              <el-button size="small" type="primary">选择文件</el-button>
              <div slot="tip" class="el-upload__tip">只能上传文件</div>
            </el-upload>
            
            <div class="file-params-section">
              <div class="section-title">附加参数</div>
              <param-table
                :params="fileParamsList"
                @add="addFileParam"
                @remove="removeFileParam"
                title="文件参数"
                :show-type="true"
              />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="查询参数" name="query">
        <div class="param-section">
          <param-table
            :params="paramsList"
            @add="addParam('params')"
            @remove="removeParam($event, 'params')"
            title="查询参数"
            :show-type="true"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-form>
</template>

<script>
import { getModuleList } from '@/api/module'
import ParamTable from './ParamTable.vue'

export default {
  name: 'InterfaceForm',
  components: {
    ParamTable
  },
  props: {
    initialData: {
      type: Object,
      default: () => ({})
    }
  },
  watch: {
    initialData: {
      handler(val) {
        if (val && Object.keys(val).length > 0) {
          // 处理版本号，移除可能存在的 'v' 前缀
          const version = val.version ? val.version.replace(/^v/i, '') : '1'
          
          this.form = {
            name: val.name || '',
            url: val.url || '',
            method: val.method || 'GET',
            moduleId: val.module_id || '',
            version: version,
            request_type: val.request_type || 'JSON',
            description: val.description || '',
            headers: val.headers || {},
            params: val.params || {},
            body: typeof val.body === 'object' ? JSON.stringify(val.body, null, 2) : val.body || ''
          }
          
          // 转换headers为列表形式
          this.headersList = Object.entries(val.headers || {}).map(([key, value]) => ({
            name: key,
            value: value,
            required: true,
            description: ''
          }))
          
          // 转换params为列表形式
          this.paramsList = Object.entries(val.params || {}).map(([key, value]) => ({
            name: key,
            value: value,
            required: true,
            description: ''
          }))
          
          // 如果是FORM类型，转换body为列表形式
          if (val.request_type === 'FORM' && val.body) {
            this.formParamsList = Object.entries(val.body).map(([key, value]) => ({
              name: key,
              value: value,
              required: true,
              description: ''
            }))
          }
        }
      },
      immediate: true
    }
  },
  data() {
    const validateJSON = (rule, value, callback) => {
      if (!value || this.form.request_type !== 'JSON') {
        callback()
        return
      }
      try {
        JSON.parse(value)
        callback()
      } catch (error) {
        callback(new Error('请输入有效的JSON格式'))
      }
    }

    return {
      activeTab: 'headers',
      methodOptions: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
      moduleOptions: [],
      paramsList: [],
      headersList: [],
      formParamsList: [],
      fileParamsList: [],
      fileList: [],
      form: {
        name: '',
        url: '',
        method: 'GET',
        moduleId: '',
        version: '1',
        request_type: 'JSON',
        headers: '',
        params: '',
        body: '',
        description: ''
      },
      rules: {
        name: [
          { required: true, message: '请输入接口名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        url: [
          { required: true, message: '请输入请求URL', trigger: 'blur' },
          { min: 1, max: 255, message: 'URL长度不能超过255个字符', trigger: 'blur' }
        ],
        method: [
          { required: true, message: '请选择请求方法', trigger: 'change' }
        ],
        moduleId: [
          { required: true, message: '请选择所属模块', trigger: 'change' }
        ],
        version: [
          { required: true, message: '请输入版本号', trigger: 'blur' },
          { pattern: /^\d+$/, message: '版本号只能是数字', trigger: 'blur' }
        ],
        body: [{ validator: validateJSON, trigger: 'blur' }]
      }
    }
  },
  created() {
    this.getModules()
  },
  methods: {
    async getModules() {
      try {
        const response = await getModuleList()
        if (response.code === '0' && response.data) {
          this.moduleOptions = (response.data || []).map(module => ({
            id: module.id,
            name: module.name
          }))
        } else {
          throw new Error(response.message || '获取模块列表失败')
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
        this.$message({
          message: '获取模块列表失败，请稍后重试',
          type: 'error'
        })
      }
    },
    validate() {
      return new Promise((resolve, reject) => {
        this.$refs.form.validate(valid => {
          if (valid) {
            const formData = this.getFormData()
            resolve(formData)
          } else {
            reject(new Error('表单验证失败'))
          }
        })
      })
    },
    getFormData() {
      // 处理headers
      const headers = this.headersList.reduce((acc, item) => {
        if (item.name && item.value !== undefined) {
          acc[item.name] = item.value
        }
        return acc
      }, {})

      // 处理params
      const params = this.paramsList.reduce((acc, item) => {
        if (item.name && item.value !== undefined) {
          acc[item.name] = item.value
        }
        return acc
      }, {})

      // 处理body
      let body = {}
      if (this.form.request_type === 'JSON') {
        try {
          body = this.form.body ? JSON.parse(this.form.body) : {}
        } catch (e) {
          console.warn('JSON parse failed:', e)
          body = {}
        }
      } else if (this.form.request_type === 'FORM') {
        body = this.formParamsList.reduce((acc, item) => {
          if (item.name) {
            acc[item.name] = this.convertParamValue(item)
          }
          return acc
        }, {})
      } else if (this.form.request_type === 'FILE') {
        body = this.fileParamsList.reduce((acc, item) => {
          if (item.name) {
            acc[item.name] = this.convertParamValue(item)
          }
          return acc
        }, {})
      }

      return {
        name: this.form.name,
        url: this.form.url,
        method: this.form.method,
        module_id: this.form.moduleId,
        version: this.form.version.replace(/^v/i, ''),
        description: this.form.description,
        request_type: this.form.request_type,
        headers,
        params,
        body
      }
    },
    convertParamValue(param) {
      switch (param.type) {
        case 'number':
          return Number(param.value)
        case 'boolean':
          return param.value.toLowerCase() === 'true'
        default:
          return param.value
      }
    },
    addParam(type) {
      const param = {
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      }
      if (type === 'params') {
        this.paramsList.push(param)
      } else {
        this.headersList.push(param)
      }
    },
    addFormParam() {
      this.formParamsList.push({
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      })
    },
    removeParam(index, type) {
      if (type === 'params') {
        this.paramsList.splice(index, 1)
      } else {
        this.headersList.splice(index, 1)
      }
    },
    removeFormParam(index) {
      this.formParamsList.splice(index, 1)
    },
    formatJSON() {
      try {
        if (this.form.body) {
          const parsed = JSON.parse(this.form.body)
          this.form.body = JSON.stringify(parsed, null, 2)
        }
      } catch (error) {
        this.$message.error('JSON格式不正确，无法格式化')
      }
    },
    clearBody() {
      this.form.body = ''
    },
    handleFileChange(file, fileList) {
      this.fileList = fileList
    },
    addFileParam() {
      this.fileParamsList.push({
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      })
    },
    removeFileParam(index) {
      this.fileParamsList.splice(index, 1)
    },
    reset() {
      this.$refs.form.resetFields()
      this.paramsList = []
      this.headersList = []
      this.formParamsList = []
      this.fileParamsList = []
      this.fileList = []
    },
    formatData() {
      return {
        ...this.getFormData(),
        headers: this.getFormData().headers.reduce((acc, { key, value }) => {
          if (key && value) {
            acc[key] = value
          }
          return acc
        }, {}),
        body: typeof this.getFormData().body === 'string' 
          ? JSON.parse(this.getFormData().body) 
          : this.getFormData().body,
        params: this.getFormData().params.reduce((acc, { key, value }) => {
          if (key && value) {
            acc[key] = value
          }
          return acc
        }, {})
      }
    }
  }
}
</script>

<style scoped>
.tip {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin: 20px 0;
  padding-left: 8px;
  border-left: 4px solid #409EFF;
}

.param-section {
  padding: 20px;
}

.body-section {
  padding: 20px;
}

.body-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.body-tools {
  display: flex;
  gap: 10px;
}

.json-editor {
  border: 1px solid #DCDFE6;
  border-radius: 4px;
}

.body-input {
  font-family: monospace;
}

.body-input :deep(.el-textarea__inner) {
  padding: 10px;
  font-family: monospace;
}

.file-upload {
  padding: 20px;
  border: 1px dashed #DCDFE6;
  border-radius: 4px;
}

.file-params-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #EBEEF5;
}

.section-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 15px;
  font-weight: 500;
}

/* 请求方法颜色 */
:deep(.get) {
  color: #67c23a;
}

:deep(.post) {
  color: #409eff;
}

:deep(.put) {
  color: #e6a23c;
}

:deep(.delete) {
  color: #f56c6c;
}

:deep(.patch) {
  color: #909399;
}
</style> 