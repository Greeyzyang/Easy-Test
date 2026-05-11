<template>
  <div class="app-container">
    <div class="page-title">创建接口</div>
    <interface-form ref="interfaceForm" />
    <div class="form-actions">
      <el-button @click="onCancel">取消</el-button>
      <el-button type="primary" @click="onSubmit" :loading="submitting">保存</el-button>
    </div>
  </div>
</template>

<script>
import { createInterface } from '@/api/interface'
import InterfaceForm from './components/InterfaceForm.vue'

export default {
  name: 'InterfaceCreate',
  components: {
    InterfaceForm
  },
  data() {
    return {
      submitting: false
    }
  },
  methods: {
    async onSubmit() {
      try {
        this.submitting = true
        const formData = await this.$refs.interfaceForm.validate()
        const response = await createInterface(formData)
        
        if (response.code === '0') {
          this.$message({
            message: '创建成功',
            type: 'success'
          })
          this.$router.push('/design/interfaces')
        } else {
          throw new Error(response.message || '创建接口失败')
        }
      } catch (error) {
        console.error('创建接口失败:', error)
        this.$message.error(error.message || '创建接口失败，请稍后重试')
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