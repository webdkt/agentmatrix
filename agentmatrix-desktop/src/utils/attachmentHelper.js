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
    'jpg': 'file-image', 'jpeg': 'file-image', 'png': 'file-image',
    'gif': 'file-image', 'svg': 'file-image', 'webp': 'file-image',
    'pdf': 'file-text', 'doc': 'file-text', 'docx': 'file-text',
    'txt': 'file-text', 'md': 'file-text',
    'xls': 'file-spreadsheet', 'xlsx': 'file-spreadsheet',
    'csv': 'file-spreadsheet',
    'js': 'file-code', 'ts': 'file-code', 'py': 'file-code',
    'java': 'file-code', 'cpp': 'file-code', 'html': 'file-code',
    'css': 'file-code', 'json': 'file-code',
    'zip': 'file-zip', 'rar': 'file-zip', '7z': 'file-zip',
    'mp4': 'file-video', 'avi': 'file-video', 'mov': 'file-video',
    'mp3': 'file-music', 'wav': 'file-music', 'flac': 'file-music'
  }

  return icons[ext] || 'file'
}
