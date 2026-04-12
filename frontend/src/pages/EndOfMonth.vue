<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import {
  CalendarCheck, FileText, Landmark, FileArchive,
  Download, Plus, Trash2, ChevronLeft, RefreshCw,
  CheckCircle, XCircle, AlertCircle,
} from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { processesApi } from '@/services/queries'

const { t } = useI18n()
const queryClient = useQueryClient()

// ── View state: 'list' | 'new' | 'detail' ─────────────────────────────────
const view = ref<'list' | 'new' | 'detail'>('list')
const selectedReportId = ref<number | null>(null)

// ── Types ──────────────────────────────────────────────────────────────────
interface Report {
  id: number
  year: number
  month: number
  status: 'generating' | 'ready' | 'failed'
  error_message: string | null
  saft_import_id: number | null
  bank_statement_id: number | null
  invoice_export_id: number | null
  saft_filename: string | null
  bank_statement_filename: string | null
  invoice_count: number
  saft_download_url: string | null
  bank_statement_download_url: string | null
  invoice_zip_download_url: string | null
  created_at: string
  completed_at: string | null
}
interface SaftOption { id: number; filename: string; company_name: string; fiscal_year: number; start_date: string; end_date: string }
interface BankOption { id: number; filename: string; account_number: string; company_name: string; period_start: string; period_end: string; opening_balance: number | null; closing_balance: number | null }
interface Available { saft_files: SaftOption[]; bank_statements: BankOption[]; invoice_count: number }

// ── Month/Year helpers ─────────────────────────────────────────────────────
const monthKeys = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
const now = new Date()
const currentYear = now.getFullYear()
const currentMonth = now.getMonth() + 1
const years = Array.from({ length: 6 }, (_, i) => currentYear - i)
const months = monthKeys.map((k, i) => ({ value: i + 1, key: k }))

function monthName(m: number) {
  return t('endOfMonth.' + (monthKeys[m - 1] ?? 'jan'))
}
function fmt(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString()
}
function fmtDateTime(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

// ── List query ─────────────────────────────────────────────────────────────
const { data: reports, isLoading: reportsLoading } = useQuery({
  queryKey: ['month-end-reports'],
  queryFn: async () => {
    const r = await processesApi.listReports()
    return r.data as Report[]
  },
  refetchInterval: (q: { state: { data?: Report[] } }) => {
    const hasGenerating = q.state.data?.some(r => r.status === 'generating')
    return hasGenerating ? 4000 : false
  },
})

// ── Detail query ───────────────────────────────────────────────────────────
const { data: detailReport, isFetching: detailLoading } = useQuery({
  queryKey: computed(() => ['month-end-report', selectedReportId.value]),
  queryFn: async () => {
    if (!selectedReportId.value) return null
    const r = await processesApi.getReport(selectedReportId.value)
    return r.data as Report
  },
  enabled: computed(() => !!selectedReportId.value),
  refetchInterval: (q: { state: { data?: Report | null } }) => {
    const s = q.state.data?.status
    return s === 'generating' ? 3000 : false
  },
})

// ── New report form ────────────────────────────────────────────────────────
const newYear = ref(currentYear)
const newMonth = ref(currentMonth)

const { data: available, isLoading: availableLoading } = useQuery({
  queryKey: computed(() => ['month-end-available', newYear.value, newMonth.value]),
  queryFn: async () => {
    const r = await processesApi.getAvailable(newYear.value, newMonth.value)
    return r.data as Available
  },
  enabled: computed(() => view.value === 'new'),
})

const canGenerate = computed(() =>
  (available.value?.saft_files.length ?? 0) > 0 &&
  (available.value?.bank_statements.length ?? 0) > 0 &&
  (available.value?.invoice_count ?? 0) > 0
)

const createMutation = useMutation({
  mutationFn: () =>
    processesApi.createReport({
      year: newYear.value,
      month: newMonth.value,
    }),
  onSuccess: (res) => {
    queryClient.invalidateQueries({ queryKey: ['month-end-reports'] })
    selectedReportId.value = res.data.id
    view.value = 'detail'
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => processesApi.deleteReport(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['month-end-reports'] })
    view.value = 'list'
    selectedReportId.value = null
  },
})

function openDetail(id: number) {
  selectedReportId.value = id
  view.value = 'detail'
}

function openNew() {
  newYear.value = currentYear
  newMonth.value = currentMonth
  view.value = 'new'
}

function confirmDelete(id: number) {
  if (window.confirm(t('endOfMonth.deleteConfirm'))) {
    deleteMutation.mutate(id)
  }
}

function downloadFile(url: string | null) {
  if (url) window.open(url, '_blank')
}
</script>

<template>
  <div class="space-y-6">

    <!-- ═══ LIST VIEW ══════════════════════════════════════════════════════ -->
    <template v-if="view === 'list'">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <CalendarCheck class="h-6 w-6 text-primary-600" />
            {{ t('endOfMonth.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">{{ t('endOfMonth.subtitle') }}</p>
        </div>
        <Button @click="openNew">
          <Plus class="h-4 w-4 mr-2" />
          {{ t('endOfMonth.newReport') }}
        </Button>
      </div>

      <Card>
        <CardContent class="pt-4">
          <div v-if="reportsLoading" class="text-center py-10 text-sm text-gray-400">
            <RefreshCw class="mx-auto h-6 w-6 animate-spin opacity-40 mb-2" />
            {{ t('endOfMonth.loading') }}
          </div>

          <div v-else-if="!reports?.length" class="text-center py-16 text-gray-400">
            <CalendarCheck class="mx-auto h-12 w-12 mb-3 opacity-25" />
            <p class="text-sm">{{ t('endOfMonth.noReports') }}</p>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead>
                <tr class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  <th class="py-3 pr-4">{{ t('endOfMonth.colPeriod') }}</th>
                  <th class="py-3 pr-4">{{ t('endOfMonth.colStatus') }}</th>
                  <th class="py-3 pr-4">{{ t('endOfMonth.colSaft') }}</th>
                  <th class="py-3 pr-4">{{ t('endOfMonth.colBank') }}</th>
                  <th class="py-3 pr-4">{{ t('endOfMonth.colInvoices') }}</th>
                  <th class="py-3 pr-4">{{ t('endOfMonth.colCreated') }}</th>
                  <th class="py-3"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr
                  v-for="r in reports"
                  :key="r.id"
                  class="hover:bg-gray-50 cursor-pointer"
                  @click="openDetail(r.id)"
                >
                  <td class="py-3 pr-4 font-medium text-gray-900">
                    {{ monthName(r.month) }} {{ r.year }}
                  </td>
                  <td class="py-3 pr-4">
                    <span
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                      :class="{
                        'bg-green-100 text-green-700': r.status === 'ready',
                        'bg-yellow-100 text-yellow-700': r.status === 'generating',
                        'bg-red-100 text-red-700': r.status === 'failed',
                      }"
                    >
                      <RefreshCw v-if="r.status === 'generating'" class="h-3 w-3 animate-spin" />
                      <CheckCircle v-else-if="r.status === 'ready'" class="h-3 w-3" />
                      <XCircle v-else class="h-3 w-3" />
                      {{ t('endOfMonth.status' + r.status.charAt(0).toUpperCase() + r.status.slice(1)) }}
                    </span>
                  </td>
                  <td class="py-3 pr-4 text-gray-600 max-w-[180px] truncate" :title="r.saft_filename ?? ''">
                    {{ r.saft_filename || '—' }}
                  </td>
                  <td class="py-3 pr-4 text-gray-600 max-w-[180px] truncate" :title="r.bank_statement_filename ?? ''">
                    {{ r.bank_statement_filename || '—' }}
                  </td>
                  <td class="py-3 pr-4 text-gray-700">{{ r.invoice_count }}</td>
                  <td class="py-3 pr-4 text-gray-500 whitespace-nowrap">{{ fmtDateTime(r.created_at) }}</td>
                  <td class="py-3 text-right" @click.stop>
                    <button
                      class="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                      :title="t('endOfMonth.deleteBtn')"
                      :disabled="deleteMutation.isPending.value"
                      @click="confirmDelete(r.id)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </template>

    <!-- ═══ NEW REPORT VIEW ════════════════════════════════════════════════ -->
    <template v-else-if="view === 'new'">
      <div class="flex items-center gap-3">
        <button class="text-gray-400 hover:text-gray-700 transition-colors" @click="view = 'list'">
          <ChevronLeft class="h-5 w-5" />
        </button>
        <h1 class="text-2xl font-bold text-gray-900">{{ t('endOfMonth.newReport') }}</h1>
      </div>

      <Card>
        <CardContent class="pt-5 space-y-5">
          <!-- Year / Month -->
          <div class="flex flex-wrap gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('endOfMonth.year') }}</label>
              <select
                v-model="newYear"
                class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('endOfMonth.month') }}</label>
              <select
                v-model="newMonth"
                class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option v-for="m in months" :key="m.value" :value="m.value">{{ t('endOfMonth.' + m.key) }}</option>
              </select>
            </div>
          </div>

          <div v-if="availableLoading" class="text-sm text-gray-400">
            {{ t('endOfMonth.loading') }}
          </div>

          <template v-else-if="available">
            <!-- Missing items warning -->
            <div
              v-if="!available.saft_files.length || !available.bank_statements.length || !available.invoice_count"
              class="rounded-md bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800 flex gap-2"
            >
              <AlertCircle class="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p v-if="!available.saft_files.length">{{ t('endOfMonth.missingSaft') }}</p>
                <p v-if="!available.bank_statements.length">{{ t('endOfMonth.missingBank') }}</p>
                <p v-if="!available.invoice_count">{{ t('endOfMonth.missingInvoices') }}</p>
              </div>
            </div>

            <!-- Auto-detected SAF-T -->
            <div v-if="available.saft_files.length" class="flex items-start gap-3 rounded-md bg-green-50 border border-green-200 px-4 py-3">
              <CheckCircle class="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
              <div class="text-sm">
                <p class="font-medium text-gray-800">{{ t('endOfMonth.saftSection') }}</p>
                <p class="text-gray-600">{{ available.saft_files[0].filename }} — {{ available.saft_files[0].company_name }} ({{ fmt(available.saft_files[0].start_date) }} – {{ fmt(available.saft_files[0].end_date) }})</p>
              </div>
            </div>

            <!-- Auto-detected bank statement -->
            <div v-if="available.bank_statements.length" class="flex items-start gap-3 rounded-md bg-green-50 border border-green-200 px-4 py-3">
              <CheckCircle class="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
              <div class="text-sm">
                <p class="font-medium text-gray-800">{{ t('endOfMonth.bankSection') }}</p>
                <p class="text-gray-600">{{ available.bank_statements[0].filename }} — {{ available.bank_statements[0].account_number }} ({{ fmt(available.bank_statements[0].period_start) }} – {{ fmt(available.bank_statements[0].period_end) }})</p>
              </div>
            </div>

            <!-- Invoice count info -->
            <p v-if="available.invoice_count > 0" class="text-sm text-gray-500 flex items-center gap-1">
              <FileText class="h-4 w-4 text-primary-500" />
              {{ t('endOfMonth.invoicesAvailable', { count: available.invoice_count }) }}
            </p>

            <!-- Error from mutation -->
            <p v-if="createMutation.isError.value" class="text-sm text-red-600 flex items-center gap-1">
              <XCircle class="h-4 w-4" />
              {{ (createMutation.error.value as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Error generating report' }}
            </p>

            <div class="flex gap-3 pt-2">
              <Button
                :disabled="!canGenerate || createMutation.isPending.value"
                @click="createMutation.mutate()"
              >
                <RefreshCw v-if="createMutation.isPending.value" class="h-4 w-4 mr-2 animate-spin" />
                <FileArchive v-else class="h-4 w-4 mr-2" />
                {{ createMutation.isPending.value ? t('endOfMonth.generating') : t('endOfMonth.generateReport') }}
              </Button>
              <Button variant="outline" @click="view = 'list'">{{ t('endOfMonth.cancelBtn') }}</Button>
            </div>
          </template>
        </CardContent>
      </Card>
    </template>

    <!-- ═══ DETAIL VIEW ════════════════════════════════════════════════════ -->
    <template v-else-if="view === 'detail'">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button class="text-gray-400 hover:text-gray-700 transition-colors" @click="view = 'list'">
            <ChevronLeft class="h-5 w-5" />
          </button>
          <div>
            <h1 class="text-2xl font-bold text-gray-900">
              {{ detailReport ? monthName(detailReport.month) + ' ' + detailReport.year : t('endOfMonth.detailTitle') }}
            </h1>
            <p v-if="detailReport" class="text-sm text-gray-500">
              {{ t('endOfMonth.generatedOn') }}: {{ fmtDateTime(detailReport.created_at) }}
            </p>
          </div>
        </div>
        <Button
          v-if="detailReport"
          variant="outline"
          class="text-red-600 border-red-300 hover:bg-red-50"
          :disabled="deleteMutation.isPending.value"
          @click="confirmDelete(detailReport.id)"
        >
          <Trash2 class="h-4 w-4 mr-2" />
          {{ t('endOfMonth.deleteBtn') }}
        </Button>
      </div>

      <div v-if="detailLoading && !detailReport" class="text-center py-16 text-gray-400 text-sm">
        <RefreshCw class="mx-auto h-8 w-8 animate-spin opacity-40 mb-2" />
        {{ t('endOfMonth.loading') }}
      </div>

      <template v-else-if="detailReport">
        <!-- Status banner while generating -->
        <div
          v-if="detailReport.status === 'generating'"
          class="flex items-center gap-3 rounded-md bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700"
        >
          <RefreshCw class="h-4 w-4 animate-spin shrink-0" />
          {{ t('endOfMonth.statusGenerating') }}…
        </div>
        <div
          v-else-if="detailReport.status === 'failed'"
          class="flex items-center gap-3 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
        >
          <XCircle class="h-4 w-4 shrink-0" />
          {{ t('endOfMonth.statusFailed') }}: {{ detailReport.error_message }}
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">

          <!-- SAF-T -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2 text-base">
                <FileText class="h-4 w-4 text-primary-600" />
                {{ t('endOfMonth.saftSection') }}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p v-if="!detailReport.saft_filename" class="text-sm text-gray-400">{{ t('endOfMonth.noFile') }}</p>
              <div v-else class="space-y-2 text-sm text-gray-700">
                <p class="font-medium break-all">{{ detailReport.saft_filename }}</p>
                <Button
                  v-if="detailReport.saft_download_url"
                  variant="outline"
                  size="sm"
                  class="w-full"
                  @click="downloadFile(detailReport.saft_download_url)"
                >
                  <Download class="h-4 w-4 mr-2" />
                  {{ t('endOfMonth.download') }}
                </Button>
              </div>
            </CardContent>
          </Card>

          <!-- Bank Statement -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2 text-base">
                <Landmark class="h-4 w-4 text-primary-600" />
                {{ t('endOfMonth.bankSection') }}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p v-if="!detailReport.bank_statement_filename" class="text-sm text-gray-400">{{ t('endOfMonth.noFile') }}</p>
              <div v-else class="space-y-2 text-sm text-gray-700">
                <p class="font-medium break-all">{{ detailReport.bank_statement_filename }}</p>
                <Button
                  v-if="detailReport.bank_statement_download_url"
                  variant="outline"
                  size="sm"
                  class="w-full"
                  @click="downloadFile(detailReport.bank_statement_download_url)"
                >
                  <Download class="h-4 w-4 mr-2" />
                  {{ t('endOfMonth.download') }}
                </Button>
              </div>
            </CardContent>
          </Card>

          <!-- Invoice ZIP -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2 text-base">
                <FileArchive class="h-4 w-4 text-primary-600" />
                {{ t('endOfMonth.invoiceSection') }}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div v-if="detailReport.status === 'generating'" class="flex items-center gap-2 text-sm text-blue-600">
                <RefreshCw class="h-4 w-4 animate-spin" />
                {{ t('endOfMonth.statusGenerating') }}…
              </div>
              <div v-else-if="!detailReport.invoice_zip_download_url" class="text-sm text-gray-400">
                {{ t('endOfMonth.noFile') }}
              </div>
              <div v-else class="space-y-2 text-sm text-gray-700">
                <p class="font-medium">
                  {{ t('endOfMonth.invoiceCount', { count: detailReport.invoice_count }) }}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  class="w-full"
                  @click="downloadFile(detailReport.invoice_zip_download_url)"
                >
                  <Download class="h-4 w-4 mr-2" />
                  {{ t('endOfMonth.downloadZip') }}
                </Button>
              </div>
            </CardContent>
          </Card>

        </div>
      </template>
    </template>

  </div>
</template>
