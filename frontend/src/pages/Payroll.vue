<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Plus, Play, Upload, FileText } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { hrApi } from '@/services/queries'

const { t } = useI18n()
const queryClient = useQueryClient()

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

const newPeriodYear = ref(currentYear)
const newPeriodMonth = ref(currentMonth)
const selectedPeriod = ref<any>(null)
const payrollFile = ref<File | null>(null)

const { data: periods, isLoading } = useQuery({
  queryKey: ['payroll-periods'],
  queryFn: async () => {
    const res = await hrApi.getPayrollPeriods()
    return res.data
  },
})

const { data: periodEntries, isLoading: loadingEntries } = useQuery({
  queryKey: ['payroll-entries', selectedPeriod],
  queryFn: async () => {
    if (!selectedPeriod.value) return []
    const res = await hrApi.getPayrollPeriods()
    const found = res.data.find((p: any) => p.id === selectedPeriod.value.id)
    return found?.entries ?? []
  },
  enabled: !!selectedPeriod.value,
})

const createPeriodMutation = useMutation({
  mutationFn: () => hrApi.createPayrollPeriod({ year: newPeriodYear.value, month: newPeriodMonth.value }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-periods'] }),
})

const processMutation = useMutation({
  mutationFn: (id: number) => hrApi.processPayrollPeriod(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-periods'] }),
})

const uploadFileMutation = useMutation({
  mutationFn: async ({ id, file }: { id: number; file: File }) => {
    const formData = new FormData()
    formData.append('file', file)
    return hrApi.uploadPayrollFile(id, formData)
  },
  onSuccess: () => {
    payrollFile.value = null
    queryClient.invalidateQueries({ queryKey: ['payroll-periods'] })
  },
})

function statusColor(status: string) {
  const map: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-600',
    processed: 'bg-blue-100 text-blue-700',
    paid: 'bg-green-100 text-green-700',
    closed: 'bg-purple-100 text-purple-700',
  }
  return map[status?.toLowerCase()] ?? 'bg-gray-100 text-gray-600'
}

const months = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
]
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('payroll.title') }}</h1>
      <p class="mt-1 text-gray-500">{{ t('payroll.subtitle') }}</p>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('payroll.createPeriodCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div class="flex items-end gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('payroll.yearLabel') }}</label>
            <input v-model.number="newPeriodYear" type="number" min="2020" max="2099"
              class="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 w-28" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('payroll.monthLabel') }}</label>
            <select v-model.number="newPeriodMonth"
              class="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option v-for="(m, i) in months" :key="i+1" :value="i+1">{{ t('common.months.' + m.toLowerCase()) }}</option>
            </select>
          </div>
          <button
            :disabled="createPeriodMutation.isPending.value"
            class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="createPeriodMutation.mutate()"
          >
            <Plus class="h-4 w-4" />
            {{ createPeriodMutation.isPending.value ? t('payroll.creating') : t('payroll.createPeriod') }}
          </button>
        </div>
      </CardContent>
    </Card>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card class="lg:col-span-1">
        <CardHeader><CardTitle>{{ t('payroll.periodsCard') }}</CardTitle></CardHeader>
        <CardContent>
          <div v-if="isLoading" class="text-center py-4 text-gray-500">{{ t('common.loading') }}</div>
          <div v-else-if="!periods?.length" class="text-center py-4 text-gray-400">{{ t('payroll.noPeriods') }}</div>
          <div v-else class="space-y-2">
            <div
              v-for="period in periods"
              :key="period.id"
              class="p-3 border rounded-lg cursor-pointer transition-colors"
              :class="selectedPeriod?.id === period.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'"
              @click="selectedPeriod = period"
            >
              <div class="flex items-center justify-between">
                <p class="font-medium text-sm">{{ t('common.months.' + months[period.month - 1].toLowerCase()) }} {{ period.year }}</p>
                <span :class="statusColor(period.status)" class="px-2 py-0.5 rounded-full text-xs font-medium capitalize">
                  {{ period.status }}
                </span>
              </div>
              <div class="flex gap-2 mt-2">
                <button
                  v-if="period.status === 'draft'"
                  class="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                  @click.stop="processMutation.mutate(period.id)"
                >
                  <Play class="h-3 w-3" />
                  {{ t('payroll.processBtn') }}
                </button>
                <label class="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 cursor-pointer">
                  <Upload class="h-3 w-3" />
                  {{ t('payroll.uploadCsv') }}
                  <input type="file" accept=".csv" class="hidden"
                    @change="(e) => { payrollFile = (e.target as HTMLInputElement).files?.[0] ?? null; if (payrollFile) uploadFileMutation.mutate({ id: period.id, file: payrollFile }) }" />
                </label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card class="lg:col-span-2">
        <CardHeader><CardTitle>
          {{ selectedPeriod ? t('payroll.entriesCardPeriod', { period: `${t('common.months.' + months[selectedPeriod.month - 1].toLowerCase())} ${selectedPeriod.year}` }) : t('payroll.entriesCard') }}
        </CardTitle></CardHeader>
        <CardContent>
          <div v-if="!selectedPeriod" class="text-center py-8 text-gray-400">
            <FileText class="h-10 w-10 mx-auto mb-2 opacity-50" />
            {{ t('payroll.selectPeriod') }}
          </div>
          <div v-else-if="loadingEntries" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
          <div v-else-if="!periodEntries?.length" class="text-center py-6 text-gray-400">{{ t('payroll.noEntries') }}</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-500">
                  <th class="pb-2 font-medium">{{ t('payroll.tableEmployee') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('payroll.tableBaseSalary') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('payroll.tableDeductions') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('payroll.tableNet') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in periodEntries" :key="entry.id" class="border-b last:border-0 hover:bg-gray-50">
                  <td class="py-2.5">{{ entry.employee_name || entry.employee_id }}</td>
                  <td class="py-2.5 text-right">€{{ Number(entry.base_salary || 0).toFixed(2) }}</td>
                  <td class="py-2.5 text-right text-red-600">-€{{ Number(entry.total_deductions || 0).toFixed(2) }}</td>
                  <td class="py-2.5 text-right font-semibold">€{{ Number(entry.net_salary || 0).toFixed(2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
