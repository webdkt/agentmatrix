/**
 * 容器路径 → 宿主机路径转换工具
 * 复刻后端 paths.py container_path_to_host 的映射规则
 */

/**
 * 判断 inline code 文本是否像容器内路径
 */
export function isContainerPath(text) {
  if (!text || typeof text !== 'string') return false
  const t = text.trim()
  // ~/xxx, ~, /data/agents/..., /home/... (absolute container paths)
  return t === '~' || t.startsWith('~/') || t.startsWith('/data/agents/')
}

/**
 * 容器路径 → 宿主机路径
 *
 * 映射规则（与后端 paths.py 一致）：
 *   /data/agents/{agent}/home/current_task/xxx → ~/current_task/xxx → work_files/{taskId}/xxx
 *   ~/current_task 或 ~/current_task/xxx        → work_files/{taskId}/xxx
 *   ~ 或 ~/xxx                                   → home/xxx
 *   /data/agents/{agent}/xxx                     → agent_files/{agent}/xxx
 *   其他                                          → null（不可映射）
 *
 * @param {string} containerPath 容器内路径
 * @param {string} agentName Agent 名称
 * @param {string} taskId 任务 ID
 * @param {string} worldPath matrix_world_path
 * @returns {string|null} 宿主机绝对路径，或 null
 */
export function containerPathToHost(containerPath, agentName, taskId, worldPath) {
  let p = containerPath.trim()

  // 1. /data/agents/{agent}/home/current_task/xxx → ~/current_task/xxx
  const absCurrentTask = `/data/agents/${agentName}/home/current_task/`
  if (p.startsWith(absCurrentTask)) {
    p = p.replace(absCurrentTask, '~/current_task/')
  }

  // 2. ~/current_task → work_files/{taskId}
  if (p === '~/current_task' || p.startsWith('~/current_task/')) {
    const relative = p.slice('~/current_task/'.length).replace(/^\//, '')
    const base = `${worldPath}/workspace/agent_files/${agentName}/work_files/${taskId}`
    return relative ? `${base}/${relative}` : base
  }

  // 3. ~/xxx → home/
  if (p === '~' || p.startsWith('~/')) {
    const relative = p.startsWith('~/') ? p.slice(2).replace(/^\//, '') : ''
    const base = `${worldPath}/workspace/agent_files/${agentName}/home`
    return relative ? `${base}/${relative}` : base
  }

  // 4. /data/agents/{agent}/xxx → agent_files/{agent}/xxx
  const containerBase = `/data/agents/${agentName}/`
  if (p.startsWith(containerBase)) {
    const relative = p.slice(containerBase.length).replace(/^\//, '')
    const base = `${worldPath}/workspace/agent_files/${agentName}`
    return relative ? `${base}/${relative}` : base
  }

  // 5. 不可映射
  return null
}
