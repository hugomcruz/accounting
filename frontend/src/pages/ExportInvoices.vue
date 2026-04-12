<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Download, FileArchive, RefreshCw, CheckCircle, XCircle, Clock, AlertCircle, Trash2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { exportApi } from '@/services/queries'

const { t } = useI18n()
const queryClient = useQueryClient()

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

const selectedYear = ref(currentYear)
const selectedMonth = ref(currentMonth)

const years = Array.from({ length: 5 }, (_, i) => currentYear - i)
const months = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
]

const monthLabel = computed(() => months.find(m => m.value === selectedMonth.value)?.label ?? '')

// Poll every 3 s so in-progress jobs refresh automatically
const { data: exports, isLoading } = useQuery({
  queryKey: ['invoice-exports'],
  queryFn: async () => {
    const res = await exportApi.listInvoiceExports()
    return res.data as InvoiceExportRecord[]
  },
  refetchInterval: (query: { state: { data?: InvoiceExportRecord[] } }) => {
    const rows = query.state.data
    const hasActive = rows?.some(r => r.status === 'pending' || r.status === 'processing')
    return hasActive ? 3000 : false
  },
})

const triggerMutation = useMutation({
  mutationFn: () => exportApi.triggerInvoiceExport(selectedYear.value, selectedMonth.value),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-exports'] })
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => exportApi.deleteInvoiceExport(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-exports'] })
  },
})

function confirmDelete(id: number) {
  if (window.confirm(t('exports.deleteConfirm'))) {
    deleteMutation.mutate(id)
  }
}

interface InvoiceExportRecord {
  id: number
  year: number
  month: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  invoice_count: number
  created_at: string
  completed_at: string | null
  error_message: string | null
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function monthName(m: number) {
  return months.find(x => x.value === m)?.label ?? m
}

async function downloadExport(id: number) {
  const res = await exportApi.downloadExport(id)
  const url = URL.createObjectURL(new Blob([res.data], { type: 'application/zip' }))
  const a = document.createElement('a')
  a.href = url
  const row = exports.value?.find((e: any) => e.id === id)
  a.download = row ? `invoices_${row.year}_${String(row.month).padStart(2, '0')}.zip` : `export_${id}.zip`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">{{ t('exports.title') }}</h1>
      <p class="mt-1 text-sm text-gray-500">{{ t('exports.subtitle') }}</p>
    </div>

    <!-- Trigger new export -->
    <Card>
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <FileArchive class="h-5 w-5 text-primary-600" />
          {{ t('exports.newExport') }}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="flex flex-wrap items-end gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('exports.yearLabel') }}</label>
            <select
              v-model="selectedYear"
              class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('exports.monthLabel') }}</label>
            <select
              v-model="selectedMonth"
              class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option v-for="m in months" :key="m.value" :value="m.value">{{ t('common.months.' + m.label.toLowerCase()) }}</option>
            </select>
          </div>

          <Button
            :disabled="triggerMutation.isPending.value"
            @click="triggerMutation.mutate()"
          >
            <Download class="h-4 w-4 mr-2" />
            {{ triggerMutation.isPending.value ? t('exports.queuing') : t('exports.exportBtn', { period: t('common.months.' + monthLabel.toLowerCase()) + ' ' + selectedYear }) }}
          </Button>
        </div>

        <p v-if="triggerMutation.isError.value" class="mt-3 text-sm text-red-600 flex items-center gap-1">
          <AlertCircle class="h-4 w-4" />
          {{ t('exports.queueError') }}
        </p>
      </CardContent>
    </Card>

    <!-- Export history -->
    <Card>
      <CardHeader>
        <div class="flex items-center justify-between">
          <CardTitle class="flex items-center gap-2">
            <Download class="h-5 w-5 text-primary-600" />
            {{ t('exports.historyCard') }}
          </CardTitle>
          <button
            class="text-gray-400 hover:text-gray-600 transition-colors"
            :title="t('common.refresh')"
            @click="queryClient.invalidateQueries({ queryKey: ['invoice-exports'] })"
          >
            <RefreshCw class="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-8 text-gray-400 text-sm">{{ t('common.loading') }}</div>

        <div v-else-if="!exports?.length" class="text-center py-8 text-gray-400 text-sm">
          {{ t('exports.noExports') }}
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                <th class="py-3 pr-4">{{ t('exports.tablePeriod') }}</th>
                <th class="py-3 pr-4">{{ t('exports.tableStatus') }}</th>
                <th class="py-3 pr-4">{{ t('exports.tableFiles') }}</th>
                <th class="py-3 pr-4">{{ t('exports.tableRequested') }}</th>
                <th class="py-3 pr-4">{{ t('exports.tableCompleted') }}</th>
                <th class="py-3"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="row in exports" :key="row.id" class="hover:bg-gray-50">
                <td class="py-3 pr-4 font-medium text-gray-900">
                  {{ t('common.months.' + String(monthName(row.month)).toLowerCase()) }} {{ row.year }}
                </td>

                <!-- Status badge -->
                <td class="py-3 pr-4">
                  <span
                    v-if="row.status === 'completed'"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700"
                  >
                    <CheckCircle class="h-3 w-3" /> {{ t('exports.statusCompleted') }}
                  </span>
                  <span
                    v-else-if="row.status === 'failed'"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700"
                    :title="row.error_message ?? ''"
                  >
                    <XCircle class="h-3 w-3" /> {{ t('exports.statusFailed') }}
                  </span>
                  <span
                    v-else-if="row.status === 'processing'"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                  >
                    <RefreshCw class="h-3 w-3 animate-spin" /> {{ t('exports.statusProcessing') }}
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600"
                  >
                    <Clock class="h-3 w-3" /> {{ t('exports.statusPending') }}
                  </span>
                </td>

                <td class="py-3 pr-4 text-gray-700">
                  {{ row.status === 'completed' ? row.invoice_count : '—' }}
                </td>

                <td class="py-3 pr-4 text-gray-500">{{ formatDate(row.created_at) }}</td>
                <td class="py-3 pr-4 text-gray-500">{{ formatDate(row.completed_at) }}</td>

                <td class="py-3 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <Button
                      v-if="row.status === 'completed'"
                      variant="secondary"
                      class="text-xs py-1 px-3"
                      @click="downloadExport(row.id)"
                    >
                      <Download class="h-3 w-3 mr-1" />
                      {{ t('common.download') }}
                    </Button>
                    <span v-else class="text-xs text-gray-400 italic">
                      {{
                        row.status === 'failed'
                          ? (row.error_message ?? t('exports.exportFailed'))
                          : t('exports.building')
                      }}
                    </span>
                    <button
                      class="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                      :title="t('exports.deleteBtn')"
                      :disabled="deleteMutation.isPending.value"
                      @click="confirmDelete(row.id)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </button>
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
