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
        <el-form-item label="目标环境" prop="env_name">
          <el-input v-model="form.env_name" placeholder="请输入环境变量名（请参考全局变量）" />
        </el-form-item>
      </el-card>

      <el-card class="box-card">
        <div slot="header" class="clearfix">
          <span>测试用例</span>
          <el-button 
            style="float: right; padding: 3px 0" 
            type="text"
            @click="handleAddCase"
          >添加用例</el-button>
        </div>
        
        <div v-if="!form.testcases || form.testcases.length === 0" class="empty-cases">
          <el-empty description="暂无测试用例">
            <el-button type="primary" @click="handleAddCase">添加用例</el-button>
          </el-empty>
        </div>
        
        <el-table
          v-else
          :data="selectedTestcases"
          border
          fit
          style="width: 100%; margin-bottom: 20px;"
        >
          <el-table-column label="用例名称" min-width="180">
            <template slot-scope="scope">
              <span>{{ scope.row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="100" align="center">
            <template slot-scope="scope">
              <el-tag :type="getPriorityType(scope.row.priority)">P{{ scope.row.priority }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="描述" min-width="220" show-overflow-tooltip>
            <template slot-scope="scope">
              <span>{{ scope.row.description || '-' }}</span>
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
      </el-card>

      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" @click="onSubmit" :loading="submitting">创建</el-button>
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
                @keyup.enter.native="searchTestcases"
              />
            </el-col>
            <el-col :span="6">
              <el-select
                v-model="caseQuery.priority"
                placeholder="优先级"
                clearable
                style="width: 100%"
                @change="searchTestcases"
              >
                <el-option
                  v-for="item in priorityOptions"
                  :key="item"
                  :label="`P${item}`"
                  :value="item"
                />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-button type="primary" @click="searchTestcases">搜索</el-button>
            </el-col>
          </el-row>
        </div>

        <el-table
          ref="caseTable"
          :data="testcaseList"
          style="width: 100%"
          border
          @selection-change="handleCaseSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="用例名称" min-width="180" />
          <el-table-column label="优先级" width="100" align="center">
            <template slot-scope="scope">
              <el-tag :type="getPriorityType(scope.row.priority)">P{{ scope.row.priority }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
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
import { getTestCases } from '@/api/testcase'
import Pagination from '@/components/Pagination'

export default {
  name: 'TestSuiteCreate',
  components: { Pagination },
  data() {
    return {
      form: {
        name: '',
        description: '',
        env_name: '',
        testcases: []
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
          { required: true, message: '请输入目标环境变量名', trigger: 'blur' }
        ]
      },
      submitting: false,
      selectedTestcases: [],
      caseSelectVisible: false,
      caseQuery: {
        page: 1,
        limit: 10,
        name: undefined,
        priority: undefined
      },
      testcaseList: [],
      totalCases: 0,
      selectedCases: [],
      priorityOptions: [1, 2, 3]
    }
  },
  methods: {
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
          priority: this.caseQuery.priority
        })
        
        if (response && response.code === '0' && response.data) {
          this.testcaseList = Array.isArray(response.data) ? response.data : 
                             (response.data.items ? response.data.items : [])
          this.totalCases = response.total || 0
          
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
    },
    onCaseSelectClose() {
      this.selectedCases = []
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
        const response = await createTestSuite(this.form)
        
        if (response && response.code === '0') {
          this.$message.success('创建成功')
          this.$router.push('/testsuites/list')
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
      this.$router.push('/testsuites/list')
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
</style> 