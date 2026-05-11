<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px">
      <el-card class="box-card">
        <div slot="header" class="clearfix">
          <span>基本信息</span>
        </div>
        <el-form-item label="套件名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入套件名称" />
        </el-form-item>
        <el-form-item label="套件描述" prop="description">
          <el-input v-model="form.description" type="textarea" rows="4" placeholder="请输入套件描述" />
        </el-form-item>
        <el-form-item label="测试环境" prop="env_name">
          <el-select v-model="form.env_name" placeholder="请选择测试环境" clearable filterable style="width: 100%">
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
          <div class="tip" style="font-size: 12px; color: #909399; margin-top: 5px;">
            <i class="el-icon-info" /> 环境选项来自全局变量 'env' 的配置
          </div>
        </el-form-item>

        <el-form-item label="公共请求头">
          <div v-for="(header, index) in form.headersList" :key="index" style="margin-bottom: 10px; display: flex; align-items: center;">
            <el-input v-model="header.key" placeholder="Key (e.g. Authorization)" style="width: 200px; margin-right: 10px;" />
            <el-input v-model="header.value" placeholder="Value (e.g. ${token})" style="width: 300px; margin-right: 10px;" />
            <el-button type="danger" icon="el-icon-delete" circle size="mini" @click="removeHeader(index)" />
          </div>
          <el-button type="text" icon="el-icon-plus" @click="addHeader">添加请求头</el-button>
          <div class="tip" style="font-size: 12px; color: #909399;">
            <i class="el-icon-info" /> 这些请求头将应用于该套件下的所有测试步骤，支持变量引用
          </div>
        </el-form-item>
      </el-card>

      <el-card class="box-card">
        <div slot="header" class="clearfix">
          <span>测试用例</span>
        </div>

        <div>
          <el-table
            ref="testcaseTable"
            :data="selectedTestcases"
            border
            fit
            row-key="id"
            style="width: 100%; margin-bottom: 20px;"
          >
            <el-table-column width="40" align="center">
              <template slot-scope="{}">
                <i class="el-icon-s-operation drag-handle" style="cursor: move; color: #909399;" />
              </template>
            </el-table-column>
            <el-table-column label="用例名称" min-width="180">
              <template slot-scope="scope">
                <router-link
                  :to="'/design/testcases/edit/' + scope.row.id"
                  class="link-type"
                  target="_blank"
                >
                  <span>{{ scope.row.name }}</span>
                </router-link>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="100" align="center">
              <template slot-scope="scope">
                <el-tag :type="getPriorityType(scope.row.priority)">P{{ scope.row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="描述" min-width="220">
              <template slot-scope="scope">
                <EllipsisCell :value="scope.row.description || '-'" :detect-json="false" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template slot-scope="scope">
                <el-button
                  type="danger"
                  size="mini"
                  icon="el-icon-delete"
                  @click="handleRemoveCase(scope.$index)"
                >删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="add-case-wrapper">
            <el-button
              type="primary"
              class="add-case-btn"
              @click="handleAddCase"
            >
              <div class="add-case-content">
                <i class="el-icon-plus add-icon" />
                <span class="add-text">添加测试用例</span>
                <div class="add-desc">点击添加新的测试用例</div>
              </div>
            </el-button>
          </div>
        </div>
      </el-card>

      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" :loading="submitting" @click="onSubmit">创建</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>

    <!-- 选择测试用例弹窗 -->
    <el-dialog
      title="选择测试用例"
      :visible.sync="caseSelectVisible"
      width="70%"
      @close="onCaseSelectClose"
    >
      <div class="dialog-content">
        <div class="search-section">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-input
                v-model="caseQuery.name"
                placeholder="搜索用例名称"
                prefix-icon="el-icon-search"
                clearable
                @input="searchTestcases"
              />
            </el-col>
            <el-col :span="12">
              <el-select
                v-model="caseQuery.module_id"
                placeholder="所属模块"
                clearable
                style="width: 100%"
                @change="searchTestcases"
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
          ref="caseTable"
          :data="testcaseList"
          style="width: 100%"
          border
          row-key="id"
          @selection-change="handleCaseSelectionChange"
        >
          <el-table-column type="selection" width="55" reserve-selection />
          <el-table-column prop="name" label="用例名称" min-width="180" />
          <el-table-column label="优先级" width="100" align="center">
            <template slot-scope="scope">
              <el-tag :type="getPriorityType(scope.row.priority)">P{{ scope.row.priority }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="描述" min-width="220">
            <template slot-scope="scope">
              <EllipsisCell :value="scope.row.description || '-'" :detect-json="false" />
            </template>
          </el-table-column>
        </el-table>

        <pagination
          v-show="totalCases > 0"
          :total="totalCases"
          :page.sync="caseQuery.page"
          :limit.sync="caseQuery.limit"
          @pagination="getTestcaseList"
        />
      </div>

      <span slot="footer" class="dialog-footer">
        <el-button @click="caseSelectVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCaseSelection">确定</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { createTestSuite } from '@/api/testsuite'
import { getList as getVariables } from '@/api/variable'
import { getTestCases } from '@/api/testcase'
import { getModuleList } from '@/api/module'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'
import Sortable from 'sortablejs'

export default {
  name: 'TestSuiteCreate',
  components: { Pagination, EllipsisCell },
  data() {
    return {
      form: {
        name: '',
        description: '',
        env_name: '',
        testcases: [],
        headersList: []
      },
      rules: {
        name: [
          { required: true, message: '请输入套件名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        description: [
          { max: 500, message: '描述不能超过500个字符', trigger: 'blur' }
        ],
        env_name: [
          { required: true, message: '请选择测试环境', trigger: 'change' }
        ]
      },
      envOptions: [],
      submitting: false,
      selectedTestcases: [],
      caseSelectVisible: false,
      caseQuery: {
        page: 1,
        limit: 10,
        name: undefined,
        module_id: undefined
      },
      testcaseList: [],
      totalCases: 0,
      selectedCases: [],
      moduleOptions: []
    }
  },
  created() {
    this.getEnvOptions()
    this.getModuleOptions()
  },
  methods: {
    async getModuleOptions() {
      try {
        const response = await getModuleList({ page: 1, limit: 1000 })
        if (response && response.code === '0' && response.data && response.data.items) {
          this.moduleOptions = response.data.items
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
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
              console.error('解析 env 变量失败:', e)
              this.envOptions = []
            }
          }
        }
      } catch (error) {
        console.error('获取全局变量失败:', error)
      }
    },
    getPriorityType(priority) {
      const types = {
        1: 'danger',
        2: 'warning',
        3: 'primary',
        4: 'success',
        5: 'info'
      }
      return types[priority] || 'info'
    },
    addHeader() {
      this.form.headersList.push({ key: '', value: '' })
    },
    removeHeader(index) {
      this.form.headersList.splice(index, 1)
    },
    handleAddCase() {
      this.caseSelectVisible = true
      this.getTestcaseList()
    },
    handleRemoveCase(index) {
      const removed = this.selectedTestcases.splice(index, 1)[0]
      this.form.testcases = this.form.testcases.filter(id => id !== removed.id)
    },
    async getTestcaseList() {
      try {
        const response = await getTestCases({
          page: this.caseQuery.page,
          limit: this.caseQuery.limit,
          name: this.caseQuery.name,
          module_id: this.caseQuery.module_id
        })

        if (response && response.code === '0' && response.data) {
          this.testcaseList = Array.isArray(response.data) ? response.data
            : (response.data.items ? response.data.items : [])
          this.totalCases = response.data.total || this.testcaseList.length

          // 预选中已选的用例
          this.$nextTick(() => {
            if (this.$refs.caseTable) {
              this.testcaseList.forEach(row => {
                if (this.form.testcases.includes(row.id)) {
                  this.$refs.caseTable.toggleRowSelection(row, true)
                }
              })
            }
          })
        } else {
          this.$message.error(response.message || '获取测试用例列表失败')
        }
      } catch (error) {
        console.error('获取测试用例列表失败:', error)
        this.$message.error(error.response?.data?.message || '获取测试用例列表失败')
      }
    },
    searchTestcases() {
      this.caseQuery.page = 1
      this.getTestcaseList()
    },
    handleCaseSelectionChange(selection) {
      this.selectedCases = selection
    },
    confirmCaseSelection() {
      // 合并已选择的用例和新选择的用例
      const newSelectedCases = this.selectedCases.filter(
        item => !this.form.testcases.includes(item.id)
      )

      // 更新已选用例列表和ID
      this.selectedTestcases = [
        ...this.selectedTestcases,
        ...newSelectedCases
      ]

      // 更新表单中的用例ID列表
      this.form.testcases = this.selectedTestcases.map(item => item.id)

      this.caseSelectVisible = false
      this.initSortable()
    },
    initSortable() {
      this.$nextTick(() => {
        const el = this.$refs.testcaseTable && this.$refs.testcaseTable.$el.querySelector('tbody')
        if (!el) return
        if (this.sortable) {
          this.sortable.destroy()
        }
        this.sortable = new Sortable(el, {
          handle: '.drag-handle',
          animation: 150,
          onEnd: ({ newIndex, oldIndex }) => {
            const targetRow = this.selectedTestcases.splice(oldIndex, 1)[0]
            this.selectedTestcases.splice(newIndex, 0, targetRow)

            // 更新表单中的用例ID列表
            this.form.testcases = this.selectedTestcases.map(item => item.id)
          }
        })
      })
    },
    onCaseSelectClose() {
      this.selectedCases = []
      if (this.$refs.caseTable) {
        this.$refs.caseTable.clearSelection()
      }
    },
    async onSubmit() {
      try {
        await this.$refs.form.validate()

        if (!this.form.testcases.length) {
          this.$confirm('当前测试套件没有添加任何测试用例，是否继续创建?', '提示', {
            confirmButtonText: '继续创建',
            cancelButtonText: '取消',
            type: 'warning'
          }).then(() => {
            this.submitForm()
          }).catch(() => {})
        } else {
          this.submitForm()
        }
      } catch (error) {
        console.error('表单验证失败:', error)
      }
    },
    async submitForm() {
      this.submitting = true
      try {
        // 处理请求头
        const headers = {}
        this.form.headersList.forEach(item => {
          if (item.key) {
            headers[item.key] = item.value
          }
        })

        const submitData = {
          ...this.form,
          headers
        }
        delete submitData.headersList

        const response = await createTestSuite(submitData)

        if (response && response.code === '0') {
          this.$message.success('创建成功')
          this.$router.push('/execution/testsuites')
        } else {
          this.$message.error(response.message || '创建失败')
        }
      } catch (error) {
        console.error('创建测试套件失败:', error)
        this.$message.error(error.response?.data?.message || '创建失败')
      } finally {
        this.submitting = false
      }
    },
    onCancel() {
      this.$router.push('/execution/testsuites')
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

  .clearfix {
    display: flex;
    justify-content: space-between;
    align-items: center;

    span {
      font-size: 16px;
      font-weight: 500;
    }
  }
}

.empty-cases {
  padding: 30px 0;
  text-align: center;
}

.search-section {
  margin-bottom: 20px;
}

.el-tag {
  margin-right: 10px;
}

.add-case-wrapper {
  margin-top: 15px;
  padding: 0;
  border-radius: 4px;
  background: transparent;
}

.add-case-btn {
  width: 100%;
  height: auto;
  padding: 15px;
  border: 1px dashed #d9d9d9;
  background: #fafafa;
  transition: all 0.3s ease;
}

.add-case-btn:hover {
  border-color: #409EFF;
  background: #f5f7fa;
}

.add-case-content {
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

.link-type {
  color: #409EFF;
  cursor: pointer;
  text-decoration: none;

  &:hover {
    color: #66b1ff;
  }
}
</style>
