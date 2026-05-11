<template>
  <span>
    <el-popover
      v-if="isJson"
      placement="right-start"
      trigger="hover"
      :append-to-body="true"
      popper-class="ellipsis-json-popover"
      :width="popoverWidth"
    >
      <pre>{{ formattedJson }}</pre>
      <span slot="reference" class="ellipsis-ref">
        <el-tag v-if="showJsonTag" size="mini" type="info" class="json-tag">JSON</el-tag>
        <span class="ellipsis-text">{{ displayText }}</span>
      </span>
    </el-popover>
    <el-tooltip
      v-else
      effect="dark"
      placement="top"
      :open-delay="200"
      :append-to-body="true"
      popper-class="ellipsis-tooltip"
    >
      <div slot="content" class="ellipsis-tooltip-content">{{ displayText }}</div>
      <span class="ellipsis-text">{{ displayText }}</span>
    </el-tooltip>
  </span>
</template>

<script>
export default {
  name: 'EllipsisCell',
  props: {
    value: {
      type: [String, Object, Array],
      default: ''
    },
    detectJson: {
      type: Boolean,
      default: true
    },
    showJsonTag: {
      type: Boolean,
      default: true
    },
    popoverWidth: {
      type: Number,
      default: 500
    }
  },
  computed: {
    isJson() {
      if (!this.detectJson) return false
      if (typeof this.value === 'object' && this.value !== null) return true
      if (typeof this.value !== 'string') return false
      const v = this.value.trim()
      if (!v) return false
      if ((v.startsWith('{') && v.endsWith('}')) || (v.startsWith('[') && v.endsWith(']'))) {
        try {
          JSON.parse(v)
          return true
        } catch (e) {
          return false
        }
      }
      return false
    },
    displayText() {
      if (typeof this.value === 'string') return this.value
      try {
        return JSON.stringify(this.value)
      } catch (e) {
        return String(this.value)
      }
    },
    formattedJson() {
      try {
        if (typeof this.value === 'string') {
          return JSON.stringify(JSON.parse(this.value), null, 2)
        }
        return JSON.stringify(this.value, null, 2)
      } catch (e) {
        return this.displayText
      }
    }
  }
}
</script>

<style scoped>
.ellipsis-ref {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
}
.json-tag {
  margin-right: 5px;
}
.ellipsis-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  max-width: 100%;
}
</style>

<style>
.ellipsis-json-popover {
  max-width: 700px;
}
.ellipsis-json-popover pre {
  max-height: 400px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.ellipsis-tooltip {
  max-width: 700px;
}
.ellipsis-tooltip-content {
  max-width: 700px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
