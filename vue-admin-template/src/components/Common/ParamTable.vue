<template>
  <div class="param-table">
    <el-button type="text" icon="el-icon-plus" @click="$emit('add')" class="add-btn">
      添加{{ title }}
    </el-button>
    <el-table :data="params" style="width: 100%" size="small" border>
      <el-table-column label="参数名" min-width="150">
        <template slot-scope="scope">
          <el-input v-model="scope.row.name" placeholder="参数名" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="参数值" min-width="200">
        <template slot-scope="scope">
            <div v-if="scope.row.type === 'file'" class="file-upload-wrapper">
              <el-input 
                :value="getDisplayValue(scope.row.value)" 
                placeholder="选择文件或输入路径" 
                size="small"
                class="file-path-input"
                @input="(val) => scope.row.value = val"
              >
                <el-upload
                  slot="append"
                  action=""
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="(file) => handleFileUpload({file: file.raw}, scope.row)"
                >
                  <el-button size="small" icon="el-icon-upload2"></el-button>
                </el-upload>
              </el-input>
            </div>
            <el-input 
              v-else
              v-model="scope.row.value" 
              placeholder="参数值" 
              size="small" 
            />
          </template>
      </el-table-column>
      <el-table-column v-if="showType" label="类型" width="120">
        <template slot-scope="scope">
          <el-select v-model="scope.row.type" size="small" style="width: 100%">
            <el-option label="String" value="string" />
            <el-option label="Number" value="number" />
            <el-option label="Boolean" value="boolean" />
            <el-option label="File" value="file" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="必填" width="80" align="center">
        <template slot-scope="scope">
          <el-checkbox v-model="scope.row.required"></el-checkbox>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="200">
        <template slot-scope="scope">
          <el-input v-model="scope.row.description" placeholder="描述" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template slot-scope="scope">
          <el-button
            type="text"
            icon="el-icon-delete"
            @click="$emit('remove', scope.$index)"
            class="delete-btn"
          />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
export default {
  name: 'ParamTable',
  props: {
    params: {
      type: Array,
      required: true
    },
    title: {
      type: String,
      required: true
    },
    showType: {
      type: Boolean,
      default: false
    }
  },
  methods: {
    handleFileUpload(param, row) {
      const file = param.file
      const reader = new FileReader()
      
      reader.onload = (e) => {
        // 将文件读取为 Base64 字符串
        // 格式通常为: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...
        // 我们将其直接存入 row.value，并附带文件名信息方便后端解析
        const base64Data = e.target.result
        const fileInfo = {
          filename: file.name,
          data: base64Data
        }
        // 为了方便后端统一处理，我们存为一个 JSON 字符串，但以 base64: 开头作为标识
        row.value = `base64:${JSON.stringify(fileInfo)}`
        this.$message.success(`文件 ${file.name} 已读取`)
      }
      
      reader.onerror = () => {
        this.$message.error('文件读取失败')
      }
      
      reader.readAsDataURL(file)
    },
    // 获取显示用的值（如果是 base64 标识，则只显示文件名）
    getDisplayValue(value) {
      if (typeof value === 'string' && value.startsWith('base64:')) {
        try {
          const fileInfo = JSON.parse(value.substring(7))
          return `[文件] ${fileInfo.filename}`
        } catch (e) {
          return value
        }
      }
      // 如果是对象或数组，转为字符串显示
      if (value !== null && typeof value === 'object') {
        return JSON.stringify(value)
      }
      return value
    }
  }
}
</script>

<style scoped>
.param-table {
  padding: 20px;
}

.add-btn {
  margin-bottom: 15px;
}

.delete-btn {
  color: #f56c6c;
}

.delete-btn:hover {
  color: #ff4949;
}

.file-upload-wrapper {
  display: flex;
  align-items: center;
}

.file-path-input :deep(.el-input-group__append) {
  padding: 0;
}

.file-path-input :deep(.el-upload) {
  display: block;
}

.file-path-input :deep(.el-button) {
  border: none;
  margin: 0;
  border-radius: 0;
  padding: 10px 15px;
}
</style> 