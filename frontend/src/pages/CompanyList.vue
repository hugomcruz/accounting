<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Building2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { companiesApi } from '@/services/queries'

const { t } = useI18n()
const router = useRouter()

const { data: companiesData, isLoading } = useQuery({
  queryKey: ['companies'],
  queryFn: async () => {
    const response = await companiesApi.getAll()
    return response.data
  },
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('companies.title') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('companies.subtitle') }}</p>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('companies.allCompanies') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>

        <div v-else-if="!companiesData?.length" class="text-center py-12">
          <Building2 class="mx-auto h-12 w-12 text-gray-400" />
          <h3 class="mt-2 text-sm font-medium text-gray-900">{{ t('companies.noCompanies') }}</h3>
          <p class="mt-1 text-sm text-gray-500">{{ t('companies.noCompaniesDesc') }}</p>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('companies.tableNif') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('companies.tableName') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('companies.tableCity') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('companies.tableType') }}</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr
                v-for="company in companiesData"
                :key="company.id"
                class="hover:bg-gray-50 cursor-pointer transition-colors"
                @click="router.push(`/companies/${company.id}`)"
              >
                <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ company.nif }}</td>
                <td class="px-6 py-4 text-sm text-gray-900">{{ company.name }}</td>
                <td class="px-6 py-4 text-sm text-gray-500">{{ company.city || '-' }}</td>
                <td class="px-6 py-4 text-sm">
                  <div class="flex gap-2">
                    <span v-if="company.is_customer" class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">{{ t('common.customer') }}</span>
                    <span v-if="company.is_supplier" class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">{{ t('common.supplier') }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
