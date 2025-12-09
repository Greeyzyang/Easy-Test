<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px">
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
          v-model="tagKey"
          ref="tagKeyInput"
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

      <!-- 测试步骤部分 -->
      <el-form-item label="测试步骤">
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
              <template slot-scope="scope">
                <i class="el-icon-rank drag-handle" style="cursor: move; font-size: 16px;"></i>
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
              show-overflow-tooltip
            >
              <template slot-scope="scope">
                <span class="url-text">{{ (getStepInterface(scope.row.interface_id) && getStepInterface(scope.row.interface_id).url) || '' }}</span>
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
                <i class="el-icon-plus add-icon"></i>
                <span class="add-text">添加测试步骤</span>
                <div class="add-desc">点击添加新的测试步骤</div>
              </div>
            </el-button>
          </div>
        </div>
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
            :data="filteredInterfaces"
            style="width: 100%"
            height="400"
            @row-click="handleInterfaceSelect"
            highlight-current-row
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
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
              :current-page="currentPage"
              :page-sizes="[10, 20, 50, 100]"
              :page-size="pageSize"
              layout="total, sizes, prev, pager, next, jumper"
              :total="totalInterfaces"
            >
            </el-pagination>
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

      <el-form-item>
        <el-button type="primary" @click="onSubmit">创建</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { createTestCase } from '@/api/testcase'
import { getInterfaceList, getInterface } from '@/api/interface'
import { getModuleList } from '@/api/module'
import Sortable from 'sortablejs'
import StepConfigForm from './components/StepConfigForm.vue'

export default {
  name: 'TestcaseCreate',
  components: {
    StepConfigForm
  },
  data() {
    return {
      form: {
        name: '',
        description: '',
        priority: 3,
        tags: [],
        steps: [],
        created_time: new Date().toISOString(),
        updated_time: new Date().toISOString(),
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
      interfaceOptions: [],
      addStepDialogVisible: false,
      interfaceSearch: '',
      moduleSearch: '',
      moduleOptions: [],
      selectedInterface: null,
      currentPage: 1,
      pageSize: 10,
      totalInterfaces: 0,
      sortable: null,
      stepConfigDialogVisible: false,
      currentStepIndex: -1,
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
      tagInputVisible: false,
      tagKey: '',
    }
  },
  computed: {
    filteredInterfaces() {
      let filtered = this.interfaceOptions
      
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
  created() {
    // 恢复之前保存的状态
    const savedState = sessionStorage.getItem('testcase_create_state')
    if (savedState) {
      const state = JSON.parse(savedState)
      this.form = state.form
      // 清除保存的状态
      sessionStorage.removeItem('testcase_create_state')
    }
    
    this.getInterfaces()
    this.getModules()
  },
  mounted() {
    this.initSortable()
  },
  watch: {
    'form.steps.length'() {
      this.initSortable()
    }
  },
  methods: {
    async getModules() {
      try {
        const response = await getModuleList({ limit: 1000 })
        if (response.code === '0' && response.data) {
          this.moduleOptions = response.data
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
        this.$message.error('获取模块列表失败')
      }
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
    getModuleName(moduleId) {
      if (!moduleId) return '无'
      const module = this.moduleOptions.find(m => String(m.id) === String(moduleId))
      return module ? module.name : '无'
    },
    async getInterfaces() {
      try {
        const response = await getInterfaceList({ 
          page: this.currentPage,
          limit: this.pageSize,
          with_module: true
        })
        if (response.code === '0' && response.data) {
          this.interfaceOptions = response.data.map(item => ({
            ...item,
            module_id: item.module_id || ''
          }))
          this.totalInterfaces = response.total || 0
        }
      } catch (error) {
        console.error('获取接口列表失败:', error)
        this.$message.error('获取接口列表失败')
      }
    },
    handleSizeChange(val) {
      this.pageSize = val
      this.getInterfaces()
    },
    handleCurrentChange(val) {
      this.currentPage = val
      this.getInterfaces()
    },
    showAddStepDialog() {
      this.addStepDialogVisible = true
      this.interfaceSearch = ''
      this.moduleSearch = ''
      this.selectedInterface = null
      this.currentPage = 1
      this.getInterfaces()
    },
    handleSearch() {
      // 搜索逻辑已经在 computed 中处理
    },
    handleInterfaceSelect(row) {
      this.selectedInterface = row
    },
    async confirmAddStep() {
      if (!this.selectedInterface) {
        this.$message.warning('请选择一个接口')
        return
      }
      
      try {
        // 获取接口默认配置
        const interfaceResponse = await getInterface(this.selectedInterface.id)
        if (interfaceResponse.code !== '0') {
          throw new Error(interfaceResponse.message || '获取接口配置失败')
        }

        const interfaceConfig = interfaceResponse.data
        
        // 创建新步骤时添加唯一ID
        const newStep = {
          id: Date.now().toString(), // 添加唯一ID
          interface_id: this.selectedInterface.id,
          name: this.selectedInterface.name,
          description: `调用 ${this.selectedInterface.name} 接口`,
          request_type: interfaceConfig.request_type || 'JSON',
          headers: interfaceConfig.headers || {},
          body: interfaceConfig.body || null,
          params: interfaceConfig.params || null,
          file_config: interfaceConfig.file_config || null,
          expected_response_code: interfaceConfig.expected_response_code || 200,
          assertions: [],
          extract_variables: interfaceConfig.extract_variables || null,
          status: 'PENDING',
          order: this.form.steps.length + 1
        }
        
        this.form.steps.push(newStep)
        this.addStepDialogVisible = false
        this.$message.success('添加步骤成功')
      } catch (error) {
        console.error('添加步骤失败:', error)
        this.$message.error(error.message || '添加步骤失败')
      }
    },
    removeStep(index) {
      this.form.steps.splice(index, 1)
      // 重新排序
      this.form.steps.forEach((step, i) => {
        step.order = i + 1
      })
    },
    handleInterfaceChange(index, interfaceId) {
      const selectedInterface = this.interfaceOptions.find(item => item.id === interfaceId)
      if (selectedInterface) {
        this.form.steps[index].name = selectedInterface.name // 选中接口后自动填充到步骤名称
        this.form.steps[index].description = `调用 ${selectedInterface.name} 接口`
      }
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
    async onSubmit() {
      try {
        // 验证表单
        await this.$refs.form.validate()
        
        // 验证测试步骤
        if (!this.form.steps.length) {
          this.$message.error('请添加测试步骤')
          return
        }

        // 构建创建测试用例的数据
        const now = new Date().toISOString()
        
        const createData = {
          name: this.form.name,
          description: this.form.description,
          priority: this.form.priority,
          tags: this.form.tags,
          steps: this.form.steps.map(step => {
            // headers/params 处理
            let headers = step.headers;
            if (Array.isArray(headers)) {
              headers = headers.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value;
                return acc;
              }, {});
            }
            let params = step.params;
            if (Array.isArray(params)) {
              params = params.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value;
                return acc;
              }, {});
            }

            // extract_variables 处理
            let extract_variables = step.extract_variables;
            if (Array.isArray(extract_variables)) {
              extract_variables = extract_variables.map(ev => ({
                name: ev.name || '',  // 确保有 name 字段
                source: ev.source ? String(ev.source).toUpperCase() : 'RESPONSE',
                path: ev.path || '',
                description: ev.description || ''
              }));
            }

            // body 处理
            let body = step.body;
            // 优先用 body_form（如果有），否则用 body
            if (Array.isArray(step.body_form) && step.body_form.length > 0) {
              body = step.body_form.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value;
                return acc;
              }, {});
            } else if (typeof body === 'string') {
              try { body = JSON.parse(body); } catch { body = {}; }
            } else if (Array.isArray(body)) {
              body = body.reduce((acc, cur) => {
                if (cur.name) acc[cur.name] = cur.value;
                return acc;
              }, {});
            }

            return {
              interface_id: step.interface_id,
              name: step.name,
              description: step.description,
              request_type: (step.request_type || '').toUpperCase(),
              headers,
              params,
              body,
              extract_variables,
              expected_response_code: step.expected_response_code,
              assertions: Array.isArray(step.assertions) ? step.assertions.map(assertion => ({
                path: assertion.path,
                value: assertion.value,
                operator: assertion.operator,
                description: assertion.description
              })) : [],
              order: step.order
            };
          }),
          created_time: now,
          updated_time: now,
          status: this.form.status
        }
        console.log('传给后端接口配置:', createData)
        // 调用创建接口
        const response = await createTestCase(createData)
        if (response.code === '0') {
          this.$message.success('创建成功')
          this.$router.push('/testcases')
        } else {
          this.$message.error(response.message || '创建失败')
        }
      } catch (error) {
        console.error('创建测试用例失败:', error)
        this.$message.error(error.message || '创建失败')
      }
    },
    getStepInterface(interfaceId) {
      return this.interfaceOptions.find(item => item.id === interfaceId)
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
    tableRowClassName({ row, rowIndex }) {
      return 'draggable-row'
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
            } else if (typeof currentStep.headers === 'object') {
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
            } else if (typeof currentStep.params === 'object') {
              params = Object.entries(currentStep.params).map(([key, value]) => ({ name: key, value }))
            }
          } else if (interfaceDetail.params && typeof interfaceDetail.params === 'object') {
            params = Object.entries(interfaceDetail.params).map(([key, value]) => ({ name: key, value }))
          }

          // 3. 合并 body
          let bodyType = (currentStep.request_type || interfaceDetail.request_type || 'FORM').toUpperCase()
          let bodyJson = ''
          let bodyForm = []
          if (bodyType === 'JSON') {
            if (typeof currentStep.body === 'string') {
              bodyJson = currentStep.body
            } else if (typeof currentStep.body === 'object' && currentStep.body !== null) {
              bodyJson = JSON.stringify(currentStep.body, null, 2)
            } else if (typeof interfaceDetail.body === 'object' && interfaceDetail.body !== null) {
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

          let paramType = (bodyType === 'JSON' || bodyType === 'FORM') ? 'body' : 'query'

          // 4. 处理 assertions 和 extract_variables
          let assertions = Array.isArray(currentStep.assertions) ? currentStep.assertions : []

          let extract_variables = []
          
          if (currentStep.extract_variables) {
            if (Array.isArray(currentStep.extract_variables)) {
              extract_variables = currentStep.extract_variables.map(ev => ({
                name: ev.name || '',
                source: ev.source ? String(ev.source).toUpperCase() : 'RESPONSE',
                path: ev.path || '',
                description: ev.description || ''
              }))
            } else if (typeof currentStep.extract_variables === 'object') {
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
      this.$confirm('确认关闭？未保存的配置将会丢失', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.stepConfigDialogVisible = false
        this.currentStepIndex = -1
      }).catch(() => {})
    },
    handleDialogClosed() {
      this.currentStepIndex = -1
      this.currentStepConfig = {
        headers: [],
        query_params: [],
        paramType: 'query',
        body_type: 'form',
        body_json: '',
        body_form: [],
        expected_response_code: '200',
        assertions: [],
        extract_variables: []
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
            extract_variables: formData.extract_variables || []
          })
          this.$message.success('配置保存成功')
        }
        this.stepConfigDialogVisible = false
      } catch (error) {
        this.$message.error(error.message || '保存配置失败')
      }
    },
    handleConfigUpdate(config) {
      // 更新当前步骤配置
      console.log('接收到配置更新:', config)
      this.currentStepConfig = config
    },
    handleCopyStep(index) {
      const step = JSON.parse(JSON.stringify(this.form.steps[index]))
      this.form.steps.push({
        ...step,
        order: this.form.steps.length + 1
      })
      this.$message.success('复制成功')
    },
    handleDeleteStep(index) {
      this.removeStep(index)
      this.$message.success('步骤删除成功')
    }
  }
}
</script>

<style scoped>
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