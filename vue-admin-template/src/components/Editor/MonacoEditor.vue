<template>
  <div ref="editorContainer" class="monaco-editor-container">
    <div v-if="loading" class="monaco-loading">
      <i class="el-icon-loading"></i> 编辑器加载中...
    </div>
  </div>
</template>

<script>
export default {
  name: 'MonacoEditor',
  props: {
    value: {
      type: String,
      default: ''
    },
    language: {
      type: String,
      default: 'javascript'
    },
    options: {
      type: Object,
      default: () => ({})
    }
  },
  data() {
    return {
      editor: null,
      monaco: null,
      loading: true
    }
  },
  watch: {
    value(newValue) {
      if (this.editor && newValue !== this.editor.getValue()) {
        this.editor.setValue(newValue)
      }
    },
    language(newValue) {
      if (this.editor) {
        this.monaco.editor.setModelLanguage(this.editor.getModel(), newValue)
      }
    }
  },
  mounted() {
    this.initMonaco()
  },
  beforeDestroy() {
    if (this.editor) {
      this.editor.dispose()
    }
  },
  methods: {
    async initMonaco() {
      // Dynamically import only the required parts of monaco-editor
      const monaco = await import('monaco-editor/esm/vs/editor/editor.api')
      this.monaco = monaco

      const defaultOptions = {
        value: this.value,
        language: this.language,
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: {
          enabled: false
        },
        scrollBeyondLastLine: false,
        fontSize: 14,
        tabSize: 2,
        wordWrap: 'on'
      }

      this.editor = monaco.editor.create(this.$refs.editorContainer, {
        ...defaultOptions,
        ...this.options
      })

      this.loading = false

      this.editor.onDidChangeModelContent(() => {
        const value = this.editor.getValue()
        this.$emit('input', value)
        this.$emit('change', value)
      })
    }
  }
}
</script>

<style scoped>
.monaco-editor-container {
  width: 100%;
  height: 100%;
  position: relative;
}
.monaco-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1e1e1e;
  color: #ccc;
  font-size: 14px;
}
</style> 