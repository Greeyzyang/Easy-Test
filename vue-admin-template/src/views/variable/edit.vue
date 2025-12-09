<template>
  <div class="app-container">
    <h2>编辑全局变量</h2>
    <el-form :model="form" ref="form" label-width="100px">
      <el-form-item label="变量名" prop="key">
        <el-input v-model="form.key" placeholder="请输入变量名" />
      </el-form-item>
      <el-form-item label="变量值" prop="value">
        <el-input
          type="textarea"
          v-model="form.value"
          placeholder="请输入变量值"
          :rows="6"
        />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input v-model="form.description" placeholder="请输入描述" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit">保存</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { getVariable, updateVariable } from '@/api/variable'
import router from '@/router'

export default {
  name: 'VariableEdit',
  data() {
    return {
      form: {
        id: '',
        key: '',
        value: '',
        description: ''
      }
    }
  },
  created() {
    const id = this.$route.query.id
    if (id) {
      getVariable(id).then(response => {
        this.form = response.data
      })
    }
  },
  methods: {
    onSubmit() {
      updateVariable(this.form.id, this.form).then(() => {
        this.$message.success('保存成功')
        router.push({ path: '/variable/list' })
      })
    },
    onCancel() {
      router.push({ path: '/variable/list' })
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
}
</style> 