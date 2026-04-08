import { ref } from 'vue'

/**
 * 邮件附件处理 Composable
 * 处理文件选择、拖拽上传、附件管理
 */
export function useEmailAttachments() {
  const attachments = ref([])
  const isDragging = ref(false)

  /**
   * 处理文件选择（通过 input 元素）
   * @param {Event} event - 文件选择事件
   */
  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files)
    if (files.length > 0) {
      attachments.value.push(...files)
      console.log(`📎 Added ${files.length} file(s) via select`)
    }
  }

  /**
   * 处理拖拽进入
   * @param {Event} event - 拖拽事件
   */
  const handleDragEnter = (event) => {
    event.preventDefault()
    isDragging.value = true
  }

  /**
   * 处理拖拽离开
   * @param {Event} event - 拖拽事件
   */
  const handleDragLeave = (event) => {
    event.preventDefault()
    isDragging.value = false
  }

  /**
   * 处理拖拽经过
   * @param {Event} event - 拖拽事件
   */
  const handleDragOver = (event) => {
    event.preventDefault()
  }

  /**
   * 处理文件放下
   * @param {Event} event - 拖拽事件
   */
  const handleFileDrop = (event) => {
    event.preventDefault()
    isDragging.value = false

    const files = Array.from(event.dataTransfer.files)
    if (files.length > 0) {
      attachments.value.push(...files)
      console.log(`📎 Added ${files.length} file(s) via drop`)
    }
  }

  /**
   * 移除附件
   * @param {number} index - 附件索引
   */
  const removeAttachment = (index) => {
    const removed = attachments.value.splice(index, 1)
    console.log(`🗑️ Removed attachment: ${removed[0]?.name}`)
  }

  /**
   * 清空所有附件
   */
  const clearAttachments = () => {
    attachments.value = []
  }

  /**
   * 格式化文件大小
   * @param {number} bytes - 文件字节数
   * @returns {string} 格式化后的文件大小
   */
  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B'

    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  /**
   * 获取附件总信息
   * @returns {object} { count, totalSize }
   */
  const getAttachmentsInfo = () => {
    const count = attachments.value.length
    const totalSize = attachments.value.reduce((sum, file) => sum + file.size, 0)
    return { count, totalSize }
  }

  return {
    attachments,
    isDragging,
    handleFileSelect,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleFileDrop,
    removeAttachment,
    clearAttachments,
    formatFileSize,
    getAttachmentsInfo
  }
}
