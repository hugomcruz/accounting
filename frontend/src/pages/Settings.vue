<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery, useMutation } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Save } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { settingsApi } from '@/services/queries'
import { setLocale } from '@/i18n'

const { t, locale } = useI18n()
const activeSection = ref('general')
const saveSuccess = ref(false)

const form = ref({
  nif_api_enabled: false,
  company_name: '',
  company_nif: '',
})

const { data: settings, isLoading } = useQuery({
  queryKey: ['settings'],
  queryFn: async () => {
    const res = await settingsApi.get()
    return res.data
  },
})

watch(settings, (s) => {
  if (s) {
    form.value = {
      nif_api_enabled: s.nif_api_enabled ?? false,
      company_name: s.company_name ?? '',
      company_nif: s.company_nif ?? '',
    }
  }
})

const updateMutation = useMutation({
  mutationFn: (data: typeof form.value) => settingsApi.update(data),
  onSuccess: () => {
    saveSuccess.value = true
    setTimeout(() => (saveSuccess.value = false), 3000)
  },
})

const navItems = [
  { key: 'general' },
  { key: 'nif_api' },
  { key: 'language' },
]

const navLabel = (key: string) => {
  if (key === 'general') return t('settings.generalNav')
  if (key === 'nif_api') return t('settings.nifApiNav')
  return t('settings.language')
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('settings.title') }}</h1>
      <p class="mt-1 text-gray-500">{{ t('settings.subtitle') }}</p>
    </div>

    <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>

    <div v-else class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <!-- Side Nav -->
      <div class="md:col-span-1">
        <nav class="space-y-1">
          <button
            v-for="item in navItems"
            :key="item.key"
            class="w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="activeSection === item.key
              ? 'bg-blue-50 text-blue-700'
              : 'text-gray-600 hover:bg-gray-100'"
            @click="activeSection = item.key"
          >
            {{ navLabel(item.key) }}
          </button>
        </nav>
      </div>

      <!-- Content -->
      <div class="md:col-span-3 space-y-4">
        <template v-if="activeSection === 'general'">
          <Card>
            <CardHeader><CardTitle>{{ t('settings.generalCard') }}</CardTitle></CardHeader>
            <CardContent>
              <div class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('settings.companyName') }}</label>
                  <input v-model="form.company_name" type="text"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('settings.companyNif') }}</label>
                  <input v-model="form.company_nif" type="text"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </template>

        <template v-if="activeSection === 'nif_api'">
          <Card>
            <CardHeader><CardTitle>{{ t('settings.nifApiCard') }}</CardTitle></CardHeader>
            <CardContent>
              <div class="space-y-4">
                <div class="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                  <div>
                    <p class="font-medium text-gray-900">{{ t('settings.nifApiToggle') }}</p>
                    <p class="text-sm text-gray-500 mt-0.5">{{ t('settings.nifApiDesc') }}</p>
                  </div>
                  <button
                    class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none"
                    :class="form.nif_api_enabled ? 'bg-blue-600' : 'bg-gray-200'"
                    @click="form.nif_api_enabled = !form.nif_api_enabled"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
                      :class="form.nif_api_enabled ? 'translate-x-6' : 'translate-x-1'"
                    ></span>
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        </template>

        <template v-if="activeSection === 'language'">
          <Card>
            <CardHeader><CardTitle>{{ t('settings.language') }}</CardTitle></CardHeader>
            <CardContent>
              <div>
                <p class="text-sm font-medium text-gray-900 mb-1">{{ t('settings.languageLabel') }}</p>
                <p class="text-sm text-gray-500 mb-4">{{ t('settings.languageDesc') }}</p>
                <div class="flex gap-3">
                  <button
                    class="px-6 py-2 rounded-lg border-2 font-medium text-sm transition-colors"
                    :class="locale === 'en' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
                    @click="setLocale('en')"
                  >
                    🇬🇧 English
                  </button>
                  <button
                    class="px-6 py-2 rounded-lg border-2 font-medium text-sm transition-colors"
                    :class="locale === 'pt' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
                    @click="setLocale('pt')"
                  >
                    🇵🇹 Português
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        </template>

        <div class="flex items-center gap-4">
          <button
            :disabled="updateMutation.isPending.value"
            class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="updateMutation.mutate(form)"
          >
            <Save class="h-4 w-4" />
            {{ updateMutation.isPending.value ? t('common.saving') : t('settings.saveSettings') }}
          </button>
          <p v-if="saveSuccess" class="text-green-600 text-sm">{{ t('settings.saveSuccess') }}</p>
          <p v-if="updateMutation.isError.value" class="text-red-600 text-sm">{{ t('settings.saveError') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
