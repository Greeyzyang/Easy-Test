<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="130px" style="max-width: 1000px;">

      <!-- Basic Info Card -->
      <el-card class="box-card" style="margin-bottom: 20px;">
        <div slot="header" class="clearfix">
          <span>基本信息</span>
        </div>
        <el-form-item label="压测名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入压测名称，如：登录接口压测" />
        </el-form-item>
        <el-form-item label="所属项目" prop="project_id">
          <el-select
            v-model="form.project_id"
            placeholder="请选择项目"
            filterable
            style="width: 100%;"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选，描述压测目的或场景" />
        </el-form-item>
      </el-card>

      <!-- Load Config Card -->
      <el-card class="box-card" style="margin-bottom: 20px;">
        <div slot="header" class="clearfix">
          <span>压测参数</span>
        </div>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="并发用户数" prop="concurrent_users">
              <el-input-number v-model="form.concurrent_users" :min="1" :max="1000" style="width: 100%;" />
              <div class="tip">同时发起请求的用户数量</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="压测模式" prop="run_mode">
              <el-select v-model="form.run_mode" style="width: 100%;">
                <el-option label="固定时长" value="duration" />
                <el-option label="固定总请求数" value="fixed_requests" />
              </el-select>
              <div class="tip">固定时长=跑满N秒; 固定总请求数=发够N个请求后停止</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item v-if="form.run_mode === 'duration'" label="持续时间(秒)" prop="duration_seconds">
              <el-input-number v-model="form.duration_seconds" :min="5" :max="3600" style="width: 100%;" />
              <div class="tip">压测持续运行的时长</div>
            </el-form-item>
            <el-form-item v-else label="总请求数" prop="total_requests_limit">
              <el-input-number v-model="form.total_requests_limit" :min="1" :max="10000000" style="width: 100%;" />
              <div class="tip">达到此请求数后自动停止</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="测试环境" prop="base_url">
          <el-select v-model="form.base_url" placeholder="请选择测试环境" clearable filterable style="width: 100%;">
            <el-option
              v-for="item in envOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            >
              <span style="float: left">{{ item.label }}</span>
              <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">{{ item.value }}</span>
            </el-option>
          </el-select>
          <div class="tip">从全局变量 env 中选择目标服务器地址</div>
        </el-form-item>
        <!-- User Pool Config -->
        <div style="margin-top: 8px; padding: 12px; border: 1px solid #EBEEF5; border-radius: 4px;">
          <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <el-switch
              v-model="form.user_pool.enabled"
              active-text="启用用户池"
              inactive-text="用户池"
              style="margin-right: 8px;"
            />
            <span style="color: #909399; font-size: 12px;">将用户池变量展开后注入请求模板中</span>
          </div>
          <div v-if="form.user_pool.enabled">
            <el-row :gutter="20">
              <el-col :span="10">
                <el-form-item label="用户池变量" label-width="100px">
                  <el-input
                    v-model="form.user_pool.variable_name"
                    :placeholder="'例如：${USER_POOL}'"
                    style="width: 100%;"
                  />
                  <div class="tip">使用 ${} 引用全局变量中的 JSON 数组变量</div>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="抽取模式" label-width="100px">
                  <el-select v-model="form.user_pool.mode" style="width: 100%;">
                    <el-option label="随机抽取" value="random" />
                    <el-option label="轮询抽取" value="round_robin" />
                  </el-select>
                  <div class="tip">随机=每次随机拿一个；轮询=按顺序循环使用</div>
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Login Auth Config -->
            <el-divider style="margin: 12px 0;" />
            <div style="margin-bottom: 8px;">
              <span style="font-size: 13px; color: #606266; font-weight: 500;">登录认证</span>
              <span style="color: #909399; font-size: 12px; margin-left: 8px;">启用后每个用户先调用登录接口获取 Token，再执行压测步骤</span>
            </div>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="登录接口 URL" label-width="110px">
                  <el-input
                    v-model="form.user_pool.auth_config.login_url"
                    placeholder="例如: /api/login 或 https://xxx.com/login"
                    style="width: 100%;"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Token 字段名" label-width="110px">
                  <el-input
                    v-model="form.user_pool.auth_config.token_key"
                    placeholder="例如: access_token"
                    style="width: 100%;"
                  />
                  <div class="tip">从登录响应体中提取 Token 的字段名</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="请求体模板 (JSON)" label-width="110px">
              <el-input
                v-model="authBodyText"
                type="textarea"
                :rows="3"
                placeholder='例如: {"username": "${username}", "password": "${password}"}'
                style="font-family: monospace;"
                @blur="parseAuthBody"
              />
              <div class="tip">使用 <code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;">${username}</code> / <code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;">${password}</code> 占位，后台会用用户池中的字段替换</div>
            </el-form-item>
          </div>
        </div>
      </el-card>

      <!-- Scenario Card -->
      <el-card class="box-card" style="margin-bottom: 20px;">
        <div slot="header" class="clearfix">
          <span>压测场景</span>
        </div>
        <el-form-item label="场景名称">
          <el-input v-model="form.scenario.name" placeholder="例如：登录+查询流程" style="width: 400px;" />
        </el-form-item>
        <el-form-item label="循环间隔(ms)">
          <el-input-number v-model="form.scenario.scenario_delay_ms" :min="0" :max="600000" style="width: 150px;" />
          <span style="color: #909399; margin-left: 8px;">一轮请求完成后等待再开始下一轮，0表示无间隔</span>
        </el-form-item>

        <!-- Steps -->
        <div style="margin-bottom: 12px;">
          <span style="font-weight: 500; color: #606266;">请求步骤（步骤间支持变量提取与替换）</span>
          <el-button type="text" icon="el-icon-document" style="margin-left: 8px;" @click="showInterfacePicker">
            从接口管理选择
          </el-button>
        </div>

        <el-table
          v-if="form.scenario.steps && form.scenario.steps.length > 0"
          :data="form.scenario.steps"
          border
          size="small"
          style="margin-bottom: 16px;"
        >
          <el-table-column label="步骤名称" min-width="140">
            <template slot-scope="{ row }">
              <el-input v-model="row.name" size="small" placeholder="步骤名" />
            </template>
          </el-table-column>
          <el-table-column label="请求方式" width="100" align="center">
            <template slot-scope="{ row }">
              <el-select v-model="row.override_method" size="small" style="width: 80px;">
                <el-option label="GET" value="GET" />
                <el-option label="POST" value="POST" />
                <el-option label="PUT" value="PUT" />
                <el-option label="DELETE" value="DELETE" />
                <el-option label="PATCH" value="PATCH" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="URL 路径" min-width="200">
            <template slot-scope="{ row }">
              <el-input v-model="row.override_url" size="small" placeholder="/api/path 或 ${variable}" />
            </template>
          </el-table-column>
          <el-table-column label="Think时间(ms)" width="130" align="center">
            <template slot-scope="{ row }">
              <el-input-number v-model="row.think_time_ms" size="small" :min="0" :max="60000" style="width: 100px;" />
            </template>
          </el-table-column>
          <el-table-column label="请求体" min-width="140" align="center">
            <template slot-scope="{ row }">
              <el-button type="text" size="mini" @click="editBody(form.scenario.steps.indexOf(row))">
                {{ row.override_body && Object.keys(row.override_body).length > 0 ? '已配置' : '配置JSON' }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="变量提取" min-width="100" align="center">
            <template slot-scope="{ row }">
              <el-button type="text" size="mini" @click="editExtractVars(form.scenario.steps.indexOf(row))">
                <span v-if="row.extract_variables && row.extract_variables.length > 0" style="color: #67C23A;">
                  {{ row.extract_variables.length }}个
                </span>
                <span v-else>提取变量</span>
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template slot-scope="scope">
              <el-button type="text" size="mini" style="color: #F56C6C;" @click="removeStep(scope.$index)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else style="text-align: center; color: #909399; padding: 16px; border: 1px dashed #DCDFE6; border-radius: 4px; margin-bottom: 16px;">
          暂无步骤，请从接口管理选择添加
        </div>
      </el-card>

      <!-- Form Actions -->
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ isEdit ? '保存修改' : '创建压测' }}
        </el-button>
        <el-button @click="cancelForm">取消</el-button>
      </el-form-item>
    </el-form>

    <!-- Body Editor Dialog -->
    <el-dialog :visible.sync="bodyDialogVisible" title="编辑请求体 (JSON)" width="600px">
      <div style="margin-bottom: 8px; color: #909399; font-size: 12px;">
        支持使用 <code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;">${variable_name}</code> 引用变量
      </div>
      <el-input
        v-model="bodyEditorContent"
        type="textarea"
        :rows="12"
        placeholder='{"key": "value", "token": "${access_token}"}'
        style="font-family: monospace;"
      />
      <div slot="footer">
        <el-button @click="bodyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveBody">确定</el-button>
      </div>
    </el-dialog>

    <!-- Extract Variables Dialog -->
    <el-dialog :visible.sync="extractDialogVisible" title="变量提取配置" width="700px">
      <div style="margin-bottom: 12px; color: #909399; font-size: 12px;">
        从当前步骤的响应中提取变量，供后续步骤使用。例如：从登录响应中提取 <code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;">access_token</code> 供后续接口引用。
      </div>

      <el-table
        :data="editingExtractVars"
        border
        size="small"
        style="margin-bottom: 12px;"
      >
        <el-table-column label="变量名称" min-width="150">
          <template slot-scope="{ row }">
            <el-input v-model="row.name" size="small" placeholder="变量名，如 access_token" />
          </template>
        </el-table-column>
        <el-table-column label="数据来源" width="120">
          <template slot-scope="{ row }">
            <el-select v-model="row.source" size="small" style="width: 100%;">
              <el-option label="响应体" value="response" />
              <el-option label="响应头" value="headers" />
              <el-option label="Cookie" value="cookies" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="提取表达式" min-width="250">
          <template slot-scope="{ row }">
            <el-input
              v-model="row.path"
              size="small"
              :placeholder="getExtractionPlaceholder(row.source)"
            />
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="150">
          <template slot-scope="{ row }">
            <el-input v-model="row.description" size="small" placeholder="变量描述" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="60" align="center">
          <template slot-scope="{ row, $index }">
            <el-button type="text" size="mini" style="color: #F56C6C;" @click="removeExtractVar($index)">
              <i class="el-icon-delete" />
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-button type="text" icon="el-icon-plus" @click="addExtractVar">
        + 添加提取变量
      </el-button>

      <div slot="footer">
        <el-button @click="extractDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveExtractVars">确定</el-button>
      </div>
    </el-dialog>

    <!-- Interface Picker Dialog -->
    <el-dialog :visible.sync="interfaceDialogVisible" title="从接口管理选择" width="75%" :close-on-click-modal="false">
      <div style="margin-bottom: 12px;">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-input
              v-model="interfaceSearch"
              placeholder="搜索接口名称、URL或方法"
              prefix-icon="el-icon-search"
              clearable
              @input="handleInterfaceSearch"
            />
          </el-col>
          <el-col :span="6">
            <el-select v-model="moduleSearch" placeholder="所属模块" clearable style="width: 100%;" @change="handleInterfaceSearch">
              <el-option v-for="m in moduleOptions" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-col>
        </el-row>
      </div>
      <el-table
        ref="interfaceTable"
        :data="filteredInterfaceList"
        style="width: 100%"
        height="400"
        highlight-current-row
        @row-click="handleInterfaceRowClick"
        @row-dblclick="confirmAddInterfaceStep"
      >
        <el-table-column prop="name" label="接口名称" min-width="150" />
        <el-table-column prop="method" label="方法" width="90" align="center">
          <template slot-scope="scope">
            <el-tag :type="getMethodType(scope.row.method)" size="small">{{ scope.row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="请求地址" min-width="220" show-overflow-tooltip />
        <el-table-column label="所属模块" width="150">
          <template slot-scope="scope">
            {{ getModuleName(scope.row.module_id) }}
          </template>
        </el-table-column>
      </el-table>
      <div style="text-align: right; margin-top: 12px;">
        <el-pagination
          :current-page="interfacePage"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="interfacePageSize"
          layout="total, sizes, prev, pager, next"
          :total="interfaceTotal"
          @size-change="handleInterfaceSizeChange"
          @current-change="handleInterfacePageChange"
        />
      </div>
      <div slot="footer">
        <el-button @click="interfaceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddInterfaceStep">添加选中接口</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getPerformanceTest, createPerformanceTest, updatePerformanceTest } from '@/api/performance-test'
import { getProjectList as getProjects } from '@/api/project'
import { getInterfaceList, getInterface } from '@/api/interface'
import { getModuleList } from '@/api/module'
import { getList as getVariables } from '@/api/variable'

export default {
  name: 'PerformanceTestForm',
  data() {
    return {
      form: {
        name: '',
        description: '',
        project_id: '',
        concurrent_users: 10,
        run_mode: 'duration',
        duration_seconds: 60,
        total_requests_limit: null,
        base_url: '',
        user_pool: {
          enabled: false,
          variable_name: '',
          mode: 'random',
          auth_config: {
            login_url: '',
            login_body_template: {},
            token_key: 'access_token'
          }
        },
        authBodyText: '',
        scenario: {
          name: '',
          enabled: true,
          scenario_delay_ms: 0,
          steps: []
        }
      },
      rules: {
        name: [{ required: true, message: '请输入压测名称', trigger: 'blur' }],
        project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
        concurrent_users: [{ required: true, message: '请设置并发数', trigger: 'blur' }],
        duration_seconds: [{ required: true, message: '请设置持续时间', trigger: 'blur' }]
      },
      projectOptions: [],
      envOptions: [],
      isEdit: false,
      editId: null,
      submitting: false,
      bodyDialogVisible: false,
      bodyEditorContent: '',
      editingStepIdx: -1,
      extractDialogVisible: false,
      editingExtractVars: [],
      interfaceDialogVisible: false,
      interfaceSearch: '',
      moduleSearch: '',
      moduleOptions: [],
      interfaceList: [],
      interfaceTotal: 0,
      interfacePage: 1,
      interfacePageSize: 20,
      selectedInterfaceRow: null
    }
  },
  computed: {
    filteredInterfaceList() {
      return this.interfaceList
    }
  },
  created() {
    this.getProjectOptions()
    this.getEnvOptions()
    this._init()
  },
  methods: {
    getMethodType(method) {
      const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
      return map[method] || 'info'
    },
    async _init() {
      const id = this.$route.params.id
      if (id) {
        this.isEdit = true
        this.editId = id
        await this.loadData(id)
      }
    },
    getExtractionPlaceholder(source) {
      const map = {
        response: '$.data.access_token',
        headers: 'Content-Type',
        cookies: 'session_id'
      }
      return map[source] || 'key 或 $.jsonpath'
    },
    parseAuthBody() {
      if (!this.authBodyText.trim()) {
        this.form.user_pool.auth_config.login_body_template = {}
        return
      }
      try {
        this.form.user_pool.auth_config.login_body_template = JSON.parse(this.authBodyText)
      } catch (e) {
        this.$message.error('请求体模板 JSON 格式错误: ' + e.message)
      }
    },
    async getProjectOptions() {
      try {
        const res = await getProjects({ limit: 1000 })
        if (res && res.code === '0' && res.data) {
          this.projectOptions = res.data.items || []
        }
      } catch (e) {
        console.error('获取项目失败', e)
      }
    },
    async getEnvOptions() {
      try {
        const response = await getVariables({ key: 'env' })
        if (response && response.code === '0' && response.data && response.data.items) {
          const envVar = response.data.items.find(item => item.key === 'env')
          if (envVar && envVar.value) {
            try {
              const envMap = JSON.parse(envVar.value)
              this.envOptions = Object.keys(envMap).map(key => ({
                label: key,
                value: envMap[key]
              }))
            } catch (e) {
              console.error('解析 env 变量失败', e)
            }
          }
        }
      } catch (e) {
        console.error('获取环境变量失败', e)
      }
    },
    async loadData(id) {
      try {
        const res = await getPerformanceTest(id)
        if (res && res.code === '0' && res.data) {
          const d = res.data
          this.form.name = d.name
          this.form.description = d.description
          this.form.project_id = d.project_id
          this.form.concurrent_users = d.concurrent_users
          this.form.run_mode = d.run_mode || 'duration'
          this.form.duration_seconds = d.duration_seconds
          this.form.total_requests_limit = d.total_requests_limit || null
          this.form.base_url = d.target_base_url || ''
          if (d.user_pool && d.user_pool.variable_name) {
            this.form.user_pool.enabled = true
            this.form.user_pool.variable_name = '${' + d.user_pool.variable_name + '}'
            this.form.user_pool.mode = d.user_pool.mode || 'random'
            const ac = d.user_pool.auth_config || {}
            this.form.user_pool.auth_config = {
              login_url: ac.login_url || '',
              token_key: ac.token_key || 'access_token',
              login_body_template: ac.login_body_template || {}
            }
            this.authBodyText = Object.keys(this.form.user_pool.auth_config.login_body_template).length > 0
              ? JSON.stringify(this.form.user_pool.auth_config.login_body_template, null, 2)
              : ''
          } else {
            this.form.user_pool.enabled = false
            this.form.user_pool.variable_name = ''
            this.form.user_pool.mode = 'random'
            this.form.user_pool.auth_config = { login_url: '', token_key: 'access_token', login_body_template: {} }
            this.authBodyText = ''
          }
          const sc = d.scenario || { name: '', enabled: true, scenario_delay_ms: 0, steps: [] }
          if (sc.steps) {
            sc.steps.forEach(step => {
              if (!step.extract_variables) {
                step.extract_variables = []
              }
            })
          }
          this.form.scenario = sc
        }
      } catch (e) {
        this.$message.error('加载压测数据失败')
      }
    },
    removeStep(stepIdx) {
      this.form.scenario.steps.splice(stepIdx, 1)
    },
    editBody(stepIdx) {
      this.editingStepIdx = stepIdx
      const body = this.form.scenario.steps[stepIdx].override_body
      this.bodyEditorContent = body && Object.keys(body).length > 0 ? JSON.stringify(body, null, 2) : ''
      this.bodyDialogVisible = true
    },
    saveBody() {
      try {
        if (this.bodyEditorContent.trim()) {
          this.form.scenario.steps[this.editingStepIdx].override_body = JSON.parse(this.bodyEditorContent)
        } else {
          this.form.scenario.steps[this.editingStepIdx].override_body = {}
        }
      } catch (e) {
        this.$message.error('JSON 格式错误: ' + e.message)
        return
      }
      this.bodyDialogVisible = false
    },
    editExtractVars(stepIdx) {
      this.editingStepIdx = stepIdx
      const step = this.form.scenario.steps[stepIdx]
      this.editingExtractVars = JSON.parse(JSON.stringify(step.extract_variables || []))
      this.extractDialogVisible = true
    },
    addExtractVar() {
      this.editingExtractVars.push({
        name: '',
        source: 'response',
        path: '',
        description: ''
      })
    },
    removeExtractVar(idx) {
      this.editingExtractVars.splice(idx, 1)
    },
    saveExtractVars() {
      const valid = this.editingExtractVars.every(v => v.name && v.path)
      if (!valid) {
        this.$message.warning('请填写完整的变量名称和提取表达式')
        return
      }
      this.form.scenario.steps[this.editingStepIdx].extract_variables = this.editingExtractVars
      this.extractDialogVisible = false
    },
    async submitForm() {
      this.$refs.form.validate(async valid => {
        if (!valid) return
        if (this.form.scenario.steps.length === 0) {
          this.$message.error('请至少添加一个请求步骤')
          return
        }

          this.submitting = true
          this.parseAuthBody()
          try {
            const payload = {
              name: this.form.name,
              description: this.form.description,
              project_id: this.form.project_id,
              concurrent_users: this.form.concurrent_users,
              run_mode: this.form.run_mode,
              duration_seconds: this.form.duration_seconds,
              total_requests_limit: this.form.total_requests_limit,
              target_base_url: this.form.base_url || null,
              user_pool: this.form.user_pool.enabled ? {
                variable_name: this.form.user_pool.variable_name.replace(/^\$\{|\}$/g, ''),
                mode: this.form.user_pool.mode || 'random',
                auth_config: {
                  login_url: this.form.user_pool.auth_config.login_url || null,
                  token_key: this.form.user_pool.auth_config.token_key || 'access_token',
                  login_body_template: this.form.user_pool.auth_config.login_body_template || null
                }
              } : null,
              scenario: {
                name: this.form.scenario.name || this.form.name,
                enabled: true,
                scenario_delay_ms: this.form.scenario.scenario_delay_ms || 0,
                steps: this.form.scenario.steps
              }
            }

          if (this.isEdit) {
            await updatePerformanceTest(this.editId, payload)
            this.$message.success('压测已更新')
          } else {
            await createPerformanceTest(payload)
            this.$message.success('压测已创建')
          }
          this.$router.push('/performance/index')
        } catch (e) {
          console.error('提交失败', e)
          this.$message.error(this.isEdit ? '更新失败' : '创建失败')
        } finally {
          this.submitting = false
        }
      })
    },
    getModuleName(moduleId) {
      const m = this.moduleOptions.find(mod => mod.id === moduleId)
      return m ? m.name : '-'
    },
    async showInterfacePicker() {
      this.interfaceDialogVisible = true
      this.interfaceSearch = ''
      this.moduleSearch = ''
      this.selectedInterfaceRow = null
      this.interfacePage = 1
      this.interfacePageSize = 20
      if (this.moduleOptions.length === 0) {
        await this.getModuleOptions()
      }
      await this.getInterfaceList()
    },
    async getInterfaceList() {
      try {
        const res = await getInterfaceList({
          page: this.interfacePage,
          limit: this.interfacePageSize,
          name: this.interfaceSearch || undefined,
          moduleId: this.moduleSearch || undefined
        })
        if (res && res.code === '0' && res.data) {
          const d = res.data
          this.interfaceList = Array.isArray(d) ? d : (d.items || [])
          this.interfaceTotal = Array.isArray(d) ? d.length : (d.total || 0)
        }
      } catch (e) {
        console.error('获取接口列表失败', e)
      }
    },
    async getModuleOptions() {
      try {
        const res = await getModuleList({ limit: 1000 })
        if (res && res.code === '0' && res.data) {
          this.moduleOptions = res.data.items || res.data || []
        }
      } catch (e) {
        console.error('获取模块列表失败', e)
      }
    },
    handleInterfaceSearch() {
      this.interfacePage = 1
      this.getInterfaceList()
    },
    handleInterfacePageChange(page) {
      this.interfacePage = page
      this.getInterfaceList()
    },
    handleInterfaceSizeChange(size) {
      this.interfacePageSize = size
      this.interfacePage = 1
      this.getInterfaceList()
    },
    handleInterfaceRowClick(row) {
      this.selectedInterfaceRow = row
    },
    async confirmAddInterfaceStep() {
      if (!this.selectedInterfaceRow) {
        this.$message.warning('请先选择一行接口')
        return
      }
      try {
        const res = await getInterface(this.selectedInterfaceRow.id)
        if (res && res.code === '0' && res.data) {
          const iface = res.data
          this.form.scenario.steps.push({
            name: iface.name,
            interface_id: iface.id,
            override_method: iface.method || 'GET',
            override_url: iface.url || '',
            override_headers: iface.headers || {},
            override_body: iface.body || {},
            think_time_ms: 0,
            extract_variables: []
          })
        }
      } catch (e) {
        this.$message.error('获取接口详情失败')
      }
      this.interfaceDialogVisible = false
    },
    cancelForm() {
      this.$router.push('/performance/index')
    }
  }
}
</script>

<style scoped>
.tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  margin-top: 4px;
}
.box-card {
  border-radius: 8px;
}
</style>
