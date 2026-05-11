<template>
  <div class="app-container">
    <div class="page-title">编辑接口</div>
    <interface-form v-if="!loading" ref="interfaceForm" :initial-data="initialData" :key="initialData.id" />
    <div class="form-actions">
      <el-button @click="onCancel">取消</el-button>
      <el-button type="primary" @click="onSubmit" :loading="submitting">保存</el-button>
    </div>
  </div>
</template>

<script>
import { getInterface, updateInterface } from '@/api/interface'
import InterfaceForm from './components/InterfaceForm.vue'

export default {
  name: 'InterfaceEdit',
  components: {
    InterfaceForm
  },
  data() {
    return {
      submitting: false,
      loading: false,
      initialData: {}
    }
  },
  created() {
    this.getInterfaceData()
  },
  methods: {
    async getInterfaceData() {
      this.loading = true
      try {
        const id = this.$route.params.id
        const response = await getInterface(id)
        if (response && response.code === '0' && response.data) {
          this.initialData = response.data
        } else {
          throw new Error(response.message || '获取接口详情失败')
        }
      } catch (error) {
        console.error('获取接口详情失败:', error)
        this.$message.error(error.message || '获取接口详情失败，请稍后重试')
      } finally {
        this.loading = false
      }
    },
    async onSubmit() {
      try {
        this.submitting = true
        const formData = await this.$refs.interfaceForm.validate()
        const id = this.$route.params.id
        const response = await updateInterface(id, formData)
        
        if (response.code === '0') {
          this.$message({
            message: '更新成功',
            type: 'success'
          })
          this.$router.push('/design/interfaces')
        } else {
          throw new Error(response.message || '更新接口失败')
        }
      } catch (error) {
        console.error('更新接口失败:', error)
        this.$message.error(error.message || '更新接口失败，请稍后重试')
      } finally {
        this.submitting = false
      }
    },
    onCancel() {
      this.$router.push('/design/interfaces')
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
  background: #fff;
}

.page-title {
  font-size: 20px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #EBEEF5;
}

.form-actions {
  margin-top: 30px;
  text-align: center;
}

.form-actions .el-button {
  padding: 12px 35px;
  margin: 0 10px;
}
</style> 