<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { RefreshCw, Banknote, User, Building2, Receipt, Search } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { bankApi, invoicesApi, hrApi, expensesApi } from '@/services/queries'
import { formatCurrency } from '@/lib/utils'

const queryClient = useQueryClient()

// Independent date ranges for invoices and transactions
const today = new Date().toISOString().split('T')[0]
const firstOfYear = `${new Date().getFullYear()}-01-01`

const invoiceStartDate = ref(firstOfYear)
const invoiceEndDate = ref(today)
const txStartDate = ref(firstOfYear)
const txEndDate = ref(today)

const invoiceDateParams = computed(() => ({
  start_date: invoiceStartDate.value,
  end_date: invoiceEndDate.value,
  limit: 500,
}))

const txDateParams = computed(() => ({
  start_date: txStartDate.value,
  end_date: txEndDate.value,
  limit: 500,
}))

const { data: invoices, isLoading: invoicesLoading } = useQuery({
  queryKey: ['invoices-manual-recon', invoiceDateParams],
  queryFn: async () => (await invoicesApi.getAll(invoiceDateParams.value)).data,
})

const { data: bankTransactions, isLoading: txLoading } = useQuery({
  queryKey: ['bank-tx-manual-recon', txDateParams],
  queryFn: async () => (await bankApi.getTransactions(txDateParams.value)).data,
})

const { data: employees } = useQuery({
  queryKey: ['employees-list'],
  queryFn: async () => (await hrApi.getEmployees({ limit: 200 })).data,
})

// ── Invoice list (left panel) ────────────────────────────────────────────────
const manualSearchInvoice = ref('')
const manualShowAll = ref(false)
const selectedManualInvoice = ref<any>(null)

const manualInvoiceList = computed(() => {
  const all = invoices.value ?? []
  const pool = manualShowAll.value ? all : all.filter((i: any) => !i.is_reconciled)
  if (!manualSearchInvoice.value) return pool
  const q = manualSearchInvoice.value.toLowerCase()
  return pool.filter((i: any) =>
    i.invoice_number?.toLowerCase().includes(q) ||
    (i.supplier_name || i.customer_name || '').toLowerCase().includes(q)
  )
})

// ── Form state (right panel) ─────────────────────────────────────────────────
const manualMethod = ref<'bank' | 'cash' | 'employee'>('bank')
const txSearch = ref('')
const selectedTxIds = ref<number[]>([])
const manualDate = ref(today)
const manualAmount = ref<number | null>(null)
const manualNotes = ref('')
const manualEmployeeId = ref<number | null>(null)
const manualLoading = ref(false)
const manualSuccess = ref('')
const manualError = ref('')

const unreconciledTxs = computed(() =>
  (bankTransactions.value ?? []).filter((tx: any) => !tx.is_reconciled)
)

const filteredManualTxs = computed(() => {
  const q = txSearch.value.toLowerCase()
  if (!q) return unreconciledTxs.value
  return unreconciledTxs.value.filter((tx: any) => tx.description.toLowerCase().includes(q))
})

const selectedTxTotal = computed(() => {
  const allTxs: any[] = bankTransactions.value ?? []
  return selectedTxIds.value.reduce((sum, id) => {
    const tx = allTxs.find((t: any) => t.id === id)
    return sum + (tx ? Math.abs(tx.amount) : 0)
  }, 0)
})

const amountMatchStatus = computed<'exact' | 'partial' | 'over' | 'none'>(() => {
  if (!selectedManualInvoice.value || selectedTxIds.value.length === 0) return 'none'
  const diff = selectedTxTotal.value - selectedManualInvoice.value.total_amount
  if (Math.abs(diff) <= 0.01) return 'exact'
  if (diff > 0.01) return 'over'
  return 'partial'
})

const canSubmitManual = computed(() => {
  if (!selectedManualInvoice.value) return false
  if (manualMethod.value === 'bank') return selectedTxIds.value.length > 0
  if (manualMethod.value === 'cash') return !!manualDate.value && !!manualAmount.value
  if (manualMethod.value === 'employee') return !!manualEmployeeId.value && !!manualDate.value && !!manualAmount.value
  return false
})

function selectManualInvoice(inv: any) {
  selectedManualInvoice.value = inv
  selectedTxIds.value = []
  manualSuccess.value = ''
  manualError.value = ''
  manualAmount.value = Number(inv.total_amount) || null
}

function resetManual() {
  selectedManualInvoice.value = null
  selectedTxIds.value = []
  manualDate.value = today
  manualAmount.value = null
  manualNotes.value = ''
  manualEmployeeId.value = null
  manualSuccess.value = ''
  manualError.value = ''
}

async function submitManual() {
  if (!selectedManualInvoice.value || !canSubmitManual.value) return
  manualLoading.value = true
  manualSuccess.value = ''
  manualError.value = ''
  try {
    if (manualMethod.value === 'bank') {
      for (const txId of selectedTxIds.value) {
        await bankApi.reconcileTransaction(txId, selectedManualInvoice.value.id)
      }
    } else {
      await invoicesApi.manualReconcile(selectedManualInvoice.value.id, {
        method: manualMethod.value,
        employee_id: manualMethod.value === 'employee' ? manualEmployeeId.value : undefined,
        payment_date: manualDate.value,
        amount: manualAmount.value,
        notes: manualNotes.value || undefined,
      })
    }
    await queryClient.invalidateQueries({ queryKey: ['invoices-manual-recon'] })
    await queryClient.invalidateQueries({ queryKey: ['bank-tx-manual-recon'] })
    await queryClient.invalidateQueries({ queryKey: ['invoices'] })
    manualSuccess.value = 'Reconciliation saved!'
    setTimeout(resetManual, 1500)
  } catch {
    manualError.value = 'Failed to save. Please try again.'
  } finally {
    manualLoading.value = false
  }
}

function companyName(inv: any) {
  return inv.supplier_name || inv.customer_name || '-'
}

// ── Mode switcher ─────────────────────────────────────────────────────────────
const activeMode = ref<'invoice' | 'expense'>('invoice')

// ── Expense Report reconciliation ─────────────────────────────────────────────
const expenseSearch = ref('')
const selectedExpenseReport = ref<any>(null)
const expTxSearch = ref('')
const selectedExpTxId = ref<number | null>(null)
const expLoading = ref(false)
const expSuccess = ref('')
const expError = ref('')

const { data: approvedReports } = useQuery({
  queryKey: ['expense-reports-approved'],
  queryFn: async () => {
    const res = await expensesApi.listReports({ status: 'approved' })
    return res.data as any[]
  },
  enabled: computed(() => activeMode.value === 'expense'),
})

const filteredExpenseReports = computed(() => {
  const all = approvedReports.value ?? []
  if (!expenseSearch.value) return all
  const q = expenseSearch.value.toLowerCase()
  return all.filter((r: any) =>
    (r.expense_id ?? '').toLowerCase().includes(q) ||
    r.title.toLowerCase().includes(q) ||
    (r.employee_name ?? '').toLowerCase().includes(q)
  )
})

const expTxDateParams = computed(() => ({
  start_date: txStartDate.value,
  end_date: txEndDate.value,
  limit: 500,
  is_reconciled: false,
}))

const { data: expTxResults, isLoading: expTxLoading } = useQuery({
  queryKey: ['bank-tx-exp-recon', expTxDateParams],
  queryFn: async () => (await bankApi.getTransactions(expTxDateParams.value)).data as any[],
  enabled: computed(() => activeMode.value === 'expense'),
})

const filteredExpTxs = computed(() => {
  const all = expTxResults.value ?? []
  if (!expTxSearch.value) return all
  const q = expTxSearch.value.toLowerCase()
  return all.filter((tx: any) => tx.description.toLowerCase().includes(q))
})

function selectExpenseReport(r: any) {
  selectedExpenseReport.value = r
  selectedExpTxId.value = null
  expSuccess.value = ''
  expError.value = ''
}

function resetExpense() {
  selectedExpenseReport.value = null
  selectedExpTxId.value = null
  expTxSearch.value = ''
  expSuccess.value = ''
  expError.value = ''
}

async function submitExpenseReconcile() {
  if (!selectedExpenseReport.value || !selectedExpTxId.value) return
  expLoading.value = true
  expSuccess.value = ''
  expError.value = ''
  try {
    await expensesApi.payReport(selectedExpenseReport.value.id, selectedExpTxId.value)
    await queryClient.invalidateQueries({ queryKey: ['expense-reports-approved'] })
    await queryClient.invalidateQueries({ queryKey: ['bank-tx-exp-recon'] })
    await queryClient.invalidateQueries({ queryKey: ['invoices'] })
    expSuccess.value = 'Expense report marked as paid!'
    setTimeout(resetExpense, 1500)
  } catch {
    expError.value = 'Failed to save. Please try again.'
  } finally {
    expLoading.value = false
  }
}

function fmtCurrency(v: number) {
  return new Intl.NumberFormat('pt-PT', { style: 'currency', currency: 'EUR' }).format(v)
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">Manual Reconciliation</h1>
      <p class="mt-1 text-gray-500">Link invoices or expense reports to bank transactions, cash payments, or employee accounts across any date range.</p>
    </div>

    <!-- Mode tabs -->
    <div class="flex gap-2">
      <button
        :class="activeMode === 'invoice'
          ? 'bg-blue-600 text-white border-blue-600'
          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
        class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors"
        @click="activeMode = 'invoice'"
      >
        <Building2 class="h-4 w-4" /> Invoice
      </button>
      <button
        :class="activeMode === 'expense'
          ? 'bg-purple-600 text-white border-purple-600'
          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
        class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors"
        @click="activeMode = 'expense'"
      >
        <Receipt class="h-4 w-4" /> Expense Report
      </button>
    </div>

    <!-- ── Invoice reconciliation ────────────────────────────────────────── -->
    <template v-if="activeMode === 'invoice'">

    <!-- Date range filters -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardContent class="pt-4">
          <p class="text-sm font-semibold text-gray-700 mb-3">Invoice Date Range</p>
          <div class="flex items-center gap-3">
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">From</label>
              <input
                v-model="invoiceStartDate"
                type="date"
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <span class="text-gray-400 mt-4">→</span>
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">To</label>
              <input
                v-model="invoiceEndDate"
                type="date"
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="pt-4">
          <p class="text-sm font-semibold text-gray-700 mb-3">Bank Transaction Date Range</p>
          <div class="flex items-center gap-3">
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">From</label>
              <input
                v-model="txStartDate"
                type="date"
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <span class="text-gray-400 mt-4">→</span>
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">To</label>
              <input
                v-model="txEndDate"
                type="date"
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Main two-panel layout -->
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">

      <!-- Left panel: invoice list -->
      <div class="lg:col-span-2 space-y-3">
        <Card>
          <CardHeader>
            <CardTitle class="text-base">Select Invoice</CardTitle>
            <div class="mt-2 space-y-2">
              <input
                v-model="manualSearchInvoice"
                type="text"
                placeholder="Search invoice or company..."
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <label class="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
                <input v-model="manualShowAll" type="checkbox" class="rounded" />
                Show already reconciled
              </label>
            </div>
          </CardHeader>
          <CardContent class="pt-0 max-h-[520px] overflow-y-auto">
            <div v-if="invoicesLoading" class="text-center py-8 text-gray-400 text-sm">Loading...</div>
            <div v-else-if="!manualInvoiceList.length" class="text-center py-8 text-gray-400 text-sm">
              No invoices found for the selected range.
            </div>
            <div v-else class="space-y-1">
              <button
                v-for="inv in manualInvoiceList"
                :key="inv.id"
                class="w-full text-left px-3 py-2.5 rounded-lg border transition-colors"
                :class="selectedManualInvoice?.id === inv.id
                  ? 'bg-blue-50 border-blue-400 ring-1 ring-blue-400'
                  : 'border-gray-200 hover:bg-gray-50'"
                @click="selectManualInvoice(inv)"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono text-xs text-gray-500">{{ inv.invoice_number }}</span>
                  <span
                    :class="inv.invoice_type === 'sale' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'"
                    class="px-1.5 py-0.5 rounded text-xs font-medium"
                  >
                    {{ inv.invoice_type === 'sale' ? 'Sale' : 'Purchase' }}
                  </span>
                </div>
                <div class="text-sm font-medium text-gray-800 mt-0.5 truncate">{{ companyName(inv) }}</div>
                <div class="flex items-center justify-between mt-0.5">
                  <span class="text-xs text-gray-400">{{ inv.invoice_date ? new Date(inv.invoice_date).toLocaleDateString() : '' }}</span>
                  <span class="text-sm font-semibold text-gray-900">{{ formatCurrency(inv.total_amount) }}</span>
                </div>
                <div v-if="inv.is_reconciled" class="mt-1">
                  <span class="text-xs font-medium px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">✓ Reconciled</span>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Right panel: reconciliation form -->
      <div class="lg:col-span-3">
        <Card v-if="!selectedManualInvoice">
          <CardContent class="flex flex-col items-center justify-center py-24 text-center text-gray-400">
            <Building2 class="h-10 w-10 mb-3 text-gray-300" />
            <p class="text-sm">Select an invoice on the left to start reconciling</p>
          </CardContent>
        </Card>

        <Card v-else>
          <CardHeader>
            <div class="flex items-start justify-between">
              <div>
                <CardTitle class="text-base">{{ selectedManualInvoice.invoice_number }}</CardTitle>
                <p class="text-sm text-gray-500 mt-0.5">{{ companyName(selectedManualInvoice) }}</p>
              </div>
              <p class="text-lg font-bold text-gray-900">{{ formatCurrency(selectedManualInvoice.total_amount) }}</p>
            </div>
          </CardHeader>
          <CardContent class="space-y-5">

            <!-- Payment method selector -->
            <div>
              <p class="text-sm font-medium text-gray-700 mb-2">Payment Method</p>
              <div class="flex gap-2 flex-wrap">
                <button
                  v-for="m in [
                    { key: 'bank', label: 'Bank Transaction' },
                    { key: 'cash', label: 'Cash' },
                    { key: 'employee', label: 'Employee Account' },
                  ]"
                  :key="m.key"
                  :class="manualMethod === m.key
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
                  class="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors"
                  @click="manualMethod = (m.key as 'bank' | 'cash' | 'employee'); selectedTxIds = []"
                >
                  <RefreshCw v-if="m.key === 'bank'" class="h-3.5 w-3.5" />
                  <Banknote v-else-if="m.key === 'cash'" class="h-3.5 w-3.5" />
                  <User v-else class="h-3.5 w-3.5" />
                  {{ m.label }}
                </button>
              </div>
            </div>

            <!-- Bank: transaction checkboxes -->
            <div v-if="manualMethod === 'bank'" class="space-y-3">
              <div>
                <p class="text-sm font-medium text-gray-700 mb-1.5">
                  Select Transactions to Link
                  <span class="text-xs text-gray-400 font-normal ml-1">(using the bank transaction date range above)</span>
                </p>
                <input
                  v-model="txSearch"
                  type="text"
                  placeholder="Filter by description..."
                  class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div v-if="txLoading" class="text-center py-4 text-gray-400 text-sm">Loading transactions...</div>
              <div v-else-if="!filteredManualTxs.length" class="text-center py-6 text-gray-400 text-sm">
                No unreconciled transactions in the selected range.
              </div>
              <div v-else class="max-h-64 overflow-y-auto border border-gray-200 rounded-lg divide-y">
                <label
                  v-for="tx in filteredManualTxs"
                  :key="tx.id"
                  class="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    :value="tx.id"
                    v-model="selectedTxIds"
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div class="flex-1 min-w-0">
                    <p class="text-xs text-gray-500">{{ new Date(tx.transaction_date).toLocaleDateString() }}</p>
                    <p class="text-sm text-gray-800 truncate">{{ tx.description }}</p>
                  </div>
                  <span
                    class="text-sm font-semibold flex-shrink-0"
                    :class="tx.amount < 0 ? 'text-red-600' : 'text-emerald-600'"
                  >
                    {{ formatCurrency(tx.amount) }}
                  </span>
                </label>
              </div>
              <p v-if="selectedTxIds.length" class="text-xs text-blue-600 font-medium">
                {{ selectedTxIds.length }} transaction{{ selectedTxIds.length > 1 ? 's' : '' }} selected
              </p>

              <!-- Amount match indicator -->
              <div
                v-if="selectedTxIds.length > 0"
                class="rounded-lg border p-3 text-sm"
                :class="{
                  'bg-emerald-50 border-emerald-200': amountMatchStatus === 'exact',
                  'bg-amber-50 border-amber-200': amountMatchStatus === 'partial',
                  'bg-red-50 border-red-200': amountMatchStatus === 'over',
                }"
              >
                <div class="flex items-center justify-between">
                  <span class="font-medium"
                    :class="{
                      'text-emerald-800': amountMatchStatus === 'exact',
                      'text-amber-800': amountMatchStatus === 'partial',
                      'text-red-800': amountMatchStatus === 'over',
                    }"
                  >
                    <template v-if="amountMatchStatus === 'exact'">✓ Amounts match</template>
                    <template v-else-if="amountMatchStatus === 'partial'">⚠ Partial — invoice not fully covered</template>
                    <template v-else>✗ Over-payment — selected total exceeds invoice</template>
                  </span>
                </div>
                <div class="mt-2 flex items-center gap-6 text-xs"
                  :class="{
                    'text-emerald-700': amountMatchStatus === 'exact',
                    'text-amber-700': amountMatchStatus === 'partial',
                    'text-red-700': amountMatchStatus === 'over',
                  }"
                >
                  <span>Selected: <strong>{{ formatCurrency(selectedTxTotal) }}</strong></span>
                  <span>Invoice: <strong>{{ formatCurrency(selectedManualInvoice.total_amount) }}</strong></span>
                  <span v-if="amountMatchStatus !== 'exact'">
                    Δ <strong>{{ formatCurrency(Math.abs(selectedTxTotal - selectedManualInvoice.total_amount)) }}</strong>
                    {{ amountMatchStatus === 'partial' ? 'remaining' : 'excess' }}
                  </span>
                </div>
                <!-- progress bar -->
                <div class="mt-3 h-2 rounded-full bg-white/60 overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-300"
                    :class="{
                      'bg-emerald-500': amountMatchStatus === 'exact',
                      'bg-amber-400': amountMatchStatus === 'partial',
                      'bg-red-500': amountMatchStatus === 'over',
                    }"
                    :style="{ width: Math.min((selectedTxTotal / selectedManualInvoice.total_amount) * 100, 100) + '%' }"
                  />
                </div>
              </div>
            </div>

            <!-- Cash -->
            <div v-else-if="manualMethod === 'cash'" class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Payment Date <span class="text-red-500">*</span></label>
                  <input
                    v-model="manualDate"
                    type="date"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Amount (€) <span class="text-red-500">*</span></label>
                  <input
                    v-model.number="manualAmount"
                    type="number"
                    step="0.01"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                <textarea
                  v-model="manualNotes"
                  rows="2"
                  placeholder="E.g. paid at reception, receipt #..."
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            </div>

            <!-- Employee -->
            <div v-else-if="manualMethod === 'employee'" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Employee <span class="text-red-500">*</span></label>
                <select
                  v-model="manualEmployeeId"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option :value="null">Select employee...</option>
                  <option v-for="emp in employees ?? []" :key="emp.id" :value="emp.id">
                    {{ emp.first_name }} {{ emp.last_name }}
                  </option>
                </select>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Payment Date <span class="text-red-500">*</span></label>
                  <input
                    v-model="manualDate"
                    type="date"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Amount (€) <span class="text-red-500">*</span></label>
                  <input
                    v-model.number="manualAmount"
                    type="number"
                    step="0.01"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                <textarea
                  v-model="manualNotes"
                  rows="2"
                  placeholder="E.g. reimbursement reason, expense reference..."
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            </div>

            <!-- Submit row -->
            <div class="flex items-center justify-between pt-3 border-t">
              <div>
                <p v-if="manualSuccess" class="text-sm font-medium text-emerald-600">{{ manualSuccess }}</p>
                <p v-if="manualError" class="text-sm font-medium text-red-600">{{ manualError }}</p>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" @click="resetManual">Cancel</Button>
                <Button :disabled="manualLoading || !canSubmitManual" @click="submitManual">
                  {{ manualLoading ? 'Saving...' : 'Reconcile' }}
                </Button>
              </div>
            </div>

          </CardContent>
        </Card>
      </div>
    </div>

    </template>
    <!-- ── END Invoice mode ───────────────────────────────────────────────── -->

    <!-- ── Expense Report reconciliation ─────────────────────────────────── -->
    <template v-if="activeMode === 'expense'">

      <!-- Expense report Bank Transaction Date Range -->
      <Card>
        <CardContent class="pt-4">
          <p class="text-sm font-semibold text-gray-700 mb-3">Bank Transaction Date Range</p>
          <div class="flex items-center gap-3">
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">From</label>
              <input v-model="txStartDate" type="date" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <span class="text-gray-400 mt-4">→</span>
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1">To</label>
              <input v-model="txEndDate" type="date" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
        </CardContent>
      </Card>

      <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">

        <!-- Left: approved expense reports -->
        <div class="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle class="text-base">Select Approved Expense Report</CardTitle>
              <div class="mt-2">
                <input
                  v-model="expenseSearch"
                  type="text"
                  placeholder="Search ID, title, employee…"
                  class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </CardHeader>
            <CardContent class="pt-0 max-h-[520px] overflow-y-auto">
              <div v-if="!filteredExpenseReports.length" class="text-center py-8 text-gray-400 text-sm">
                No approved expense reports found.
              </div>
              <div v-else class="space-y-1">
                <button
                  v-for="r in filteredExpenseReports"
                  :key="r.id"
                  class="w-full text-left px-3 py-2.5 rounded-lg border transition-colors"
                  :class="selectedExpenseReport?.id === r.id
                    ? 'bg-purple-50 border-purple-400 ring-1 ring-purple-400'
                    : 'border-gray-200 hover:bg-gray-50'"
                  @click="selectExpenseReport(r)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-mono text-xs text-gray-500">{{ r.expense_id ?? `#${r.id}` }}</span>
                    <span class="px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">Approved</span>
                  </div>
                  <div class="text-sm font-medium text-gray-800 mt-0.5 truncate">{{ r.title }}</div>
                  <div class="flex items-center justify-between mt-0.5">
                    <span class="text-xs text-gray-400">{{ r.employee_name }}</span>
                    <span class="text-sm font-semibold text-gray-900">{{ fmtCurrency(r.total_amount) }}</span>
                  </div>
                </button>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Right: payment link form -->
        <div class="lg:col-span-3">
          <Card v-if="!selectedExpenseReport">
            <CardContent class="flex flex-col items-center justify-center py-24 text-center text-gray-400">
              <Receipt class="h-10 w-10 mb-3 text-gray-300" />
              <p class="text-sm">Select an approved expense report on the left</p>
            </CardContent>
          </Card>

          <Card v-else>
            <CardHeader>
              <div class="flex items-start justify-between">
                <div>
                  <CardTitle class="text-base">{{ selectedExpenseReport.expense_id ?? `#${selectedExpenseReport.id}` }} — {{ selectedExpenseReport.title }}</CardTitle>
                  <p class="text-sm text-gray-500 mt-0.5">{{ selectedExpenseReport.employee_name }} · {{ selectedExpenseReport.items?.length ?? 0 }} item(s)</p>
                </div>
                <p class="text-lg font-bold text-purple-700">{{ fmtCurrency(selectedExpenseReport.total_amount) }}</p>
              </div>
            </CardHeader>
            <CardContent class="space-y-4">

              <!-- Items summary -->
              <div class="bg-gray-50 rounded-lg p-3 space-y-1 text-sm max-h-40 overflow-y-auto">
                <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Expense Items</p>
                <div v-for="item in selectedExpenseReport.items" :key="item.id" class="flex justify-between text-gray-700">
                  <span class="truncate mr-2">{{ item.description }}</span>
                  <span class="font-medium whitespace-nowrap">{{ fmtCurrency(item.eur_amount ?? item.amount) }}</span>
                </div>
              </div>

              <!-- Bank transaction picker -->
              <div>
                <p class="text-sm font-medium text-gray-700 mb-1.5">Link to Bank Transfer</p>
                <div class="relative mb-2">
                  <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    v-model="expTxSearch"
                    type="text"
                    placeholder="Filter transactions…"
                    class="w-full pl-9 pr-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div v-if="expTxLoading" class="text-center py-4 text-gray-400 text-sm">Loading…</div>
                <div v-else-if="!filteredExpTxs.length" class="text-center py-6 text-gray-400 text-sm">No unreconciled transactions in range.</div>
                <div v-else class="max-h-52 overflow-y-auto border border-gray-200 rounded-lg divide-y">
                  <label
                    v-for="tx in filteredExpTxs"
                    :key="tx.id"
                    class="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                    :class="selectedExpTxId === tx.id ? 'bg-purple-50' : ''"
                  >
                    <input v-model="selectedExpTxId" type="radio" :value="tx.id" class="accent-purple-600" />
                    <div class="flex-1 min-w-0">
                      <p class="text-xs text-gray-500">{{ new Date(tx.transaction_date).toLocaleDateString() }}</p>
                      <p class="text-sm text-gray-800 truncate">{{ tx.description }}</p>
                    </div>
                    <span
                      class="text-sm font-semibold flex-shrink-0"
                      :class="tx.amount < 0 ? 'text-red-600' : 'text-emerald-600'"
                    >{{ formatCurrency(tx.amount) }}</span>
                  </label>
                </div>
              </div>

              <!-- Submit row -->
              <div class="flex items-center justify-between pt-3 border-t">
                <div>
                  <p v-if="expSuccess" class="text-sm font-medium text-emerald-600">{{ expSuccess }}</p>
                  <p v-if="expError" class="text-sm font-medium text-red-600">{{ expError }}</p>
                </div>
                <div class="flex gap-2">
                  <Button variant="outline" @click="resetExpense">Cancel</Button>
                  <Button
                    class="bg-purple-600 hover:bg-purple-700"
                    :disabled="expLoading || !selectedExpTxId"
                    @click="submitExpenseReconcile"
                  >
                    {{ expLoading ? 'Saving…' : 'Mark as Paid' }}
                  </Button>
                </div>
              </div>

            </CardContent>
          </Card>
        </div>
      </div>
    </template>
    <!-- ── END Expense mode ───────────────────────────────────────────────── -->

  </div>
</template>
