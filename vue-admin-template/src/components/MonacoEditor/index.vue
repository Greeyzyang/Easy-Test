<template>
  <div ref="editorContainer" class="monaco-editor-container"></div>
</template>

<script>
import * as monaco from 'monaco-editor'

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
      editor: null
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
        monaco.editor.setModelLanguage(this.editor.getModel(), newValue)
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
    initMonaco() {
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
}
</style> 