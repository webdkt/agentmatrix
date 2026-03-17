/**
 * 附件处理工具函数
 */

import { invoke } from '@tauri-apps/api/core'

/**
 * 打开附件（使用系统默认应用）
 * @param {string} recipient - 收件人名称（例如：DKT）
 * @param {string} taskId - 任务 ID
 * @param {string} filename - 文件名
 */
export async function openAttachment(recipient, taskId, filename) {
  // 获取配置
  const config = await invoke('get_config')

  // 构建文件路径
  const path = `${config.matrix_world_path}/workspace/agent_files/${recipient}/work_files/${taskId}/attachments/${filename}`

  // 使用自定义命令打开文件（绕过 opener 插件限制）
  await invoke('open_attachment_path', { path })

  console.log('✅ 已打开附件:', path)
}

/**
 * 获取附件图标（根据文件类型）
 * @param {string} filename - 文件名
 * @returns {string} 图标类名
 */
export function getAttachmentIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase()

  const icons = {
    'jpg': 'ti-file-image', 'jpeg': 'ti-file-image', 'png': 'ti-file-image',
    'gif': 'ti-file-image', 'svg': 'ti-file-image', 'webp': 'ti-file-image',
    'pdf': 'ti-file-text', 'doc': 'ti-file-text', 'docx': 'ti-file-text',
    'txt': 'ti-file-text', 'md': 'ti-file-text',
    'xls': 'ti-file-spreadsheet', 'xlsx': 'ti-file-spreadsheet',
    'csv': 'ti-file-spreadsheet',
    'js': 'ti-file-code', 'ts': 'ti-file-code', 'py': 'ti-file-code',
    'java': 'ti-file-code', 'cpp': 'ti-file-code', 'html': 'ti-file-code',
    'css': 'ti-file-code', 'json': 'ti-file-code',
    'zip': 'ti-file-zip', 'rar': 'ti-file-zip', '7z': 'ti-file-zip',
    'mp4': 'ti-file-video', 'avi': 'ti-file-video', 'mov': 'ti-file-video',
    'mp3': 'ti-file-music', 'wav': 'ti-file-music', 'flac': 'ti-file-music'
  }

  return icons[ext] || 'ti-file'
}
