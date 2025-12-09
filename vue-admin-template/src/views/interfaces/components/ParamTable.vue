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
          <el-input v-model="scope.row.value" placeholder="参数值" size="small" />
        </template>
      </el-table-column>
      <el-table-column v-if="showType" label="类型" width="120">
        <template slot-scope="scope">
          <el-select v-model="scope.row.type" size="small" style="width: 100%">
            <el-option label="String" value="string" />
            <el-option label="Number" value="number" />
            <el-option label="Boolean" value="boolean" />
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
</style> 