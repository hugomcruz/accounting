<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Plus, Receipt, CheckCircle, Clock, XCircle, Send, Trash2, X, Banknote, Search } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { expensesApi, hrApi, bankApi } from '@/services/queries'
import { useAuthStore } from '@/stores/auth'
import type { ExpenseReport } from '@/types'

const router = useRouter()
const queryClient = useQueryClient()
const { t } = useI18n()
const auth = useAuthStore()

const isUser = computed(() => auth.isUser)
const isStaff = computed(() => auth.isStaff)

const filterStatus = ref('')
const showCreateModal = ref(false)
const form = ref({ employee_id: '', title: '', description: '' })

const { data: employees } = useQuery({
  queryKey: ['employees'],
  queryFn: async () => {
    const res = await hrApi.getEmployees()
    return res.data as { id: number; first_name: string; last_name: string }[]
  },
  // Only staff need the employee list for the dropdown
  enabled: isStaff,
})

const queryParams = computed(() => ({
  status: filterStatus.value || undefined,
}))

const { data: reports, isLoading } = useQuery({
  queryKey: ['expense-reports', queryParams],
  queryFn: async () => {
    const res = await expensesApi.listReports(queryParams.value)
    return res.data as ExpenseReport[]
  },
})

const createMutation = useMutation({
  mutationFn: () => {
    const empId = isUser.value ? undefined : Number(form.value.employee_id)
    return expensesApi.createReport(empId, {
      title: form.value.title,
      description: form.value.description || undefined,
    })
  },
  onSuccess: (res: { data: ExpenseReport }) => {
    queryClient.invalidateQueries({ queryKey: ['expense-reports'] })
    showCreateModal.value = false
    form.value = { employee_id: '', title: '', description: '' }
    router.push(`/expenses/${res.data.id}`)
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => expensesApi.deleteReport(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expense-reports'] }),
})

// ─── Mark Paid / Reconcile Modal ──────────────────────────────────────────
const showPayModal = ref(false)
const payingReport = ref<ExpenseReport | null>(null)
const txSearch = ref('')
const selectedTxId = ref<number | null>(null)

const txSearchParams = computed(() => ({
  search: txSearch.value || undefined,
  is_reconciled: false,
  limit: 50,
}))

const { data: txResults, isFetching: txFetching } = useQuery({
  queryKey: ['bank-tx-search', txSearchParams],
  queryFn: async () => {
    const res = await bankApi.getTransactions(txSearchParams.value)
    return res.data as { id: number; transaction_date: string; description: string; amount: number }[]
  },
  enabled: computed(() => showPayModal.value),
})

const payMutation = useMutation({
  mutationFn: () => expensesApi.payReport(payingReport.value!.id, selectedTxId.value!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['expense-reports'] })
    showPayModal.value = false
    payingReport.value = null
    selectedTxId.value = null
    txSearch.value = ''
  },
})

function openPayModal(report: ExpenseReport) {
  payingReport.value = report
  selectedTxId.value = null
  txSearch.value = ''
  showPayModal.value = true
}

function confirmDelete(report: ExpenseReport) {
  if (confirm(t('expenseReports.deleteConfirm', { title: report.title }))) deleteMutation.mutate(report.id)
}

const statusConfig: Record<string, { label: string; classes: string }> = {
  draft:     { label: t('expenseReports.filterDraft'),     classes: 'bg-gray-100 text-gray-600' },
  submitted: { label: t('expenseReports.filterSubmitted'), classes: 'bg-blue-100 text-blue-700' },
  approved:  { label: t('expenseReports.filterApproved'),  classes: 'bg-green-100 text-green-700' },
  rejected:  { label: t('expenseReports.filterRejected'),  classes: 'bg-red-100 text-red-700' },
  paid:      { label: t('expenseReports.filterPaid'),      classes: 'bg-purple-100 text-purple-700' },
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString()
}

function fmtOpt(iso?: string) {
  return iso ? new Date(iso).toLocaleDateString() : '—'
}

function fmtAmount(v: number) {
  return new Intl.NumberFormat('pt-PT', { style: 'currency', currency: 'EUR' }).format(v)
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">{{ t('expenseReports.title') }}</h1>
        <p class="mt-1 text-sm text-gray-500">{{ t('expenseReports.subtitle') }}</p>
      </div>
      <Button @click="showCreateModal = true">
        <Plus class="h-4 w-4 mr-2" />
        {{ t('expenseReports.newReport') }}
      </Button>
    </div>

    <!-- Filters -->
    <div class="flex gap-2 flex-wrap">
      <button
        v-for="opt in [{ value: '', label: t('common.all') }, { value: 'draft', label: t('expenseReports.filterDraft') }, { value: 'submitted', label: t('expenseReports.filterSubmitted') }, { value: 'approved', label: t('expenseReports.filterApproved') }, { value: 'rejected', label: t('expenseReports.filterRejected') }, { value: 'paid', label: t('expenseReports.filterPaid') }]"
        :key="opt.value"
        :class="[
          'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
          filterStatus === opt.value
            ? 'bg-primary-600 text-white'
            : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50',
        ]"
        @click="filterStatus = opt.value"
      >
        {{ opt.label }}
      </button>
    </div>

    <Card>
      <CardContent>
        <div v-if="isLoading" class="text-center py-10 text-gray-400 text-sm">{{ t('common.loading') }}</div>
        <div v-else-if="!reports?.length" class="text-center py-10 text-gray-400 text-sm">
          {{ t('expenseReports.noReports') }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                <th class="pb-2 pr-4 font-medium">{{ t('expenseReports.colId') }}</th>
                <th v-if="isStaff" class="pb-2 pr-4 font-medium">{{ t('expenseReports.colEmployee') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('expenseReports.colTitle') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('expenseReports.colCreated') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('expenseReports.colSubmitted') }}</th>
                <th class="pb-2 pr-4 font-medium text-right">{{ t('expenseReports.colAmount') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('expenseReports.colStatus') }}</th>
                <th class="pb-2 font-medium">{{ t('expenseReports.colDecision') }}</th>
                <th class="pb-2 w-8"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="report in reports"
                :key="report.id"
                class="border-b last:border-0 hover:bg-gray-50 transition-colors cursor-pointer"
                @click="router.push(`/expenses/${report.id}`)"
              >
                <td class="py-2.5 pr-4 font-mono text-xs text-gray-500 whitespace-nowrap">{{ report.expense_id ?? `#${report.id}` }}</td>
                <td v-if="isStaff" class="py-2.5 pr-4 text-gray-700 whitespace-nowrap">{{ report.employee_name ?? '—' }}</td>
                <td class="py-2.5 pr-4">
                  <p class="font-medium text-gray-900 truncate max-w-[220px]">{{ report.title }}</p>
                </td>
                <td class="py-2.5 pr-4 text-gray-500 whitespace-nowrap text-xs">{{ fmt(report.created_at) }}</td>
                <td class="py-2.5 pr-4 text-gray-500 whitespace-nowrap text-xs">{{ fmtOpt(report.submitted_at) }}</td>
                <td class="py-2.5 pr-4 text-right font-semibold text-gray-900 whitespace-nowrap">{{ fmtAmount(report.total_amount) }}</td>
                <td class="py-2.5 pr-4">
                  <span :class="['px-2 py-0.5 rounded-full text-xs font-medium', statusConfig[report.status]?.classes]">
                    {{ statusConfig[report.status]?.label ?? report.status }}
                  </span>
                </td>
                <td class="py-2.5 pr-4 text-xs text-gray-500 whitespace-nowrap">
                  <template v-if="report.status === 'paid'">{{ fmtOpt(report.paid_at) }}</template>
                  <template v-else-if="report.status === 'approved'">{{ fmtOpt(report.approved_at) }}</template>
                  <template v-else-if="report.status === 'rejected'">{{ fmtOpt(report.updated_at) }}</template>
                  <template v-else>—</template>
                </td>
                <td class="py-2.5 text-right whitespace-nowrap" @click.stop>
                  <button
                    v-if="report.status === 'approved' && isStaff"
                    class="text-purple-500 hover:text-purple-700 transition-colors mr-2"
                    :title="t('expenseReports.markPaid')"
                    @click="openPayModal(report)"
                  >
                    <Banknote class="h-4 w-4" />
                  </button>
                  <button
                    v-if="report.status === 'draft'"
                    class="text-gray-300 hover:text-red-500 transition-colors"
                    title="Delete"
                    @click="confirmDelete(report)"
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

    <!-- Create modal -->
    <Teleport to="body">
      <div
        v-if="showCreateModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        @click.self="showCreateModal = false"
      >
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold text-gray-900">{{ t('expenseReports.newReportModal') }}</h2>
            <button class="text-gray-400 hover:text-gray-600" @click="showCreateModal = false">
              <X class="h-5 w-5" />
            </button>
          </div>

          <div class="space-y-3">
            <!-- Employee selector: only shown to staff (admin/accountant) -->
            <div v-if="isStaff">
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseReports.employeeRequired') }}</label>
              <select
                v-model="form.employee_id"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">{{ t('expenseReports.selectEmployee') }}</option>
                <option v-for="emp in employees" :key="emp.id" :value="emp.id">
                  {{ emp.first_name }} {{ emp.last_name }}
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseReports.titleRequired') }}</label>
              <input
                v-model="form.title"
                type="text"
                :placeholder="t('expenseReports.titlePlaceholder')"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseReports.descriptionLabel') }}</label>
              <textarea
                v-model="form.description"
                rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <Button variant="secondary" @click="showCreateModal = false">{{ t('common.cancel') }}</Button>
            <Button
              :disabled="(isStaff && !form.employee_id) || !form.title || createMutation.isPending.value"
              @click="createMutation.mutate()"
            >
              {{ createMutation.isPending.value ? t('expenseReports.creating') : t('expenseReports.createReport') }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Mark Paid Modal ─────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showPayModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        @click.self="showPayModal = false"
      >
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg p-6 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold text-gray-900">{{ t('expenseReports.markPaidModal') }}</h2>
            <button class="text-gray-400 hover:text-gray-600" @click="showPayModal = false">
              <X class="h-5 w-5" />
            </button>
          </div>

          <p class="text-sm text-gray-600">
            {{ t('expenseReports.markPaidDesc', { id: payingReport?.expense_id ?? `#${payingReport?.id}`, amount: fmtAmount(payingReport?.total_amount ?? 0) }) }}
          </p>

          <!-- Transaction search -->
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              v-model="txSearch"
              type="text"
              :placeholder="t('expenseReports.searchTransaction')"
              class="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <!-- Transaction list -->
          <div class="border rounded-lg divide-y max-h-64 overflow-y-auto text-sm">
            <div v-if="txFetching" class="text-center py-6 text-gray-400 text-xs">{{ t('common.loading') }}</div>
            <div v-else-if="!txResults?.length" class="text-center py-6 text-gray-400 text-xs">{{ t('expenseReports.noTransactions') }}</div>
            <label
              v-for="tx in txResults"
              :key="tx.id"
              class="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
              :class="selectedTxId === tx.id ? 'bg-purple-50' : ''"
            >
              <input v-model="selectedTxId" type="radio" :value="tx.id" class="accent-purple-600" />
              <div class="flex-1 min-w-0">
                <p class="font-medium text-gray-800 truncate">{{ tx.description }}</p>
                <p class="text-xs text-gray-500">{{ new Date(tx.transaction_date).toLocaleDateString() }}</p>
              </div>
              <span class="font-semibold text-gray-700 whitespace-nowrap">{{ fmtAmount(tx.amount) }}</span>
            </label>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <Button variant="secondary" @click="showPayModal = false">{{ t('common.cancel') }}</Button>
            <Button
              class="bg-purple-600 hover:bg-purple-700"
              :disabled="!selectedTxId || payMutation.isPending.value"
              @click="payMutation.mutate()"
            >
              <Banknote class="h-4 w-4 mr-1.5" />
              {{ payMutation.isPending.value ? t('expenseReports.markingPaid') : t('expenseReports.confirmMarkPaid') }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
