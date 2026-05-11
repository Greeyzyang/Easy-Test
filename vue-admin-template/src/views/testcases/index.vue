<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="用例名称"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-select
        v-model="listQuery.module_id"
        placeholder="所属模块"
        clearable
        style="width: 200px"
        class="filter-item"
        @change="handleFilter"
      >
        <el-option
          v-for="item in moduleOptions"
          :key="item.id"
          :label="item.name"
          :value="item.id"
        />
      </el-select>
      <el-button v-waves class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>
      <el-button class="filter-item" style="margin-left: 10px;" type="primary" icon="el-icon-edit" @click="handleCreate">
        新建用例
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="Loading"
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="用例名称" min-width="150">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属模块" width="150" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.module ? scope.row.module.name : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="标签"
        width="150"
        show-overflow-tooltip
      >
        <template slot-scope="scope">
          <el-tag
            v-for="tag in scope.row.tags"
            :key="tag"
            size="mini"
            class="list-tag"
          >
            {{ tag }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="280" fixed="right">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
            编辑
          </el-button>
          <el-button type="success" size="mini" @click="handleCopy(scope.row)">
            复制
          </el-button>
          <el-button type="warning" size="mini" @click="handleExecute(scope.row)">
            执行
          </el-button>
          <el-button type="danger" size="mini" @click="handleDelete(scope.row)">
            删除
          </el-button>
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
  </div>
</template>

<script>
import { getTestCases, deleteTestCase, getTestCase, createTestCase } from '@/api/testcase'
import { getModuleList } from '@/api/module'
import waves from '@/directive/waves'
import Pagination from '@/components/Layout/Pagination'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'TestcaseList',
  components: { Pagination },
  directives: { waves },
  data() {
    return {
      list: null,
      total: 0,
      listLoading: true,
      moduleOptions: [],
      listQuery: {
        page: 1,
        limit: 20,
        name: undefined,
        module_id: undefined
      }
    }
  },
  created() {
    this.getModules()
    this.getList()
  },
  methods: {
    async getModules() {
      try {
        const response = await getModuleList({ page: 1, limit: 100 })
        if (response && response.code === '0') {
          this.moduleOptions = response.data.items || []
        }
      } catch (error) {
        console.error('Fetch modules failed', error)
      }
    },
    async getList() {
      this.listLoading = true
      try {
        const response = await getTestCases(this.listQuery)
        console.log('API Response:', response)
        // 后端返回 { code: '0', data: { items: [...], total: 100 } }
        if (response && response.code === '0' && response.data) {
          const { items, total } = response.data
          this.list = items || []
          this.total = total || 0
        } else {
          console.error('Unexpected response format:', response)
          this.$message.error('数据格式错误')
        }
      } catch (error) {
        console.error('获取测试用例列表失败:', error)
        this.$message.error(error.response?.data?.msg || '获取测试用例列表失败')
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/design/testcases/create')
    },
    handleUpdate(row) {
      this.$router.push(`/design/testcases/edit/${row.id}`)
    },
    async handleDelete(row) {
      try {
        await this.$confirm('确认删除该测试用例吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteTestCase(row.id)
        this.$message.success('删除成功')
        this.getList()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除测试用例失败:', error)
          this.$message.error(error.response?.data?.msg || '删除测试用例失败')
        }
      }
    },
    async handleCopy(row) {
      try {
        const { data } = await getTestCase(row.id)
        if (!data) {
          throw new Error('测试用例不存在')
        }
        
        // 获取所有测试用例名称
        const allTestcases = await getTestCases({ limit: 1000 })
        const items = allTestcases.data.items || allTestcases.data
        const existingNames = items.map(item => item.name)
        
        // 生成新名称
        let newName = data.name
        let counter = 1
        while (existingNames.includes(newName + ` (${counter})`)) {
          counter++
        }
        newName = newName + ` (${counter})`
        
        // 复制数据，修改名称
        const copyData = {
          ...data,
          name: newName,
          id: undefined,
          created_time: undefined,
          updated_time: undefined
        }
        
        // 创建新的测试用例
        await createTestCase(copyData)
        this.$message.success('复制成功')
        this.getList()
      } catch (error) {
        console.error('复制测试用例失败:', error)
        this.$message.error(error.response?.data?.msg || '复制测试用例失败')
      }
    },
    getPriorityType(priority) {
      const typeMap = {
        1: 'danger',
        2: 'warning',
        3: 'info',
        4: 'success',
        5: ''
      }
      return typeMap[priority] || ''
    },
    handleExecute(row) {
      this.$message({
        message: `开始执行测试用例: ${row.name}`,
        type: 'info'
      })
      // TODO: 实现测试用例执行逻辑
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

.link-type {
  color: #409EFF;
  cursor: pointer;
  &:hover {
    color: #66b1ff;
  }
}

.el-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.el-tag + .el-tag {
  margin-left: 0;
}

.pagination-container {
  margin-top: 20px;
  text-align: right;
}

.list-tag {
  margin: 2px;
  height: 20px;
  line-height: 18px;
  font-size: 11px;
  padding: 0 4px;
}
</style> 