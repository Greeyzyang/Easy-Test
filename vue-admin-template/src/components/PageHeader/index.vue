<template>
  <div class="page-header">
    <div class="left">
      <span class="title">{{ title }}</span>
    </div>
    <div class="right">
      <el-button size="small" @click="handleCancel">取消</el-button>
      <el-button type="primary" size="small" @click="handleSave" :loading="loading">保存</el-button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PageHeader',
  props: {
    title: {
      type: String,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    },
    save: {
      type: Function,
      required: true
    },
    cancel: {
      type: Function,
      required: true
    }
  },
  methods: {
    handleSave() {
      this.save()
    },
    handleCancel() {
      this.cancel()
    }
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  margin-bottom: 20px;
  border-bottom: 1px solid #EBEEF5;
}

.title {
  font-size: 20px;
  font-weight: 500;
  color: #303133;
}

.right {
  display: flex;
  gap: 10px;
}
</style> 