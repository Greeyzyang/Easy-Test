<template>
  <div class="app-container">
    <el-form
      ref="form"
      :model="form"
      :rules="rules"
      label-width="120px"
      class="dialog-form"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="函数名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入函数名称" />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入函数描述" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <!-- 移除了参数配置 -->
        </el-col>
      </el-row>
      <el-form-item label="函数代码" prop="code">
        <div class="editor-container">
          <monaco-editor
            v-model="form.code"
            language="python"
            :options="editorOptions"
            @change="onEditorChange"
          />
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit" :loading="submitLoading">创建</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { createFunction } from '@/api/function'
import MonacoEditor from '@/components/MonacoEditor'

export default {
  name: 'FunctionCreate',
  components: {
    MonacoEditor
  },
  data() {
    return {
      submitLoading: false,
      form: {
        name: '',
        description: '',
        code: ''
      },
      rules: {
        name: [{ required: true, message: '请输入函数名称', trigger: 'blur' }],
        code: [{ required: true, message: '请输入函数代码', trigger: 'blur' }]
      },
      editorOptions: {
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: {
          enabled: false
        },
        scrollBeyondLastLine: false,
        fontSize: 14,
        tabSize: 4,
        wordWrap: 'on'
      }
    }
  },
  methods: {
    // 移除了 addParameter 和 removeParameter 方法
    onEditorChange(value) {
      this.form.code = value
    },
    onSubmit() {
      this.$refs.form.validate(valid => {
        if (valid) {
          this.submitLoading = true
          // 确保只提交 name, description, code
          const submitData = {
            name: this.form.name,
            description: this.form.description,
            code: this.form.code
          }
          createFunction(submitData).then(() => {
            this.$message({
              message: '创建成功',
              type: 'success'
            })
            this.$router.push('/functions/list')
          }).catch(error => {
            console.error('创建函数失败:', error)
            this.$message.error(error.response?.data?.msg || '创建函数失败')
          }).finally(() => {
            this.submitLoading = false
          })
        }
      })
    },
    onCancel() {
      this.$router.push('/functions/list')
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
  background: #fff;
}

.dialog-form {
  padding: 20px;
}

.editor-container {
  height: 400px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

</style> 