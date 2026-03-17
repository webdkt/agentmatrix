import { ref, onMounted, onUnmounted } from 'vue'

/**
 * WebSocket 客户端
 * 用于与后端建立实时通信连接
 */
class WebSocketClient {
  constructor(url) {
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000
    this.eventHandlers = {}
  }

  connect() {
    try {
      console.log('🔌 Connecting to WebSocket:', this.url)
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected')
        this.reconnectAttempts = 0
        this.trigger('open')

        // 重连后立即请求系统状态
        this.requestSystemStatus()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('📨 WebSocket message received:', data)
          this.trigger('message', data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onclose = () => {
        console.log('❌ WebSocket disconnected')
        this.trigger('close')
        this.attemptReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('⚠️ WebSocket error:', error)
        this.trigger('error', error)
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      setTimeout(() => {
        this.connect()
      }, this.reconnectDelay)
    } else {
      console.error('Max reconnect attempts reached')
      this.trigger('maxReconnectAttemptsReached')
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
      console.log('📤 WebSocket message sent:', data)
    } else {
      console.error('WebSocket is not connected')
    }
  }

  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = []
    }
    this.eventHandlers[event].push(handler)
  }

  off(event, handler) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event] = this.eventHandlers[event].filter(h => h !== handler)
    }
  }

  trigger(event, data) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach(handler => handler(data))
    }
  }

  requestSystemStatus() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.send({
        type: 'REQUEST_SYSTEM_STATUS'
      })
      console.log('📊 Requested system status')
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
    }
  }
}

/**
 * WebSocket Composable
 * 提供 WebSocket 连接和事件处理
 */
export function useWebSocket() {
  const isConnected = ref(false)
  const wsClient = ref(null)
  const messageHandlers = ref([])

  // 初始化 WebSocket 连接
  const connect = () => {
    // 连接到后端 WebSocket (端口 8000)
    // 在开发环境中，我们需要连接到 Python 后端而不是 Vite 开发服务器
    const wsUrl = 'ws://localhost:8000/ws'

    console.log('🔌 Connecting to WebSocket:', wsUrl)

    wsClient.value = new WebSocketClient(wsUrl)
    wsClient.value.connect()

    // 监听连接状态
    wsClient.value.on('open', () => {
      isConnected.value = true
    })

    wsClient.value.on('close', () => {
      isConnected.value = false
    })

    wsClient.value.on('message', (data) => {
      // 分发消息给所有注册的处理器
      messageHandlers.value.forEach(handler => handler(data))
    })
  }

  // 注册消息处理器
  const onMessage = (handler) => {
    messageHandlers.value.push(handler)

    // 返回清理函数
    return () => {
      messageHandlers.value = messageHandlers.value.filter(h => h !== handler)
    }
  }

  // 发送消息
  const send = (data) => {
    if (wsClient.value) {
      wsClient.value.send(data)
    }
  }

  // 断开连接
  const disconnect = () => {
    if (wsClient.value) {
      wsClient.value.disconnect()
      wsClient.value = null
      isConnected.value = false
    }
  }

  // 组件卸载时断开连接
  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    connect,
    send,
    disconnect,
    onMessage
  }
}
