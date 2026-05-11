<template>
  <div class="app-container">
    <el-form ref="form" v-loading="loading" :model="form" :rules="rules" label-width="120px">
      <!-- 基本信息部分 -->
      <el-card class="box-card">
        <div slot="header" class="clearfix">
          <span>基本信息</span>
        </div>
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入用例名称" />
        </el-form-item>
        <el-form-item label="用例描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入用例描述"
          />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="form.priority" placeholder="请选择优先级" style="width: 100%">
            <el-option
              v-for="item in priorityOptions"
              :key="item"
              :label="'P' + item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属模块" prop="module_id">
          <el-select v-model="form.module_id" placeholder="请选择所属模块" style="width: 100%" clearable filterable>
            <el-option
              v-for="item in moduleOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签" prop="tags">
          <el-tag
            v-for="tag in form.tags"
            :key="tag"
            closable
            @close="handleTagClose(tag)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-if="tagInputVisible"
            ref="tagKeyInput"
            v-model="tagKey"
            class="tag-input"
            size="small"
            placeholder="标签名"
            @keyup.enter.native="handleTagKeyConfirm"
            @blur="handleTagKeyConfirm"
          />
          <el-button v-if="!tagInputVisible" class="button-new-tag" size="small" @click="showTagInput">
            + 新增标签
          </el-button>
        </el-form-item>
      </el-card>

      <!-- 测试步骤部分 -->
      <el-card class="box-card">
        <div slot="header" class="clearfix">
          <span>测试步骤</span>
        </div>
        <div class="steps-container">
          <el-table
            ref="stepsTable"
            :data="form.steps"
            style="width: 100%"
            border
            stripe
            :row-key="row => row.id || row.order"
            :row-class-name="tableRowClassName"
          >
            <el-table-column
              label="排序"
              width="60"
              align="center"
            >
              <template slot-scope="{}">
                <i class="el-icon-rank drag-handle" style="cursor: move; font-size: 16px;" />
              </template>
            </el-table-column>
            <el-table-column
              label="步骤名称"
              min-width="180"
            >
              <template slot-scope="scope">
                <el-input v-model="scope.row.name" placeholder="请输入步骤名称" size="small" />
              </template>
            </el-table-column>
            <el-table-column
              label="请求方法"
              width="100"
              align="center"
            >
              <template slot-scope="scope">
                <el-tag :type="getMethodType(getStepInterface(scope.row.interface_id) && getStepInterface(scope.row.interface_id).method)" size="small">
                  {{ (getStepInterface(scope.row.interface_id) && getStepInterface(scope.row.interface_id).method) || '' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="请求地址"
              min-width="180"
            >
              <template slot-scope="scope">
                <EllipsisCell :value="(getStepInterface(scope.row.interface_id) && getStepInterface(scope.row.interface_id).url) || ''" :detect-json="false" />
              </template>
            </el-table-column>
            <el-table-column
              label="操作"
              width="220"
              align="center"
              fixed="right"
            >
              <template slot-scope="scope">
                <div class="operation-buttons">
                  <el-button
                    type="primary"
                    size="mini"
                    @click="handleConfigStep(scope.$index)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    type="success"
                    size="mini"
                    @click="handleCopyStep(scope.$index)"
                  >
                    复制
                  </el-button>
                  <el-button
                    type="danger"
                    size="mini"
                    @click="handleDeleteStep(scope.$index)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="add-step-wrapper">
            <el-button
              type="primary"
              class="add-step-btn"
              @click="showAddStepDialog"
            >
              <div class="add-step-content">
                <i class="el-icon-plus add-icon" />
                <span class="add-text">添加测试步骤</span>
                <div class="add-desc">点击添加新的测试步骤</div>
              </div>
            </el-button>
          </div>
        </div>
      </el-card>

      <el-form-item>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </el-form-item>

      <!-- 添加步骤弹窗 -->
      <el-dialog title="添加测试步骤" :visible.sync="addStepDialogVisible" width="70%" :close-on-click-modal="false">
        <div class="dialog-content">
          <div class="search-section">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-input
                  v-model="interfaceSearch"
                  placeholder="搜索接口名称、URL或方法"
                  prefix-icon="el-icon-search"
                  clearable
                  @input="handleSearch"
                />
              </el-col>
              <el-col :span="12">
                <el-select
                  v-model="moduleSearch"
                  placeholder="选择所属模块"
                  clearable
                  style="width: 100%"
                  @change="handleSearch"
                >
                  <el-option
                    v-for="item in moduleOptions"
                    :key="item.id"
                    :label="item.name"
                    :value="item.id"
                  />
                </el-select>
              </el-col>
            </el-row>
          </div>
          <el-table
            :data="filteredInterfaces.slice((currentPage-1)*pageSize, currentPage*pageSize)"
            style="width: 100%"
            height="400"
            highlight-current-row
            @row-click="handleInterfaceSelect"
            @row-dblclick="confirmAddStep"
          >
            <el-table-column prop="name" label="接口名称" min-width="150" />
            <el-table-column prop="method" label="请求方法" width="100">
              <template slot-scope="scope">
                <el-tag :type="getMethodType(scope.row.method)">{{ scope.row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="url" label="请求地址" min-width="200" />
            <el-table-column label="所属模块" width="150">
              <template slot-scope="scope">
                {{ getModuleName(scope.row.module_id) }}
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-container">
            <el-pagination
              :current-page="currentPage"
              :page-sizes="[10, 20, 50, 100]"
              :page-size="pageSize"
              layout="total, sizes, prev, pager, next, jumper"
              :total="totalInterfaces"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>
        <div slot="footer" class="dialog-footer">
          <el-button @click="addStepDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmAddStep">确定</el-button>
        </div>
      </el-dialog>

      <!-- 步骤配置弹窗 -->
      <el-dialog
        title="步骤配置"
        :visible.sync="stepConfigDialogVisible"
        width="80%"
        :before-close="handleStepConfigClose"
        :close-on-click-modal="false"
        :destroy-on-close="true"
        @closed="handleDialogClosed"
      >
        <step-config-form
          ref="stepConfigForm"
          :initial-data="currentStepConfig"
          :visible.sync="stepConfigDialogVisible"
          @update:config="handleConfigUpdate"
          @save="handleStepConfigSave"
          @cancel="handleStepConfigClose"
          @confirm="handleStepConfigSave"
        />
      </el-dialog>
    </el-form>
  </div>
</template>

<script>
import { getTestCase, updateTestCase } from '@/api/testcase'
import { getInterfaceList, getInterface } from '@/api/interface'
import { getModuleList } from '@/api/module'
import StepConfigForm from './components/StepConfigForm.vue'
import Sortable from 'sortablejs'
import EllipsisCell from '@/components/Common/EllipsisCell'

export default {
  name: 'TestcaseEdit',
  components: {
    StepConfigForm,
    EllipsisCell
  },
  data() {
    return {
      loading: true,
      form: {
        id: '',
        name: '',
        description: '',
        priority: 3,
        module_id: '',
        tags: [],
        steps: [],
        status: 'PENDING'
      },
      rules: {
        name: [
          { required: true, message: '请输入用例名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        description: [
          { max: 500, message: '描述不能超过500个字符', trigger: 'blur' }
        ],
        priority: [
          { required: true, message: '请选择优先级', trigger: 'change' }
        ]
      },
      priorityOptions: [1, 2, 3],
      tagInputVisible: false,
      tagKey: '',
      interfaceOptions: [],
      addStepDialogVisible: false,
      interfaceSearch: '',
      moduleSearch: '',
      moduleOptions: [],
      selectedInterface: null,
      stepConfigDialogVisible: false,
      currentStepConfig: {
        headers: [],
        query_params: [],
        paramType: 'query',
        body_type: 'form',
        body_json: '',
        body_form: [],
        expected_response_code: '200',
        assertions: [],
        extract_variables: []
      },
      currentStepIndex: -1,
      currentPage: 1,
      pageSize: 10,
      sortable: null
    }
  },
  computed: {
    totalInterfaces() {
      return this.filteredInterfaces.length
    },
    filteredInterfaces() {
      let filtered = this.interfaceOptions || []

      // 模块筛选
      if (this.moduleSearch) {
        filtered = filtered.filter(item => {
          return String(item.module_id) === String(this.moduleSearch)
        })
      }

      // 关键词搜索
      if (this.interfaceSearch) {
        const search = this.interfaceSearch.toLowerCase()
        filtered = filtered.filter(item =>
          item.name.toLowerCase().includes(search) ||
          item.url.toLowerCase().includes(search) ||
          item.method.toLowerCase().includes(search)
        )
      }

      return filtered
    }
  },
  watch: {
    'form.steps.length'() {
      this.initSortable()
    }
  },
  async created() {
    this.form.id = this.$route.params.id
    if (!this.form.id) {
      this.$message.error('测试用例ID不能为空')
      this.$router.push('/design/testcases')
      return
    }
    try {
      await this.init()
    } catch (error) {
      console.error('页面初始化失败:', error)
      this.$message.error('页面加载失败，请刷新重试')
    }
  },
  mounted() {
    this.initSortable()
  },
  methods: {
    async init() {
      this.loading = true
      try {
        // 获取接口和模块列表
        const [interfacesRes, modulesRes] = await Promise.all([
          getInterfaceList({ limit: 1000, with_module: true }),
          getModuleList({ limit: 1000 })
        ])

        if ((interfacesRes.code === '0' || interfacesRes.code === 0) && interfacesRes.data) {
          this.interfaceOptions = interfacesRes.data.items || interfacesRes.data
        }
        if ((modulesRes.code === '0' || modulesRes.code === 0) && modulesRes.data) {
          this.moduleOptions = modulesRes.data.items || modulesRes.data
        }

        // 获取测试用例数据
        const testcaseRes = await getTestCase(this.form.id)
        if ((testcaseRes.code === '0' || testcaseRes.code === 0) && testcaseRes.data) {
          const { name, description, priority, module_id, tags, steps = [] } = testcaseRes.data

          // 转换标签格式
          const formattedTags = Array.isArray(tags) ? tags
            : (tags && typeof tags === 'object' ? Object.keys(tags) : [])

          // 格式化步骤数据
          const formattedSteps = Array.isArray(steps) ? steps.map((step, index) => ({
            id: step.id || Date.now().toString() + index, // 添加唯一ID
            order: index + 1,
            interface_id: step.interface_id || '',
            name: step.name || '',
            description: step.description || '',
            request_type: step.request_type || 'JSON',
            headers: step.headers || {},
            body: step.body || null,
            params: step.params || null,
            file_config: step.file_config || null,
            expected_response_code: step.expected_response_code || 200,
            assertions: step.assertions || [],
            extract_variables: step.extract_variables || null,
            status: step.status || 'PENDING'
          })) : []

          this.form = {
            id: this.form.id,
            name: name || '',
            description: description || '',
            priority: Number(priority) || 3,
            module_id: module_id || '',
            tags: formattedTags,
            steps: formattedSteps,
            status: testcaseRes.data.status || 'PENDING'
          }
        } else {
          console.error('testcaseRes:', testcaseRes)
          throw new Error(testcaseRes.message || '获取测试用例数据失败')
        }
      } catch (error) {
        console.error('初始化失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },
    initSortable() {
      this.$nextTick(() => {
        const el = this.$refs.stepsTable && this.$refs.stepsTable.$el.querySelector('tbody')
        if (!el) return
        if (this.sortable) {
          this.sortable.destroy()
        }
        this.sortable = new Sortable(el, {
          handle: '.drag-handle',
          animation: 150,
          onEnd: ({ newIndex, oldIndex }) => {
            // 保存当前步骤的完整数据
            const targetRow = { ...this.form.steps[oldIndex] }

            // 更新数组
            this.form.steps.splice(oldIndex, 1)
            this.form.steps.splice(newIndex, 0, targetRow)

            // 更新步骤顺序
            this.form.steps.forEach((step, index) => {
              this.$set(step, 'order', index + 1)
            })

            // 强制刷新表格
            this.$nextTick(() => {
              if (this.$refs.stepsTable) {
                this.$refs.stepsTable.doLayout()
              }
            })
          }
        })
      })
    },
    showTagInput() {
      this.tagInputVisible = true
      this.$nextTick(() => {
        if (this.$refs.tagKeyInput) {
          this.$refs.tagKeyInput.focus()
        }
      })
    },
    handleTagKeyConfirm() {
      const tag = this.tagKey && this.tagKey.trim()
      if (tag && !this.form.tags.includes(tag)) {
        this.form.tags.push(tag)
        this.$message.success('标签添加成功')
      } else if (this.form.tags.includes(tag)) {
        this.$message.warning('标签已存在')
      }
      this.tagInputVisible = false
      this.tagKey = ''
    },
    handleTagClose(tag) {
      this.form.tags = this.form.tags.filter(t => t !== tag)
      this.$message.success('标签删除成功')
    },
    getMethodType(method) {
      const typeMap = {
        GET: 'success',
        POST: 'primary',
        PUT: 'warning',
        DELETE: 'danger',
        PATCH: 'info'
      }
      return typeMap[method] || 'info'
    },
    showAddStepDialog() {
      this.addStepDialogVisible = true
      this.interfaceSearch = ''
      this.selectedInterface = null
    },
    handleSearch() {
      this.currentPage = 1
    },
    handleInterfaceSelect(row) {
      this.selectedInterface = row
    },
    confirmAddStep() {
      if (!this.selectedInterface) {
        this.$message.warning('请选择一个接口')
        return
      }
      this.form.steps.push({
        interface_id: this.selectedInterface.id,
        description: `调用 ${this.selectedInterface.name} 接口`,
        order: this.form.steps.length + 1
      })
      this.addStepDialogVisible = false
    },
    handleAddStep() {
      const newStep = {
        order: this.form.steps.length + 1,
        interface_id: '',
        description: '',
        request_data: {},
        assertions: [],
        extract_variables: {}
      }
      this.form.steps.push(newStep)
    },
    handleDeleteStep(index) {
      this.form.steps.splice(index, 1)
      // 重新计算步骤顺序
      this.form.steps.forEach((step, idx) => {
        step.order = idx + 1
      })
    },
    handleInterfaceChange(index, interfaceId) {
      if (!interfaceId || !this.form.steps[index]) return
      const selectedInterface = this.interfaceOptions.find(item => item.id === interfaceId)
      if (selectedInterface) {
        this.$set(this.form.steps, index, {
          ...this.form.steps[index],
          interface_id: interfaceId,
          name: selectedInterface.name, // 选中接口后自动填充到步骤名称
          description: `调用 ${selectedInterface.name} 接口`
        })
      }
    },
    getStepInterface(interfaceId) {
      if (!interfaceId) return null
      return this.interfaceOptions.find(item => item.id === interfaceId) || null
    },
    getModuleName(moduleId) {
      const module = this.moduleOptions.find(item => item.id === moduleId)
      return module ? module.name : '未命名模块'
    },
    async handleConfigStep(index) {
      if (!this.form.steps[index]) {
        this.$message.error('步骤数据不存在')
        return
      }
      this.currentStepIndex = index
      const currentStep = this.form.steps[index]
      try {
        const response = await getInterface(currentStep.interface_id)
        if (response.code === '0' && response.data) {
          const interfaceDetail = response.data

          // 1. 合并 headers
          let headers = []
          if (currentStep.headers) {
            if (Array.isArray(currentStep.headers)) {
              headers = currentStep.headers
            } else if (currentStep.headers && typeof currentStep.headers === 'object') {
              headers = Object.entries(currentStep.headers).map(([key, value]) => ({ name: key, value }))
            }
          } else if (interfaceDetail.headers && typeof interfaceDetail.headers === 'object') {
            headers = Object.entries(interfaceDetail.headers).map(([key, value]) => ({ name: key, value }))
          }

          // 2. 合并 params
          let params = []
          if (currentStep.params) {
            if (Array.isArray(currentStep.params)) {
              params = currentStep.params
            } else if (currentStep.params && typeof currentStep.params === 'object') {
              params = Object.entries(currentStep.params).map(([key, value]) => ({ name: key, value }))
            }
          } else if (interfaceDetail.params && typeof interfaceDetail.params === 'object') {
            params = Object.entries(interfaceDetail.params).map(([key, value]) => ({ name: key, value }))
          }

          // 3. 合并 body
          const bodyType = (currentStep.request_type || interfaceDetail.request_type || 'FORM').toUpperCase()
          let bodyJson = ''
          let bodyForm = []
          if (bodyType === 'JSON') {
            if (typeof currentStep.body === 'string') {
              bodyJson = currentStep.body
            } else if (currentStep.body && typeof currentStep.body === 'object') {
              bodyJson = JSON.stringify(currentStep.body, null, 2)
            } else if (interfaceDetail.body && typeof interfaceDetail.body === 'object') {
              bodyJson = JSON.stringify(interfaceDetail.body, null, 2)
            }
          } else {
            if (Array.isArray(currentStep.body)) {
              bodyForm = currentStep.body
            } else if (currentStep.body && typeof currentStep.body === 'object') {
              bodyForm = Object.entries(currentStep.body).map(([key, value]) => ({ name: key, value }))
            } else if (interfaceDetail.body && typeof interfaceDetail.body === 'object') {
              bodyForm = Object.entries(interfaceDetail.body).map(([key, value]) => ({ name: key, value }))
            }
          }

          const paramType = (bodyType === 'JSON' || bodyType === 'FORM') ? 'body' : 'query'

          // 4. 处理 assertions 和 extract_variables
          const assertions = Array.isArray(currentStep.assertions) ? currentStep.assertions : []
          let extract_variables = []

          if (currentStep.extract_variables) {
            if (Array.isArray(currentStep.extract_variables)) {
              extract_variables = currentStep.extract_variables.map(ev => ({
                name: ev.name || '',
                source: ev.source ? String(ev.source).toUpperCase() : 'RESPONSE',
                path: ev.path || '',
                description: ev.description || ''
              }))
            } else if (currentStep.extract_variables && typeof currentStep.extract_variables === 'object') {
              extract_variables = Object.entries(currentStep.extract_variables).map(([key, value]) => ({
                name: key,
                source: 'RESPONSE',
                path: value.path || value,
                description: value.description || ''
              }))
            }
          }

          this.currentStepConfig = {
            headers,
            query_params: params,
            paramType,
            body_type: bodyType === 'JSON' ? 'json' : 'form',
            body_json: bodyJson,
            body_form: bodyForm,
            expected_response_code: currentStep.expected_response_code || '200',
            assertions,
            extract_variables
          }
          this.stepConfigDialogVisible = true
        } else {
          this.$message.error('获取接口详情失败')
        }
      } catch (error) {
        console.error('获取接口详情失败:', error)
        this.$message.error('获取接口详情失败')
      }
    },
    handleStepConfigClose() {
      this.stepConfigDialogVisible = false
      this.currentStepConfig = {
        interface_id: '',
        name: '',
        description: '',
        request_type: 'JSON',
        headers: [],
        body: null,
        params: null,
        file_config: null,
        expected_response_code: 200,
        assertions: [],
        extract_variables: null,
        status: 'PENDING'
      }
      this.currentStepIndex = -1
    },
    handleConfigUpdate(config) {
      if (this.currentStepIndex >= 0 && this.currentStepIndex < this.form.steps.length) {
        this.$set(this.form.steps, this.currentStepIndex, {
          ...this.form.steps[this.currentStepIndex],
          ...config
        })
      }
    },
    async handleStepConfigSave() {
      try {
        const formData = await this.$refs.stepConfigForm.validate()
        if (this.currentStepIndex > -1) {
          // 变量提取处理
          let extract_variables = formData.extract_variables || []
          extract_variables = extract_variables.map(ev => ({
            name: ev.name || '',
            source: ev.source ? String(ev.source).toUpperCase() : 'RESPONSE',
            path: ev.path || '',
            description: ev.description || ''
          }))

          // 处理 headers
          let headers = {}
          if (Array.isArray(formData.headers)) {
            headers = formData.headers.reduce((acc, cur) => {
              if (cur.name) acc[cur.name] = cur.value
              return acc
            }, {})
          }

          // 处理 params
          let params = {}
          if (Array.isArray(formData.query_params)) {
            params = formData.query_params.reduce((acc, cur) => {
              if (cur.name) acc[cur.name] = cur.value
              return acc
            }, {})
          }

          // 处理 body
          let body = null
          if (formData.body_type === 'json') {
            try {
              body = JSON.parse(formData.body_json)
            } catch (e) {
              body = formData.body_json
            }
          } else {
            if (Array.isArray(formData.body_form)) {
              body = formData.body_form.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value
                return acc
              }, {})
            }
          }

          // 合并并保存
          this.$set(this.form.steps, this.currentStepIndex, {
            ...this.form.steps[this.currentStepIndex],
            headers,
            params,
            body,
            request_type: formData.body_type === 'json' ? 'JSON' : 'FORM',
            expected_response_code: formData.expected_response_code,
            assertions: Array.isArray(formData.assertions) ? formData.assertions.map(assertion => ({
              path: assertion.path,
              value: assertion.value,
              operator: assertion.operator,
              description: assertion.description
            })) : [],
            extract_variables
          })
          this.$message.success('配置保存成功')
        }
        this.stepConfigDialogVisible = false
      } catch (error) {
        this.$message.error(error.message || '保存配置失败')
      }
    },
    handleDialogClosed() {
      this.currentStepIndex = -1
      this.currentStepConfig = {
        interface_id: '',
        name: '',
        description: '',
        request_type: 'JSON',
        headers: [],
        body: null,
        params: null,
        file_config: null,
        expected_response_code: 200,
        assertions: [],
        extract_variables: null,
        status: 'PENDING'
      }
    },
    handleSizeChange(newSize) {
      this.pageSize = newSize
    },
    handleCurrentChange(newPage) {
      this.currentPage = newPage
    },
    tableRowClassName({ row, rowIndex }) {
      if (rowIndex % 2 === 1) {
        return 'even-row'
      }
      return ''
    },
    handleCopyStep(index) {
      const step = JSON.parse(JSON.stringify(this.form.steps[index]))
      this.form.steps.push({
        ...step,
        order: this.form.steps.length + 1
      })
      this.$message.success('复制成功')
    },
    async handleSave() {
      try {
        await this.$refs.form.validate()

        // 验证测试步骤
        if (!this.form.steps.length) {
          this.$message.error('请添加测试步骤')
          return
        }

        const invalidStep = this.form.steps.find(step => !step.interface_id)
        if (invalidStep) {
          this.$message.warning('请为所有步骤选择接口')
          return
        }

        // 构建更新数据
        const updateData = {
          name: this.form.name,
          description: this.form.description,
          priority: Number(this.form.priority),
          tags: this.form.tags,
          steps: this.form.steps.map((step, idx) => {
            // headers/params 处理
            let headers = step.headers
            if (Array.isArray(headers)) {
              headers = headers.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value
                return acc
              }, {})
            }
            let params = step.params
            if (Array.isArray(params)) {
              params = params.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value
                return acc
              }, {})
            }

            // body 处理
            let body = step.body
            if (step.body_type === 'json' && typeof step.body_json === 'string') {
              try {
                body = JSON.parse(step.body_json)
              } catch {
                body = {}
              }
            } else if (Array.isArray(step.body_form)) {
              body = step.body_form.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value
                return acc
              }, {})
            }

            return {
              interface_id: step.interface_id,
              name: step.name || this.getStepInterface(step.interface_id)?.name || `步骤${idx + 1}`,
              description: step.description,
              request_type: (step.request_type || 'JSON').toUpperCase(),
              headers,
              params,
              body,
              extract_variables: Array.isArray(step.extract_variables)
                ? step.extract_variables.map(ev => ({
                  ...ev,
                  source: (ev.source || 'RESPONSE').toUpperCase()
                }))
                : step.extract_variables,
              expected_response_code: step.expected_response_code,
              assertions: Array.isArray(step.assertions) ? step.assertions.map(assertion => ({
                path: assertion.path,
                value: assertion.value,
                operator: assertion.operator,
                description: assertion.description
              })) : [],
              order: step.order
            }
          }),
          status: this.form.status
        }

        console.log('更新测试用例数据:', updateData)
        const response = await updateTestCase(this.form.id, updateData)
        if (response.code === '0') {
          this.$message.success('保存成功')
          this.$router.push('/design/testcases')
        } else {
          throw new Error(response.message || '保存失败')
        }
      } catch (error) {
        console.error('保存失败:', error)
        this.$message.error(error.message || '保存失败')
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
}

.box-card {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.box-card :deep(.el-card__header) {
  padding: 15px 20px;
  border-bottom: 1px solid #ebeef5;
}

.box-card :deep(.el-card__body) {
  padding: 20px;
}

.clearfix {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.clearfix span {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.steps-container {
  margin-top: 10px;
}

.el-table {
  margin-bottom: 15px;
}

.el-table :deep(th) {
  background-color: #f5f7fa;
  color: #606266;
  font-weight: 500;
  height: 44px;
}

.el-table :deep(td) {
  padding: 12px 0;
}

.el-table :deep(.el-button--text) {
  padding: 0 8px;
  font-size: 13px;
}

.el-table :deep(.el-button--text + .el-button--text) {
  margin-left: 8px;
}

.el-table :deep(.el-button--text:hover) {
  color: #66b1ff;
}

.el-table :deep(.el-button--text[style*="color: #F56C6C"]:hover) {
  color: #ff7875 !important;
}

.el-tag {
  margin-right: 8px;
  margin-bottom: 8px;
  height: 24px;
  line-height: 22px;
  border-radius: 4px;
  font-size: 12px;
}

.el-tag + .el-tag {
  margin-left: 0;
}

.tag-input {
  width: 120px;
  margin-right: 10px;
  margin-bottom: 8px;
  vertical-align: bottom;
  display: inline-block;
}

.tag-input:first-of-type {
  margin-left: 0;
}

.button-new-tag {
  height: 32px;
  line-height: 30px;
  padding: 0 10px;
  margin-bottom: 8px;
  margin-left: 0;
}

.add-step-wrapper {
  margin-top: 15px;
  padding: 0;
  border-radius: 4px;
  background: transparent;
}

.add-step-btn {
  width: 100%;
  height: auto;
  padding: 15px;
  border: 1px dashed #d9d9d9;
  background: #fafafa;
  transition: all 0.3s ease;
}

.add-step-btn:hover {
  border-color: #409EFF;
  background: #f5f7fa;
}

.add-step-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #606266;
}

.add-icon {
  font-size: 20px;
  margin-bottom: 6px;
  color: #909399;
}

.add-text {
  font-size: 14px;
  margin-bottom: 2px;
}

.add-desc {
  font-size: 12px;
  color: #909399;
}

.dialog-content {
  padding: 20px;
}

.search-section {
  margin-bottom: 20px;
}

.search-section .el-row {
  margin-bottom: 10px;
}

.interface-select-wrapper {
  display: flex;
  align-items: center;
}

.interface-select-wrapper :deep(.el-select) {
  width: 100%;
}

.url-text {
  color: #606266;
  font-size: 13px;
}

.dialog-footer {
  text-align: right;
  padding-top: 15px;
}

/* 请求方法标签样式 */
.el-tag.method-get {
  color: #67c23a;
  background-color: #f0f9eb;
  border-color: #c2e7b0;
}

.el-tag.method-post {
  color: #409eff;
  background-color: #ecf5ff;
  border-color: #b3d8ff;
}

.el-tag.method-put {
  color: #e6a23c;
  background-color: #fdf6ec;
  border-color: #f5dab1;
}

.el-tag.method-delete {
  color: #f56c6c;
  background-color: #fef0f0;
  border-color: #fbc4c4;
}

.el-tag.method-patch {
  color: #909399;
  background-color: #f4f4f5;
  border-color: #d3d4d6;
}

/* 优先级标签样式 */
.el-tag.priority-p1 {
  color: #f56c6c;
  background-color: #fef0f0;
  border-color: #fbc4c4;
}

.el-tag.priority-p2 {
  color: #e6a23c;
  background-color: #fdf6ec;
  border-color: #f5dab1;
}

.el-tag.priority-p3 {
  color: #409eff;
  background-color: #ecf5ff;
  border-color: #b3d8ff;
}

.el-tag.priority-p4 {
  color: #67c23a;
  background-color: #f0f9eb;
  border-color: #c2e7b0;
}

.el-tag.priority-p5 {
  color: #909399;
  background-color: #f4f4f5;
  border-color: #d3d4d6;
}

.operation-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 5px;

  .el-button {
    margin: 0;
    padding: 5px 8px;
  }
}
</style>
