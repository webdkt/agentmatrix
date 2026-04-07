import { reactive } from 'vue'

const pendingEmails = reactive({})

// Store for resolved new emails (session_id → email)
// Used to inject real email into EmailList without an API call
const resolvedNewEmails = reactive({})

let counter = 0

export function addPendingEmail(sessionId, emailData, userName = 'User') {
  const id = `placeholder-${Date.now()}-${++counter}`
  const placeholder = {
    id,
    sender: userName,
    recipient: emailData.recipient,
    subject: emailData.subject || '',
    body: emailData.body,
    timestamp: new Date().toISOString(),
    is_from_user: true,
    in_reply_to: emailData.in_reply_to || null,
    task_id: sessionId,
    attachments: emailData._localAttachments || [],
    _isPlaceholder: true,
  }

  pendingEmails[id] = { placeholder, sessionId }
  return placeholder
}

export function removePendingEmail(placeholderId) {
  delete pendingEmails[placeholderId]
}

export function getPlaceholdersForSession(sessionId) {
  return Object.values(pendingEmails)
    .filter(entry => entry.sessionId === sessionId)
    .map(entry => entry.placeholder)
}

// Store a resolved email for a new session (to avoid loadEmails API call)
export function setResolvedEmailForSession(sessionId, email) {
  resolvedNewEmails[sessionId] = email
}

// Get and consume a resolved email for a session (one-time use)
export function consumeResolvedEmail(sessionId) {
  const email = resolvedNewEmails[sessionId]
  if (email) {
    delete resolvedNewEmails[sessionId]
  }
  return email || null
}
