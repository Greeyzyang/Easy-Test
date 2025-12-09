<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="接口名称"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-select 
        v-model="listQuery.moduleId" 
        placeholder="所属模块" 
        clearable 
        style="width: 200px" 
        class="filter-item"
      >
        <el-option
          v-for="item in moduleOptions"
          :key="item.id"
          :label="item.name"
          :value="item.id"
        />
      </el-select>
      <el-button 
        v-waves 
        class="filter-item" 
        type="primary" 
        icon="el-icon-search" 
        @click="handleFilter"
      >
        搜索
      </el-button>
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="primary"
        icon="el-icon-plus"
        @click="handleCreate"
      >
        新建接口
      </el-button>
    </div>

    <el-table
      :key="tableKey"
      v-loading="listLoading"
      :data="list"
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="接口名称">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="请求地址">
        <template slot-scope="scope">
          <span>{{ scope.row.url }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属模块" align="center">
        <template slot-scope="scope">
          <span>{{ getModuleName(scope.row.module_id) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="版本" width="100" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.version }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="180" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" min-width="230">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
            编辑
          </el-button>
          <el-button type="success" size="mini" @click="handleCopy(scope.row)">
            复制
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
import { getInterfaceList, deleteInterface } from '@/api/interface'
import { getModuleList } from '@/api/module'
import waves from '@/directive/waves'
import Pagination from '@/components/Pagination'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'InterfaceList',
  components: { Pagination },
  directives: { waves },
  data() {
    return {
      tableKey: 0,
      list: [],
      total: 0,
      listLoading: true,
      listQuery: {
        page: 1,
        limit: 20,
        name: undefined,
        moduleId: undefined
      },
      moduleOptions: [],
      executeDialogVisible: false,
      currentInterface: null,
      executeResult: null,
      executing: false
    }
  },
  created() {
    this.getModules()
    this.getList()
  },
  methods: {
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
    async getModules() {
      try {
        const response = await getModuleList()
        if (response.code === '0' && response.data) {
          this.moduleOptions = response.data.map(module => ({
            id: module.id,
            name: module.name
          }))
        } else {
          throw new Error(response.message || '获取模块列表失败')
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
        this.$message.error(error.message || '获取模块列表失败，请稍后重试')
      }
    },
    async getList() {
      this.listLoading = true
      try {
        const params = {
          skip: (this.listQuery.page - 1) * this.listQuery.limit,
          limit: this.listQuery.limit,
          name: this.listQuery.name,
          module_id: this.listQuery.moduleId,
        }

        const response = await getInterfaceList(params)
        if (response.code === '0') {
          this.list = response.data.map(item => ({
            ...item,
            module: {
              ...item.module,
              project: item.module?.project || null
            }
          }))
          this.total = response.total || response.data.length
        } else {
          throw new Error(response.message || '获取接口列表失败')
        }
      } catch (error) {
        console.error('获取接口列表失败:', error)
        this.$message.error(error.message || '获取接口列表失败，请稍后重试')
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/interfaces/create')
    },
    handleUpdate(row) {
      this.$router.push(`/interfaces/edit/${row.id}`)
    },
    handleCopy(row) {
      const newInterface = { ...row }
      delete newInterface.id
      delete newInterface.created_time
      delete newInterface.updated_time
      newInterface.name = `${newInterface.name}-${newInterface.id}`
      this.$router.push({
        path: '/interfaces/create',
        query: { data: JSON.stringify(newInterface) }
      })
    },
    async handleDelete(row) {
      try {
        await this.$confirm('此操作将永久删除该接口，是否继续？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        const response = await deleteInterface(row.id)
        if (response.code === '0') {
          this.$message({
            type: 'success',
            message: '删除成功!'
          })
          this.getList()
        } else {
          throw new Error(response.message || '删除接口失败')
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除接口失败:', error)
          this.$message.error(error.message || '删除接口失败，请稍后重试')
        }
      }
    },
    getModuleName(moduleId) {
      const module = this.moduleOptions.find(m => m.id === moduleId)
      return module ? module.name : '-'
    },
    formatDateTime
  },
  computed: {
    safeSteps() {
      return Array.isArray(this.form.steps)
        ? this.form.steps.filter(step => !!step && typeof step === 'object')
        : [];
    }
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
</style> 