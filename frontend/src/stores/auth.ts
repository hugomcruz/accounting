import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

// Refresh the token when this many milliseconds remain before expiry.
const REFRESH_THRESHOLD_MS = 5 * 60 * 1000   // 5 minutes

// How often the session-check timer fires.
const CHECK_INTERVAL_MS = 30 * 1000           // 30 seconds

// Show the idle warning this many milliseconds before forced logout.
const WARN_BEFORE_LOGOUT_MS = 2 * 60 * 1000  // 2 minutes

// DOM events that count as user activity.
const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  'mousedown', 'keydown', 'scroll', 'touchstart', 'click',
]

/** Extract the expiry timestamp (ms) from a JWT without a library. */
function parseTokenExpiry(jwtToken: string): number | null {
  try {
    const payload = JSON.parse(atob(jwtToken.split('.')[1]))
    return payload.exp ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))
  const user = ref<User | null>(
    localStorage.getItem('auth_user')
      ? JSON.parse(localStorage.getItem('auth_user')!)
      : null
  )

  // Session state
  const tokenExpiry    = ref<number | null>(token.value ? parseTokenExpiry(token.value) : null)
  const idleTimeoutMs  = ref<number>(30 * 60 * 1000)   // updated from server on login
  const lastActivity   = ref<number>(Date.now())
  const showIdleWarning = ref(false)

  // Internal handles
  let _checkTimer: ReturnType<typeof setInterval> | null = null
  let _refreshing = false

  // ── Computed ──────────────────────────────────────────────────────────
  const isAuthenticated = computed(() => !!token.value)
  const role            = computed(() => user.value?.role?.toLowerCase() ?? '')
  const isAdmin         = computed(() => role.value === 'admin')
  const isAccountant    = computed(() => role.value === 'accounting')
  const isUser          = computed(() => role.value === 'user')
  const isStaff         = computed(() => ['admin', 'accounting', 'finance'].includes(role.value))

  // ── Activity tracking ─────────────────────────────────────────────────
  function _recordActivity() {
    lastActivity.value = Date.now()
    if (showIdleWarning.value) showIdleWarning.value = false
  }

  // ── Token refresh ─────────────────────────────────────────────────────
  async function _refresh() {
    if (_refreshing) return
    _refreshing = true
    try {
      const response = await api.post('/auth/refresh')
      const data = response.data
      _applyToken(data.access_token, data.user, data.expires_in)
    } catch {
      // Token is no longer valid – log out.
      logout()
    } finally {
      _refreshing = false
    }
  }

  function _applyToken(accessToken: string, userData: User, expiresIn?: number) {
    token.value = accessToken
    user.value = userData
    tokenExpiry.value = parseTokenExpiry(accessToken)
    if (expiresIn) idleTimeoutMs.value = expiresIn * 1000
    localStorage.setItem('auth_token', accessToken)
    localStorage.setItem('auth_user', JSON.stringify(userData))
  }

  // ── Periodic session check ────────────────────────────────────────────
  function _checkSession() {
    if (!token.value) return

    const now        = Date.now()
    const idleMs     = now - lastActivity.value
    const warnThreshold = idleTimeoutMs.value - WARN_BEFORE_LOGOUT_MS

    // Force-logout on idle timeout
    if (idleMs >= idleTimeoutMs.value) {
      logout()
      return
    }

    // Show idle warning
    showIdleWarning.value = idleMs >= warnThreshold

    // Proactively refresh if the token is about to expire and user is active
    if (tokenExpiry.value) {
      const timeUntilExpiry = tokenExpiry.value - now
      const userIsActive = idleMs < REFRESH_THRESHOLD_MS
      if (timeUntilExpiry > 0 && timeUntilExpiry < REFRESH_THRESHOLD_MS && userIsActive) {
        _refresh()
      }
    }
  }

  // ── Public API ────────────────────────────────────────────────────────
  async function login(username: string, password: string) {
    const response = await api.post('/auth/login', { username, password })
    const data = response.data
    _applyToken(data.access_token, data.user, data.expires_in)
    lastActivity.value = Date.now()
  }

  function logout() {
    teardownSession()
    token.value = null
    user.value = null
    tokenExpiry.value = null
    showIdleWarning.value = false
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }

  /** Call once after a successful login (or on app mount when already logged in). */
  function setupSession() {
    if (_checkTimer) return  // already running

    if (token.value) {
      tokenExpiry.value = parseTokenExpiry(token.value)
    }
    lastActivity.value = Date.now()

    ACTIVITY_EVENTS.forEach(evt =>
      window.addEventListener(evt, _recordActivity, { passive: true })
    )

    _checkTimer = setInterval(_checkSession, CHECK_INTERVAL_MS)
  }

  /** Call on logout or app unmount to clean up listeners and the timer. */
  function teardownSession() {
    if (_checkTimer) {
      clearInterval(_checkTimer)
      _checkTimer = null
    }
    ACTIVITY_EVENTS.forEach(evt =>
      window.removeEventListener(evt, _recordActivity)
    )
  }

  /** Dismiss the idle warning and record activity (used by the "Stay logged in" button). */
  function stayActive() {
    _recordActivity()
    _refresh()
  }

  return {
    token, user,
    isAuthenticated, role, isAdmin, isAccountant, isUser, isStaff,
    showIdleWarning, idleTimeoutMs,
    login, logout, setupSession, teardownSession, stayActive,
  }
})
