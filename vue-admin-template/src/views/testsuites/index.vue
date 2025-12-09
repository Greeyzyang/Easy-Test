<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="selectedEnv"
        placeholder="请输入环境变量名（参考全局变量）"
        class="filter-item"
        style="width: 200px;"
      />
      <el-input
        v-model="listQuery.name"
        placeholder="任务名称"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-button v-waves class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="primary"
        icon="el-icon-plus"
        @click="handleCreate"
      >
        新建任务
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="加载中..."
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="任务名称">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述" show-overflow-tooltip>
        <template slot-scope="scope">
          <span>{{ scope.row.description || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="用例数量" align="center" width="100">
        <template slot-scope="scope">
          <el-tag>{{ scope.row.testcases ? scope.row.testcases.length : 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" width="160">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" width="160">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" min-width="280">
        <template slot-scope="scope">
          <div v-if="scope.row.running" style="width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;">
            <el-progress
              :percentage="scope.row.progressPercent"
              :text-inside="true"
              :stroke-width="20"
              style="width: 90%; margin-bottom: 8px;"
            />
            <div style="width: 100%; text-align: center; color: #409EFF;">{{ scope.row.progressText }}</div>
          </div>
          <div v-else style="display: flex; flex-direction: row; justify-content: center; align-items: center; flex-wrap: wrap;">
            <el-button 
              type="success" 
              size="mini" 
              :loading="scope.row.running" 
              @click="handleRun(scope.row)"
              style="margin: 5px;" 
            >
              运行
            </el-button>
            <el-button type="info" size="mini" @click="handleSchedule(scope.row)" style="margin: 5px;">
              定时
            </el-button>
            <el-button type="primary" size="mini" @click="handleUpdate(scope.row)" style="margin: 5px;">
              编辑
            </el-button>
            <el-button type="success" size="mini" @click="handleCopy(scope.row)" style="margin: 5px;">
              复制
            </el-button>
            <el-button type="danger" size="mini" @click="handleDelete(scope.row)" style="margin: 5px;">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total>0"
      :total="total"
      :page.sync="listQuery.page"
      :limit.sync="listQuery.limit"
      @pagination="getList"
    />

    <el-dialog :visible.sync="progressDialogVisible" title="执行进度" width="400px" :close-on-click-modal="false" :show-close="false">
      <el-progress :percentage="progressPercent" status="success" :text-inside="true" style="margin-bottom: 10px;" />
      <div style="text-align:center;">{{ progressText }}</div>
    </el-dialog>

    <el-dialog :visible.sync="scheduleDialogVisible" title="定时执行测试任务" width="500px">
      <el-form ref="scheduleForm" :model="scheduleForm" label-width="120px" :rules="scheduleRules">
        <el-form-item label="测试任务名称">
          <el-input v-model="currentSchedulingRow.name" :disabled="true" />
        </el-form-item>
        <el-form-item label="Cron 表达式" prop="cron_expression">
          <el-input v-model="scheduleForm.cron_expression" placeholder="例如: 0 0 * * * (每天零点执行)" />
          <div class="tip">
            Cron 表达式用于定义任务的执行时间。
            <a href="https://tool.lu/crontab/" target="_blank">点击此处查看 Cron 表达式生成工具</a>
          </div>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="cancelSchedule">
          取消
        </el-button>
        <el-button type="primary" @click="submitSchedule">
          确定
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getTestSuites, deleteTestSuite, createTestSuite, executeTestSuite, scheduleTestSuite } from '@/api/testsuite'
import waves from '@/directive/waves'
import Pagination from '@/components/Pagination'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'TestSuiteList',
  components: { Pagination },
  directives: { waves },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      listQuery: {
        page: 1,
        limit: 10,
        name: undefined
      },
      selectedEnv: '',
      progressDialogVisible: false,
      progressPercent: 0,
      progressText: '',
      ws: null,
      scheduleDialogVisible: false,
      scheduleForm: {
        testsuite_id: null,
        cron_expression: ''
      },
      currentSchedulingRow: { name: '' },
      scheduleRules: {
        cron_expression: [
          { required: true, message: '请输入 Cron 表达式', trigger: 'blur' },
          { pattern: /^(\S+\s+\S+\s+\S+\s+\S+\s+\S+\s*\S*)$/, message: '请输入有效的 Cron 表达式', trigger: 'blur' }
        ]
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    async getList() {
      this.listLoading = true
      try {
        const response = await getTestSuites(this.listQuery)
        if (response && response.code === '0' && response.data) {
          this.list = (Array.isArray(response.data) ? response.data : []).map(item => ({
            ...item,
            running: false,
            progressPercent: 0,
            progressText: ''
          }))
          this.total = response.total || this.list.length
        } else {
          console.error('获取测试任务列表失败:', response)
          this.$message.error(response.message || '获取测试任务列表失败')
          this.list = []
          this.total = 0
        }
      } catch (error) {
        console.error('获取测试任务列表失败:', error)
        this.$message.error(error.response?.data?.message || '获取测试任务列表失败')
        this.list = []
        this.total = 0
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/testsuites/create')
    },
    handleUpdate(row) {
      this.$router.push(`/testsuites/edit/${row.id}`)
    },
    async handleRun(row) {
      // 优先使用页面上输入的环境变量，如果为空，则使用测试任务本身保存的环境变量
      const envToUse = this.selectedEnv || row.env_name;
      if (!envToUse) {
        this.$message.error('请输入目标环境变量，或为测试任务设置一个默认环境');
        return;
      }
      console.log('--- handleRun: 开始执行 ---', row.id);
      this.$set(row, 'running', true);
      this.$set(row, 'progressPercent', 0);
      // 读取环境变量
      const baseApi = process.env.VUE_APP_BASE_API;

      // 解析出主机和端口（开发环境是 http://localhost:8000，生产环境是 /prod-api，需特殊处理）
      let wsHost;
      if (baseApi.startsWith('http')) {
        // 开发环境
        wsHost = baseApi.replace(/^http/, 'ws');
      } else {
        // 生产环境，假设和前端同域
        wsHost = window.location.origin.replace(/^http/, 'ws') + baseApi;
      }
      const wsUrl = `${wsHost}/rest/v1/testsuites/ws/progress/${row.id}`;
      console.log('WebSocket URL:', wsUrl);

      // 确保之前的WebSocket连接已关闭
      if (row.ws) {
        row.ws.close();
      }

      row.ws = new WebSocket(wsUrl);
      console.log('WebSocket 实例创建成功');

      // 1. 监听进度消息
      row.ws.onmessage = (event) => {
        try {
          console.log('WebSocket onmessage: 收到消息', event.data);
          const msg = JSON.parse(event.data);
          console.log('收到进度消息：', msg);
          this.$set(row, 'progressPercent', msg.progress);
          this.$set(row, 'progressText', msg.text);
          if (msg.progress >= 100) {
            console.log('进度达到100%，关闭WebSocket');
            setTimeout(() => {
              this.$set(row, 'running', false);
              if (row.ws && row.ws.readyState === WebSocket.OPEN) {
                row.ws.close();
              }
              console.log('WebSocket 已关闭');
            }, 1000);
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };

      // 2. 连接建立后再发起测试执行请求
      row.ws.onopen = async () => {
        console.log('WebSocket onopen: 连接已建立');
        try {
          console.log('发送 executeTestSuite 请求...');
          const response = await executeTestSuite(row.id, {
            env_name: envToUse
          });
          console.log('executeTestSuite 响应:', response);
          if (response && response.code === '0') {
            this.$message.success('测试任务开始执行');
            setTimeout(() => {
              this.$router.push({
                path: `/testreports/detail/${response.data.id}`
              });
            }, 1200);
          } else {
            this.$message.error(response.message || '执行失败');
            this.$set(row, 'running', false);
            if (row.ws && row.ws.readyState === WebSocket.OPEN) {
              row.ws.close();
            }
            console.error('executeTestSuite 执行失败:', response);
          }
        } catch (error) {
          console.error('executeTestSuite 请求异常:', error);
          this.$message.error(error.response?.data?.message || '执行失败');
          this.$set(row, 'running', false);
          if (row.ws && row.ws.readyState === WebSocket.OPEN) {
            row.ws.close();
          }
        }
      };

      row.ws.onerror = (error) => {
        console.error('WebSocket onerror: 连接失败', error);
        this.$set(row, 'running', false);
        this.$message.error('WebSocket 连接失败，无法实时显示进度');
        if (row.ws && row.ws.readyState === WebSocket.OPEN) {
          row.ws.close();
        }
      };

      row.ws.onclose = (event) => {
        console.log('WebSocket onclose: 连接已关闭', event);
      };
    },
    handleSchedule(row) {
      this.scheduleDialogVisible = true;
      this.currentSchedulingRow = row;
      this.scheduleForm.testsuite_id = row.id;
      this.scheduleForm.cron_expression = row.cron_expression || '';
      this.$nextTick(() => {
        this.$refs.scheduleForm.clearValidate();
      });
    },
    submitSchedule() {
      this.$refs.scheduleForm.validate(async (valid) => {
        if (valid) {
          console.log('提交定时任务:', this.scheduleForm);
          try {
            const response = await scheduleTestSuite(this.scheduleForm);
            if (response && response.code === '0') {
              this.$message.success('定时任务已成功创建！');
              this.scheduleDialogVisible = false;
              // 可以在这里刷新列表或更新UI以显示定时任务状态
            } else {
              this.$message.error(response.message || '创建定时任务失败！');
            }
          } catch (error) {
            console.error('调用定时任务API失败:', error);
            this.$message.error(error.response?.data?.message || '创建定时任务失败，请检查网络或后端服务');
          }
        } else {
          console.log('表单验证失败');
          return false;
        }
      });
    },
    cancelSchedule() {
      this.scheduleDialogVisible = false;
    },
    async handleDelete(row) {
      try {
        await this.$confirm(`确认删除测试任务 "${row.name}" 吗?`, '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        const response = await deleteTestSuite(row.id)
        if (response && response.code === '0') {
          this.$message.success('删除成功')
          this.getList()
        } else {
          this.$message.error(response.message || '删除失败')
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除测试任务失败:', error)
          this.$message.error(error.response?.data?.message || '删除失败')
        }
      }
    },
    async handleCopy(row) {
      try {
        const allTestSuitesRes = await getTestSuites({ limit: 1000 })
        if (allTestSuitesRes.code !== '0') {
          throw new Error(allTestSuitesRes.message || '获取测试任务列表失败')
        }
        
        const existingNames = Array.isArray(allTestSuitesRes.data) 
          ? allTestSuitesRes.data.map(item => item.name)
          : []
        
        let newName = row.name
        let counter = 1
        while (existingNames.includes(newName + ` (${counter})`)) {
          counter++
        }
        newName = newName + ` (${counter})`
        
        const copyData = {
          name: newName,
          description: row.description,
          testcases: row.testcases ? row.testcases.map(tc => tc.id) : []
        }
        
        const response = await createTestSuite(copyData)
        if (response && response.code === '0') {
          this.$message.success('复制成功')
          this.getList()
        } else {
          this.$message.error(response.message || '复制失败')
        }
      } catch (error) {
        console.error('复制测试任务失败:', error)
        this.$message.error(error.response?.data?.message || '复制测试任务失败')
      }
    },
    formatDateTime
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
  background: #fff;
}

.filter-container {
  padding-bottom: 10px;
  .filter-item {
    display: inline-block;
    vertical-align: middle;
    margin-bottom: 10px;
    margin-right: 10px;
  }
}

.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
  line-height: 1.5;
}

.link-type {
  color: #409EFF;
  cursor: pointer;
  &:hover {
    color: #66b1ff;
  }
}

.pagination-container {
  margin-top: 20px;
  text-align: right;
}

.env-select-dialog {
  .el-select {
    width: 100%;
    margin-top: 10px;
  }
}
</style> 