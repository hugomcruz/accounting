<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Edit2, Save, X } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { companiesApi } from '@/services/queries'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const id = Number(route.params.id)
const isEditing = ref(false)

const formData = ref({
  name: '',
  address: '',
  postal_code: '',
  city: '',
  country: 'PT',
  email: '',
  phone: '',
  is_customer: false,
  is_supplier: false,
})

const { data: company, isLoading } = useQuery({
  queryKey: ['company', id],
  queryFn: async () => {
    const response = await companiesApi.getById(id)
    return response.data
  },
  enabled: !!id,
})

watch(company, (c) => {
  if (c) {
    formData.value = {
      name: c.name || '',
      address: c.address || '',
      postal_code: c.postal_code || '',
      city: c.city || '',
      country: c.country || 'PT',
      email: c.email || '',
      phone: c.phone || '',
      is_customer: c.is_customer || false,
      is_supplier: c.is_supplier || false,
    }
  }
})

const updateMutation = useMutation({
  mutationFn: (data: typeof formData.value) => companiesApi.update(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['company', id] })
    queryClient.invalidateQueries({ queryKey: ['companies'] })
    isEditing.value = false
  },
})

function handleCancel() {
  if (company.value) {
    formData.value = {
      name: company.value.name || '',
      address: company.value.address || '',
      postal_code: company.value.postal_code || '',
      city: company.value.city || '',
      country: company.value.country || 'PT',
      email: company.value.email || '',
      phone: company.value.phone || '',
      is_customer: company.value.is_customer || false,
      is_supplier: company.value.is_supplier || false,
    }
  }
  isEditing.value = false
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <button class="p-2 hover:bg-gray-100 rounded-lg" @click="router.push('/companies')">
          <ArrowLeft class="h-5 w-5" />
        </button>
        <div>
          <h1 class="text-3xl font-bold text-gray-900">{{ t('companies.detailTitle') }}</h1>
          <p v-if="company" class="mt-1 text-gray-500">{{ t('companies.nif') }}: {{ company.nif }}</p>
        </div>
      </div>
      <div v-if="company">
        <button
          v-if="!isEditing"
          class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          @click="isEditing = true"
        >
          <Edit2 class="h-4 w-4" />
          {{ t('common.edit') }}
        </button>
        <div v-else class="flex gap-2">
          <button
            class="flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
            @click="handleCancel"
          >
            <X class="h-4 w-4" />
            {{ t('common.cancel') }}
          </button>
          <button
            :disabled="updateMutation.isPending.value"
            class="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            @click="updateMutation.mutate(formData)"
          >
            <Save class="h-4 w-4" />
            {{ updateMutation.isPending.value ? t('common.saving') : t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>
    <div v-else-if="!company" class="text-center py-8 text-gray-500">{{ t('companies.notFound') }}</div>

    <template v-else>
      <Card>
        <CardHeader><CardTitle>{{ t('companies.companyInfo') }}</CardTitle></CardHeader>
        <CardContent>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.nif') }}</label>
              <input type="text" :value="company.nif" disabled
                class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.nameRequired') }}</label>
              <input v-model="formData.name" type="text" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div class="md:col-span-2">
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.address') }}</label>
              <input v-model="formData.address" type="text" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.postalCode') }}</label>
              <input v-model="formData.postal_code" type="text" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.city') }}</label>
              <input v-model="formData.city" type="text" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('companies.country') }}</label>
              <input v-model="formData.country" type="text" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('common.email') }}</label>
              <input v-model="formData.email" type="email" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('common.phone') }}</label>
              <input v-model="formData.phone" type="tel" :disabled="!isEditing"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-700" />
            </div>
            <div class="md:col-span-2">
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('companies.companyType') }}</label>
              <div class="flex gap-4">
                <label class="flex items-center gap-2">
                  <input v-model="formData.is_customer" type="checkbox" :disabled="!isEditing"
                    class="w-4 h-4 text-blue-600 border-gray-300 rounded disabled:opacity-50" />
                  <span class="text-sm text-gray-700">{{ t('common.customer') }}</span>
                </label>
                <label class="flex items-center gap-2">
                  <input v-model="formData.is_supplier" type="checkbox" :disabled="!isEditing"
                    class="w-4 h-4 text-blue-600 border-gray-300 rounded disabled:opacity-50" />
                  <span class="text-sm text-gray-700">{{ t('common.supplier') }}</span>
                </label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{{ t('companies.metadata') }}</CardTitle></CardHeader>
        <CardContent>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <p class="text-gray-500">{{ t('companies.createdAt') }}</p>
              <p class="text-gray-900">{{ new Date(company.created_at).toLocaleString() }}</p>
            </div>
            <div>
              <p class="text-gray-500">{{ t('companies.updatedAt') }}</p>
              <p class="text-gray-900">{{ new Date(company.updated_at).toLocaleString() }}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
