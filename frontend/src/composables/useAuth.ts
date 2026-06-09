import { computed, ref } from 'vue'
import { getCurrentUser, login, logout } from '../api/auth'
import { clearAuthToken, getAuthToken, setAuthToken } from '../lib/http'
import type { AuthUser } from '../types'

const user = ref<AuthUser | null>(null)
const isLoading = ref(false)
const isReady = ref(false)
const error = ref('')

async function initializeAuth() {
  if (isReady.value) return user.value
  isLoading.value = true
  error.value = ''
  try {
    user.value = await getCurrentUser()
  } catch (err) {
    user.value = null
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoading.value = false
    isReady.value = true
  }
  return user.value
}

async function signIn(username: string, password: string) {
  isLoading.value = true
  error.value = ''
  try {
    const result = await login(username, password)
    setAuthToken(result.token)
    user.value = result.user
    isReady.value = true
    return result.user
  } catch (err) {
    clearAuthToken()
    user.value = null
    error.value = err instanceof Error ? err.message : String(err)
    throw err
  } finally {
    isLoading.value = false
  }
}

async function signOut() {
  isLoading.value = true
  error.value = ''
  try {
    if (getAuthToken()) await logout()
  } catch {
    // Local logout should still complete if the backend token is already invalid.
  } finally {
    clearAuthToken()
    user.value = null
    isReady.value = true
    isLoading.value = false
  }
}

export function useAuth() {
  return {
    user,
    isLoading,
    isReady,
    error,
    isAuthenticated: computed(() => Boolean(user.value)),
    initializeAuth,
    signIn,
    signOut,
  }
}
