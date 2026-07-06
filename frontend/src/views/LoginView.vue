<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppAlert from '../components/ui/AppAlert.vue'
import FieldError from '../components/ui/FieldError.vue'
import { useAuth } from '../composables/useAuth'
import { useI18n } from '../composables/useI18n'
import { useTheme } from '../composables/useTheme'
import { required, type ValidationErrors } from '../lib/validation'

const route = useRoute()
const router = useRouter()
const { error: authError, isLoading, signIn } = useAuth()
const { theme } = useTheme()
const { t } = useI18n()

const form = ref({
  username: 'admin',
  password: 'admin',
})
const errors = ref<ValidationErrors>({})
const message = ref('')

const redirectTo = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/dashboard'
})

function validateForm() {
  const nextErrors: ValidationErrors = {}
  const usernameError = required(form.value.username, t('login.username'))
  const passwordError = required(form.value.password, t('login.password'))

  if (usernameError) nextErrors.username = usernameError
  if (passwordError) nextErrors.password = passwordError

  errors.value = nextErrors
  return Object.keys(nextErrors).length === 0
}

async function submitLogin() {
  message.value = ''
  if (!validateForm()) return

  try {
    await signIn(form.value.username, form.value.password)
    message.value = t('login.successMessage')
    await router.replace(redirectTo.value)
  } catch {
    // useAuth exposes the backend error through authError.
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel surface">
      <div class="login-brand">
        <span class="brand-mark">
          <img
            :src="theme === 'pink' ? '/brand/logo-pink.png' : '/brand/logo-blue.png'"
            alt="Digital Forensics"
          />
        </span>
        <div>
          <strong>{{ t('app.name') }}</strong>
          <p>{{ t('app.subtitle') }}</p>
        </div>
      </div>

      <div class="login-copy">
        <h1>{{ t('login.title') }}</h1>
        <p>{{ t('login.description') }}</p>
      </div>

      <form class="login-form" @submit.prevent="submitLogin">
        <label class="field">
          <span>{{ t('login.username') }}</span>
          <input v-model="form.username" autocomplete="username" placeholder="admin" />
          <FieldError :message="errors.username" />
        </label>

        <label class="field">
          <span>{{ t('login.password') }}</span>
          <input v-model="form.password" autocomplete="current-password" placeholder="admin" type="password" />
          <FieldError :message="errors.password" />
        </label>

        <button class="primary-button" :disabled="isLoading" type="submit">
          {{ isLoading ? t('login.signingIn') : t('login.signIn') }}
        </button>

        <AppAlert v-if="message" tone="success" :title="t('common.operationSuccess')" :message="message" />
        <AppAlert v-if="authError" tone="error" :title="t('login.failedTitle')" :message="authError" />
      </form>

      <div class="login-note">
        <span>{{ t('login.defaultAccount') }}</span>
        <span>{{ t('login.productionHint') }}</span>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(90deg, rgba(40, 72, 102, 0.025) 1px, transparent 1px),
    linear-gradient(180deg, rgba(40, 72, 102, 0.025) 1px, transparent 1px),
    radial-gradient(circle at 18% 20%, rgba(15, 118, 110, 0.12), transparent 30%),
    linear-gradient(135deg, oklch(0.992 0.004 235), oklch(0.958 0.014 206));
  background-size: 32px 32px, 32px 32px, auto, auto;
}

.login-panel {
  width: min(100%, 480px);
  display: grid;
  gap: 24px;
  padding: 28px;
  border-radius: var(--radius);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  overflow: hidden;
  padding: 3px;
  border-radius: var(--radius);
  background: #fff;
  border: 1px solid color-mix(in oklch, var(--primary) 18%, transparent);
  box-shadow: 0 12px 28px color-mix(in oklch, var(--primary) 24%, transparent);
}

.brand-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.login-brand strong {
  display: block;
  font-size: 18px;
}

.login-brand p,
.login-copy p,
.login-note {
  margin: 0;
  color: #64748b;
}

.login-copy h1 {
  margin: 0 0 8px;
  font-size: 30px;
  letter-spacing: 0;
}

.login-copy p {
  line-height: 1.65;
}

.login-form {
  display: grid;
  gap: 16px;
}

.field {
  display: grid;
  gap: 8px;
}

.field span {
  color: var(--muted-foreground);
  font-size: 13px;
  font-weight: 800;
}

.field input {
  width: 100%;
  min-height: 46px;
  padding: 12px 14px;
  border: 1px solid rgba(190, 202, 216, 0.82);
  border-radius: var(--radius);
}

.primary-button {
  border: none;
  border-radius: var(--radius);
  padding: 12px 16px;
  color: white;
  font-weight: 900;
  cursor: pointer;
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.64;
}

.login-note {
  display: grid;
  gap: 6px;
  padding-top: 16px;
  border-top: 1px solid rgba(226, 232, 240, 0.86);
  font-size: 13px;
}
</style>
