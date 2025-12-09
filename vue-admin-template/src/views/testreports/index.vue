<template>
  <div class="app-container">
    <div class="filter-container">
      <el-select v-model="listQuery.project_id" placeholder="选择项目" clearable style="width: 150px" class="filter-item">
        <el-option v-for="item in projectOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="listQuery.status" placeholder="执行状态" clearable style="width: 120px" class="filter-item">
        <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="加载中..."
      border
      fit
      highlight-current-row
      style="width: 100%"
    >
      <el-table-column label="报告名称" min-width="150px">
        <template slot-scope="{row}">
          <router-link :to="'/testreports/detail/'+row.id" class="link-type">
            <span>{{ row.name }}</span>
          </router-link>
        </template>
      </el-table-column>
      <el-table-column label="测试套件" width="150px" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.suite_name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="执行状态" width="100px" align="center">
        <template slot-scope="scope">
          <el-tag :type="statusTagType(scope.row.status)">{{ scope.row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="执行时间" width="180px" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.duration }}s</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="180" class-name="small-padding fixed-width">
        <template slot-scope="{row}">
          <el-button type="primary" size="mini" @click="handleDetail(row)">
            详情
          </el-button>
          <el-button type="danger" size="mini" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-sizes="[10, 20, 30, 50]"
        :page-size.sync="listQuery.limit"
        :current-page.sync="listQuery.page"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script>
import { getTestReports, deleteTestReport} from '@/api/testreport'
import { getProjectList } from '@/api/project'

export default {
  name: 'TestReportList',
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      statusOptions: [
        { label: '待处理', value: 'PENDING' },
        { label: '进行中', value: 'IN_PROGRESS' },
        { label: '已完成', value: 'COMPLETED' },
        { label: '失败', value: 'FAILED' },
        { label: '成功', value: 'PASSED' },
        { label: '跳过', value: 'SKIPPED' }
      ],
      listQuery: {
        page: 1,
        limit: 10,
        status: undefined,
        project_id: undefined
      },
      projectOptions: []
    }
  },
  created() {
    this.getList()
    this.getProjects()
  },
  methods: {
    statusTagType(status) {
      const statusMap = {
        PASSED: 'success',
        COMPLETED: 'success',
        FAILED: 'danger',
        IN_PROGRESS: 'warning',
        PENDING: 'info',
        SKIPPED: 'info'
      }
      return statusMap[String(status).toUpperCase()] || 'info'
    },
    async getList() {
      try {
        this.listLoading = true
        const { data } = await getTestReports(this.listQuery)
        this.list = data.map(item => ({
          id: item.id,
          name: item.name,
          suite_name: item.testsuite_name,
          status: item.status || 'success',
          duration: item.duration,
          pass_rate: item.pass_rate,
          total_cases: item.total_cases,
          passed_cases: item.passed_cases,
          failed_cases: item.failed_cases
        }))
        this.total = data.length
      } catch (error) {
        this.$message.error('获取测试报告列表失败：' + error.message)
      } finally {
        this.listLoading = false
      }
    },
    async getProjects() {
      try {
        const { data } = await getProjectList()
        this.projectOptions = data.map(item => ({
          label: item.name,
          value: item.id
        }))
      } catch (error) {
        this.$message.error('获取项目列表失败：' + error.message)
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleDetail(row) {
      this.$router.push(`/testreports/detail/${row.id}`)
    },
    async handleDelete(row) {
      try {
        await this.$confirm('确认删除该测试报告吗？', '提示', {
          type: 'warning'
        })
        await deleteTestReport(row.id)
        this.$message.success('删除成功')
        this.getList()
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('删除失败：' + error.message)
        }
      }
    },
    handleCurrentChange(val) {
      this.listQuery.page = val
      this.getList()
    },
    handleSizeChange(val) {
      this.listQuery.limit = val
      this.getList()
    }
  }
}
</script>

<style scoped>
.pagination-container {
  padding: 32px 16px;
}
.link-type {
  color: #409EFF;
  text-decoration: none;
}
.filter-container {
  padding-bottom: 10px;
}
.filter-item {
  margin-right: 10px;
}
</style> 