<template>
  <div class="step-config-form">
    <el-form ref="form" :model="formData" :rules="rules" label-width="120px">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="请求配置" name="request">
          <!-- 请求头配置 -->
          <el-form-item label="请求头" prop="headers">
            <el-alert
              v-if="!formData.headers.length"
              title="可以添加自定义请求头，如 Content-Type、Authorization 等"
              type="info"
              :closable="false"
              show-icon
            />
            <param-table
              :params="formData.headers"
              title="请求头"
              @add="addHeader"
              @remove="removeHeader"
            >
              <template #tip>
                <el-tooltip content="常用请求头" placement="top">
                  <el-dropdown @command="handleAddCommonHeader" trigger="click">
                    <el-button type="text" icon="el-icon-plus">
                      常用请求头<i class="el-icon-arrow-down el-icon--right"></i>
                    </el-button>
                    <el-dropdown-menu slot="dropdown">
                      <el-dropdown-item command="json">Content-Type: application/json</el-dropdown-item>
                      <el-dropdown-item command="form">Content-Type: application/x-www-form-urlencoded</el-dropdown-item>
                      <el-dropdown-item command="multipart">Content-Type: multipart/form-data</el-dropdown-item>
                    </el-dropdown-menu>
                  </el-dropdown>
                </el-tooltip>
              </template>
            </param-table>
          </el-form-item>

          <!-- 请求参数配置 -->
          <el-form-item label="请求参数" prop="paramType">
            <el-radio-group v-model="formData.paramType" style="margin-bottom: 15px">
              <el-radio label="query">Query参数</el-radio>
              <el-radio label="body">Body参数</el-radio>
            </el-radio-group>

            <template v-if="formData.paramType === 'query'">
              <param-table
                :params="formData.query_params"
                title="Query参数"
                @add="addQueryParam"
                @remove="removeQueryParam"
              />
            </template>

            <template v-else>
              <el-form-item label="请求体类型" label-width="120px" prop="body_type">
                <el-radio-group v-model="formData.body_type">
                  <el-radio label="json">JSON</el-radio>
                  <el-radio label="form">Form Data</el-radio>
                </el-radio-group>
              </el-form-item>

              <template v-if="formData.body_type === 'json'">
                <el-form-item prop="body_json">
                  <el-input
                    type="textarea"
                    v-model="formData.body_json"
                    :rows="8"
                    placeholder="请输入JSON格式的请求体"
                    @blur="formatJSON"
                  />
                  <div class="json-tools">
                    <el-button type="text" size="small" @click="formatJSON">格式化JSON</el-button>
                    <el-button type="text" size="small" @click="compactJSON">压缩JSON</el-button>
                  </div>
                </el-form-item>
              </template>

              <template v-else>
                <param-table
                  :params="formData.body_form"
                  title="Form参数"
                  @add="addFormParam"
                  @remove="removeFormParam"
                />
              </template>
            </template>
          </el-form-item>
        </el-tab-pane>

        <el-tab-pane label="验证配置" name="validation">
          <el-form-item label="期望状态码" prop="expected_response_code">
            <el-input-number
              v-model="formData.expected_response_code"
              :min="100"
              :max="599"
              controls-position="right"
              style="width: 180px"
            >
              <template slot="prepend">
                <el-tooltip content="HTTP状态码参考" placement="top">
                  <el-dropdown @command="handleStatusCodeSelect" trigger="click">
                    <el-button type="text">
                      常用状态码<i class="el-icon-arrow-down el-icon--right"></i>
                    </el-button>
                    <el-dropdown-menu slot="dropdown">
                      <el-dropdown-item command="200">200 - 成功</el-dropdown-item>
                      <el-dropdown-item command="201">201 - 已创建</el-dropdown-item>
                      <el-dropdown-item command="400">400 - 请求错误</el-dropdown-item>
                      <el-dropdown-item command="401">401 - 未授权</el-dropdown-item>
                      <el-dropdown-item command="404">404 - 未找到</el-dropdown-item>
                      <el-dropdown-item command="500">500 - 服务器错误</el-dropdown-item>
                    </el-dropdown-menu>
                  </el-dropdown>
                </el-tooltip>
              </template>
            </el-input-number>
          </el-form-item>

          <el-form-item label="断言配置" prop="assertions">
            <el-alert
              v-if="!formData.assertions.length"
              title="添加断言来验证接口响应是否符合预期"
              type="info"
              :closable="false"
              show-icon
            />
            <el-table :data="formData.assertions" border style="width: 100%">
              <el-table-column label="断言类型" width="180">
                <template slot-scope="scope">
                  <el-select v-model="scope.row.operator" placeholder="请选择断言类型">
                    <el-option
                      v-for="item in assertionOperators"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    >
                      <span>{{ item.label }}</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">{{ item.value }}</span>
                    </el-option>
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="JSON路径" min-width="250">
                <template slot-scope="scope">
                  <el-input 
                    v-model="scope.row.path" 
                    placeholder="请输入JSON路径，如: $.data.id"
                  >
                    <template slot="prepend">
                      <el-tooltip content="JSON路径示例" placement="top">
                        <i class="el-icon-question"></i>
                      </el-tooltip>
                    </template>
                  </el-input>
                </template>
              </el-table-column>
              <el-table-column label="期望值" min-width="250">
                <template slot-scope="scope">
                  <el-input 
                    v-model="scope.row.value"
                    :placeholder="getExpectedPlaceholder(scope.row.operator)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="160" align="center" fixed="right">
                <template slot-scope="scope">
                  <div class="operation-buttons">
                    <el-button 
                      size="mini" 
                      type="success"
                      @click="duplicateAssertion(scope.$index)"
                    >复制</el-button>
                    <el-button 
                      size="mini" 
                      type="danger"
                      @click="removeAssertion(scope.$index)"
                    >删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top: 10px">
              <el-button type="primary" size="small" @click="addAssertion" icon="el-icon-plus">添加断言</el-button>
              <el-button type="text" size="small" @click="clearAssertions" icon="el-icon-delete">清空断言</el-button>
            </div>
          </el-form-item>
        </el-tab-pane>

        <el-tab-pane label="变量提取" name="variables">
          <el-form-item label="变量配置" prop="extract_variables">
            <el-alert
              v-if="!formData.extract_variables.length"
              title="从响应中提取变量，可用于后续测试步骤"
              type="info"
              :closable="false"
              show-icon
            />
            <el-table :data="formData.extract_variables" border style="width: 100%">
              <el-table-column label="变量名称" min-width="180">
                <template slot-scope="scope">
                  <el-input 
                    v-model="scope.row.name" 
                    placeholder="请输入变量名称"
                  />
                </template>
              </el-table-column>
              <el-table-column label="数据来源" width="120">
                <template slot-scope="scope">
                  <el-select v-model="scope.row.source" placeholder="请选择数据来源">
                    <el-option label="响应体" value="RESPONSE">
                      <span>响应体</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">使用JSONPath</span>
                    </el-option>
                    <el-option label="响应头" value="HEADERS">
                      <span>响应头</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">Header名称</span>
                    </el-option>
                    <el-option label="Cookie" value="COOKIES">
                      <span>Cookie</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">Cookie名称</span>
                    </el-option>
                    <el-option label="请求体" value="BODY">
                      <span>请求体</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">使用JSONPath</span>
                    </el-option>
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="提取表达式" min-width="250">
                <template slot-scope="scope">
                  <el-input 
                    v-model="scope.row.path" 
                    :placeholder="getExtractionPlaceholder(scope.row.source)"
                  >
                    <template slot="prepend">
                      <el-tooltip :content="getExtractionTip(scope.row.source)" placement="top">
                        <i class="el-icon-question"></i>
                      </el-tooltip>
                    </template>
                  </el-input>
                </template>
              </el-table-column>
              <el-table-column label="变量描述" min-width="200">
                <template slot-scope="scope">
                  <el-input v-model="scope.row.description" placeholder="请输入变量用途描述" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="160" align="center" fixed="right">
                <template slot-scope="scope">
                  <div class="operation-buttons">
                    <el-button 
                      size="mini" 
                      type="success"
                      @click="duplicateExtractVariable(scope.$index)"
                    >复制</el-button>
                    <el-button 
                      size="mini" 
                      type="danger"
                      @click="removeExtractVariable(scope.$index)"
                    >删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top: 10px">
              <el-button type="primary" size="small" @click="addExtractVariable" icon="el-icon-plus">添加变量</el-button>
              <el-button type="text" size="small" @click="clearExtractVariables" icon="el-icon-delete">清空变量</el-button>
            </div>
          </el-form-item>
        </el-tab-pane>
      </el-tabs>

      <!-- 底部按钮 -->
      <div class="form-footer">
        <el-button @click="handleCancel">取 消</el-button>
        <el-button type="primary" @click="handleConfirm">确 定</el-button>
      </div>
    </el-form>
  </div>
</template>

<script>
import ParamTable from '@/components/Common/ParamTable'
import Sortable from 'sortablejs'
import { getFunctionList } from '@/api/function'

export default {
  name: 'StepConfigForm',
  components: {
    ParamTable
  },
  props: {
    initialData: {
      type: Object,
      required: true
    },
    visible: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      activeTab: 'request',
      formData: {
        headers: [],
        query_params: [],
        paramType: 'query',
        body_type: 'form',
        body_json: '',
        body_form: [],
        expected_response_code: 200,
        assertions: [],
        extract_variables: [],
      },
      rules: {
        expected_response_code: [
          { required: true, message: '请输入期望状态码', trigger: 'blur' },
          { type: 'number', min: 100, max: 599, message: '状态码范围为100-599', trigger: 'blur' }
        ],
        body_json: [
          { validator: this.validateJSON, trigger: 'blur' }
        ]
      },
      assertionOperators: [
        { label: '等于', value: 'equal' },
        { label: '不等于', value: 'not_equal' },
        { label: '包含', value: 'contains' },
        { label: '不包含', value: 'not_contains' },
        { label: '大于', value: 'greater_than' },
        { label: '小于', value: 'less_than' },
        { label: '存在', value: 'exists' },
        { label: '不存在', value: 'not_exists' }
      ],
    }
  },
  watch: {
    initialData: {
      handler(newVal) {
        if (newVal) {
          this.formData = {
            ...newVal,
            headers: Array.isArray(newVal.headers) ? newVal.headers : [],
            query_params: Array.isArray(newVal.query_params) ? newVal.query_params : [],
            body_form: Array.isArray(newVal.body_form) ? newVal.body_form : [],
            extract_variables: Array.isArray(newVal.extract_variables) ? newVal.extract_variables : [],
            assertions: Array.isArray(newVal.assertions) ? newVal.assertions.map(assertion => ({
              path: assertion.path || '',
              value: assertion.value,
              operator: assertion.operator || 'equal',
              description: assertion.description || ''
            })) : [],
          }
        }
      },
      immediate: true
    },
    'formData.steps.length'(val) {
      this.$nextTick(() => {
        this.initSortable()
      })
    }
  },
  created() {
  },
  mounted() {
  },
  methods: {
    // 请求头相关方法
    addHeader() {
      this.formData.headers.push({
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      })
    },
    removeHeader(index) {
      this.formData.headers.splice(index, 1)
    },
    handleAddCommonHeader(type) {
      const headers = {
        json: { name: 'Content-Type', value: 'application/json' },
        form: { name: 'Content-Type', value: 'application/x-www-form-urlencoded' },
        multipart: { name: 'Content-Type', value: 'multipart/form-data' }
      }
      const header = headers[type]
      if (header) {
        this.formData.headers.push({
          ...header,
          type: 'string',
          required: true,
          description: '内容类型'
        })
      }
    },
    // Query参数相关方法
    addQueryParam() {
      this.formData.query_params.push({
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      })
    },
    removeQueryParam(index) {
      this.formData.query_params.splice(index, 1)
    },
    // Form参数相关方法
    addFormParam() {
      this.formData.body_form.push({
        name: '',
        value: '',
        type: 'string',
        required: false,
        description: ''
      })
    },
    removeFormParam(index) {
      this.formData.body_form.splice(index, 1)
    },
    // JSON处理相关方法
    formatJSON() {
      try {
        if (this.formData.body_json) {
          const parsed = JSON.parse(this.formData.body_json)
          this.formData.body_json = JSON.stringify(parsed, null, 2)
        }
      } catch (e) {
        this.$message.warning('JSON格式不正确')
      }
    },
    compactJSON() {
      try {
        if (this.formData.body_json) {
          const parsed = JSON.parse(this.formData.body_json)
          this.formData.body_json = JSON.stringify(parsed)
        }
      } catch (e) {
        this.$message.warning('JSON格式不正确')
      }
    },
    validateJSON(rule, value, callback) {
      if (!value) {
        callback()
        return
      }
      try {
        JSON.parse(value)
        callback()
      } catch (e) {
        callback(new Error('JSON格式不正确'))
      }
    },
    // 断言相关方法
    addAssertion() {
      this.formData.assertions.push({
        operator: 'equal',
        path: '',
        value: null,
        description: ''
      })
    },
    removeAssertion(index) {
      this.formData.assertions.splice(index, 1)
    },
    duplicateAssertion(index) {
      const assertion = { ...this.formData.assertions[index] }
      this.formData.assertions.splice(index + 1, 0, assertion)
    },
    clearAssertions() {
      this.formData.assertions = []
      this.$message.success('断言已清空')
    },
    // 变量相关方法
    addExtractVariable() {
      this.formData.extract_variables.push({
        name: '',
        source: 'RESPONSE',
        path: '',
        description: ''
      })
    },
    removeExtractVariable(index) {
      this.formData.extract_variables.splice(index, 1)
    },
    duplicateExtractVariable(index) {
      const variable = { ...this.formData.extract_variables[index] }
      this.formData.extract_variables.splice(index + 1, 0, variable)
    },
    clearExtractVariables() {
      this.formData.extract_variables = []
      this.$message.success('变量已清空')
    },
    getExtractionPlaceholder(type) {
      const placeholders = {
        json_path: '$.data.id',
        regex: '正则表达式',
        xpath: '//div[@id]',
        body: '$.your_field'
      }
      return placeholders[type] || '请输入提取表达式'
    },
    getExtractionTip(type) {
      const tips = {
        json_path: 'JSON Path示例: $.data.list[0].id',
        regex: '正则表达式示例：\\w+',
        xpath: 'XPath示例: //div[@class="content"]',
        body: 'JSON Path示例: $.your_field'
      }
      return tips[type] || '提取表达式说明'
    },
    getExpectedPlaceholder(operator) {
      const placeholders = {
        equal: '请输入期望值',
        not_equal: '请输入期望值',
        contains: '请输入包含的值',
        not_contains: '请输入不包含的值',
        greater_than: '请输入大于的值',
        less_than: '请输入小于的值',
        exists: '请输入存在值',
        not_exists: '请输入不存在值'
      }
      return placeholders[operator] || '请输入期望值'
    },
    // 状态码相关方法
    handleStatusCodeSelect(code) {
      this.formData.expected_response_code = Number(code)
    },
    // 表单验证
    async validate() {
      try {
        await this.$refs.form.validate()
        
        // 转换回原始格式 (Array -> Object)
        const paramsToObject = (params) => {
          return params.reduce((acc, cur) => {
            if (cur.name) acc[cur.name] = cur.value
            return acc
          }, {})
        }

        // 转换断言数据
        const convertAssertions = (assertions) => {
          return assertions.map(assertion => ({
            operator: assertion.operator || 'equal',
            path: assertion.path || '',
            value: assertion.value,
            description: assertion.description || ''
          }))
        }
        
        // 转换变量提取配置
        const convertExtractVariables = (vars) => {
          return vars.map(ev => ({
            name: ev.name,
            path: ev.path,
            source: ev.source,
            description: ev.description
          }))
        }
        
        const result = {
          ...this.formData,
          headers: paramsToObject(this.formData.headers),
          assertions: convertAssertions(this.formData.assertions),
          extract_variables: convertExtractVariables(this.formData.extract_variables),
          params: paramsToObject(this.formData.query_params)
        }

        // 处理请求体
        if (this.formData.body_type === 'json') {
          result.request_type = 'JSON'
          try {
            if (this.formData.body_json && this.formData.body_json.trim()) {
              result.body = JSON.parse(this.formData.body_json)
            } else {
              result.body = null
            }
          } catch (e) {
            result.body = null
          }
        } else {
          result.request_type = 'FORM'
          const bodyForm = paramsToObject(this.formData.body_form)
          result.body = Object.keys(bodyForm).length > 0 ? bodyForm : null
        }
        
        return result
      } catch (error) {
        console.error('Validation error:', error)
        throw new Error('表单验证失败')
      }
    },
    // 处理取消按钮点击
    handleCancel() {
      this.$emit('cancel')
      this.$emit('update:visible', false)
    },
    // 处理确认按钮点击
    async handleConfirm() {
      try {
        const data = await this.validate()
        this.$emit('confirm', data)
        this.$emit('save', data)
        this.$emit('update:visible', false)
      } catch (error) {
        this.$message.error(error.message)
      }
    },
    handleConfigChange() {
      this.$emit('update:config', this.formData)
    },
    initSortable() {
      this.$nextTick(() => {
        const el = this.$el.querySelector('.el-table__body-wrapper tbody')
        if (el && (!this.sortable || this.sortable.el !== el)) {
          if (this.sortable) this.sortable.destroy()
          this.sortable = new Sortable(el, {
            handle: '.drag-handle',
            animation: 150,
            onEnd: ({ newIndex, oldIndex }) => {
              const moved = this.formData.steps.splice(oldIndex, 1)[0]
              this.formData.steps.splice(newIndex, 0, moved)
              this.formData.steps.forEach((step, idx) => {
                step.order = idx + 1
              })
            }
          })
        }
      })
    },
    async fetchFunctions() {
      try {
        const response = await getFunctionList()
        this.functions = response.data.items
      } catch (error) {
        console.error('Failed to fetch functions:', error)
      }
    },
    validateForm() {
      return new Promise((resolve, reject) => {
        this.$refs.form.validate((valid) => {
          if (valid) {
            const formData = { ...this.formData }
            
            // 处理函数调用数据
            if (formData.type === 'function') {
              formData.function = {
                id: formData.function_id
              }
              delete formData.function_id
            }
            
            resolve(formData)
          } else {
            reject(new Error('表单验证失败'))
          }
        })
      })
    }
  }
}
</script>

<style scoped>
.el-tabs {
  margin-top: 20px;
}

.el-form-item {
  margin-bottom: 22px;
}

.el-table {
  margin-bottom: 10px;
}

.el-select {
  width: 100%;
}

.json-tools {
  margin-top: 8px;
  text-align: right;
}

.json-tools .el-button {
  margin-left: 15px;
}

.el-alert {
  margin-bottom: 15px;
}

.el-input-number {
  width: 180px;
}

.el-dropdown {
  margin-right: 10px;
}

.el-button-group {
  .el-button + .el-button {
    margin-left: -1px;
  }
}

.el-tooltip {
  cursor: help;
}

.form-footer {
  margin-top: 20px;
  text-align: right;
  padding: 20px;
  border-top: 1px solid #dcdfe6;
}

.form-footer .el-button + .el-button {
  margin-left: 10px;
}

.step-config-form {
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.operation-buttons {
  display: flex;
  justify-content: center;
  gap: 5px;
}

.function-params {
  margin-top: 10px;
  
  .param-item {
    margin-bottom: 10px;
  }
}
</style>