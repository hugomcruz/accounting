<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { FileText, Building2, Database, Clock } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import { invoicesApi, companiesApi, saftApi, invoiceQueueApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'

const { t } = useI18n()
const router = useRouter()

const { data: invoicesData } = useQuery({
  queryKey: ['invoices-recent'],
  queryFn: async () => {
    const response = await invoicesApi.getAll({ limit: 10, order_by: 'created_at' })
    return response.data
  },
})

const { data: invoicesCount } = useQuery({
  queryKey: ['invoices-count'],
  queryFn: async () => {
    const response = await invoicesApi.getCount()
    return response.data.count
  },
})

const { data: companiesData } = useQuery({
  queryKey: ['companies-summary'],
  queryFn: async () => {
    const response = await companiesApi.getAll()
    return response.data
  },
})

const { data: saftData } = useQuery({
  queryKey: ['saft-summary'],
  queryFn: async () => {
    const response = await saftApi.getImports()
    return response.data
  },
})

const { data: queueData } = useQuery({
  queryKey: ['queue-summary'],
  queryFn: async () => {
    const response = await invoiceQueueApi.getAll({ status: 'needs_review' })
    return response.data
  },
})

const recentInvoices = computed(() => invoicesData.value ?? [])
const totalInvoices = computed(() => invoicesCount.value ?? 0)
const totalCompanies = computed(() => companiesData.value?.length ?? 0)
const totalImports = computed(() => saftData.value?.length ?? 0)
const pendingReview = computed(() => queueData.value?.length ?? 0)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('dashboard.title') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('dashboard.welcome') }}</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-gray-600">{{ t('dashboard.totalInvoices') }}</p>
            <p class="text-2xl font-bold text-gray-900">{{ totalInvoices }}</p>
          </div>
          <FileText class="h-8 w-8 text-primary-500" />
        </div>
      </Card>

      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-gray-600">{{ t('dashboard.companies') }}</p>
            <p class="text-2xl font-bold text-gray-900">{{ totalCompanies }}</p>
          </div>
          <Building2 class="h-8 w-8 text-green-500" />
        </div>
      </Card>

      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-gray-600">{{ t('dashboard.saftImports') }}</p>
            <p class="text-2xl font-bold text-gray-900">{{ totalImports }}</p>
          </div>
          <Database class="h-8 w-8 text-purple-500" />
        </div>
      </Card>

      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-gray-600">{{ t('dashboard.pendingReview') }}</p>
            <p class="text-2xl font-bold text-orange-600">{{ pendingReview }}</p>
          </div>
          <Clock class="h-8 w-8 text-orange-500" />
        </div>
      </Card>
    </div>

    <!-- Recent invoices -->
    <Card>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900">{{ t('dashboard.recentInvoices') }}</h2>
        <button
          class="text-sm text-primary-600 hover:text-primary-800 font-medium"
          @click="router.push('/invoices')"
        >
          {{ t('common.viewAll') }}
        </button>
      </div>

      <div v-if="recentInvoices.length === 0" class="text-center py-8 text-gray-500">
        {{ t('dashboard.noInvoices') }}
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('common.type') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('dashboard.supplier') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('common.date') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('dashboard.invoiceNumber') }}</th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total Amount</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="invoice in recentInvoices"
              :key="invoice.id"
              class="hover:bg-gray-50 cursor-pointer"
              @click="router.push(`/invoices/${invoice.id}`)"
            >
              <td class="px-4 py-3 text-sm">
                <span
                  :class="invoice.invoice_type === 'SALE' || invoice.invoice_type === 'sale'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-blue-100 text-blue-800'"
                  class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium"
                >
                  {{ invoice.invoice_type === 'SALE' || invoice.invoice_type === 'sale' ? t('common.sale') : t('common.purchase') }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">{{ invoice.supplier_name ?? invoice.customer_name ?? '-' }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ formatDate(invoice.invoice_date) }}</td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ invoice.invoice_number }}</td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900 text-right">{{ formatCurrency(invoice.total_amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
