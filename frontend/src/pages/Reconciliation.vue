<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { RefreshCw, CheckCircle, AlertCircle, Link, Banknote, User, Receipt } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { bankApi, invoicesApi, expensesApi } from '@/services/queries'
import { formatCurrency } from '@/lib/utils'

const { t } = useI18n()
const queryClient = useQueryClient()

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

const selectedYear = ref(String(currentYear))
const selectedMonth = ref(String(currentMonth).padStart(2, '0'))

const months = [
  { value: '01', label: 'January' }, { value: '02', label: 'February' },
  { value: '03', label: 'March' }, { value: '04', label: 'April' },
  { value: '05', label: 'May' }, { value: '06', label: 'June' },
  { value: '07', label: 'July' }, { value: '08', label: 'August' },
  { value: '09', label: 'September' }, { value: '10', label: 'October' },
  { value: '11', label: 'November' }, { value: '12', label: 'December' },
]

const invoiceDateParams = computed(() => {
  const y = Number(selectedYear.value)
  const m = Number(selectedMonth.value)
  const start = new Date(y, m - 1, 1)
  const end = new Date(y, m, 0)
  return {
    start_date: start.toISOString().split('T')[0],
    end_date: end.toISOString().split('T')[0],
    limit: 500,
  }
})

const bankDateParams = computed(() => ({
  year: Number(selectedYear.value),
  month: Number(selectedMonth.value),
  limit: 500,
}))

const { data: invoices } = useQuery({
  queryKey: ['invoices-reconciliation', invoiceDateParams],
  queryFn: async () => (await invoicesApi.getAll(invoiceDateParams.value)).data,
})

const { data: bankTransactions } = useQuery({
  queryKey: ['bank-tx-reconciliation', bankDateParams],
  queryFn: async () => (await bankApi.getTransactions(bankDateParams.value)).data,
})

const { data: statements } = useQuery({
  queryKey: ['bank-statements-list'],
  queryFn: async () => (await bankApi.getStatements()).data,
})

// Paid expense reports for the selected period
const expenseReportParams = computed(() => ({
  status: 'paid',
}))
const { data: paidExpenseReports } = useQuery({
  queryKey: ['expense-reports-paid', expenseReportParams],
  queryFn: async () => {
    const res = await expensesApi.listReports(expenseReportParams.value)
    return res.data as any[]
  },
})

// Invoice IDs that belong to expense items (reconciled via expense report)
const expenseInvoiceIds = computed(() => {
  const ids = new Set<number>()
  for (const report of paidExpenseReports.value ?? []) {
    for (const item of report.items ?? []) {
      if (item.invoice_id) ids.add(item.invoice_id)
    }
  }
  return ids
})

const reconciledInvoiceIds = computed(() => {
  const ids = new Set<number>()
  for (const tx of bankTransactions.value ?? []) {
    if (tx.is_reconciled && tx.invoice_id) ids.add(tx.invoice_id)
  }
  return ids
})

const unreconciledInvoices = computed(() =>
  (invoices.value ?? []).filter((inv: any) =>
    !reconciledInvoiceIds.value.has(inv.id) &&
    !inv.is_reconciled &&
    !expenseInvoiceIds.value.has(inv.id)
  )
)
const reconciledInvoices = computed(() =>
  (invoices.value ?? []).filter((inv: any) =>
    (reconciledInvoiceIds.value.has(inv.id) || inv.is_reconciled) &&
    !expenseInvoiceIds.value.has(inv.id)
  )
)
const unreconciledTxs = computed(() =>
  (bankTransactions.value ?? []).filter((tx: any) => !tx.is_reconciled)
)
const reconciledTxs = computed(() =>
  (bankTransactions.value ?? []).filter((tx: any) => tx.is_reconciled)
)

function linkedTransaction(invoiceId: number) {
  return (bankTransactions.value ?? []).find(
    (tx: any) => tx.invoice_id === invoiceId && tx.is_reconciled
  )
}

const reconcileMutation = useMutation({
  mutationFn: async (statementId: number) => bankApi.reconcileStatement(statementId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoices-reconciliation'] })
    queryClient.invalidateQueries({ queryKey: ['bank-tx-reconciliation'] })
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
  },
})

async function autoReconcileAll() {
  if (!statements.value?.length) return
  for (const stmt of statements.value) {
    await reconcileMutation.mutateAsync(stmt.id)
  }
}

function companyName(inv: any) {
  return inv.supplier_name || inv.customer_name || '-'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">{{ t('reconciliation.title') }}</h1>
        <p class="mt-1 text-gray-500">{{ t('reconciliation.subtitle') }}</p>
      </div>
      <button
        :disabled="reconcileMutation.isPending.value"
        class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        @click="autoReconcileAll"
      >
        <RefreshCw class="h-4 w-4" :class="reconcileMutation.isPending.value ? 'animate-spin' : ''" />
        {{ reconcileMutation.isPending.value ? t('reconciliation.reconciling') : t('reconciliation.autoReconcileAll') }}
      </button>
    </div>

    <!-- Period selector -->
    <Card>
      <CardContent class="pt-4">
        <div class="flex items-center gap-4">
          <p class="text-sm font-medium text-gray-700">{{ t('reconciliation.periodLabel') }}</p>
          <select v-model="selectedMonth" class="px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option v-for="m in months" :key="m.value" :value="m.value">{{ t('common.months.' + m.label.toLowerCase()) }}</option>
          </select>
          <select v-model="selectedYear" class="px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
            <option v-for="y in [2026, 2025, 2024, 2023]" :key="y" :value="String(y)">{{ y }}</option>
          </select>
        </div>
      </CardContent>
    </Card>

    <!-- Summary stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('reconciliation.reconciledInvoices') }}</p>
          <p class="text-xl font-bold text-green-600 mt-1">{{ reconciledInvoices.length }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('reconciliation.unreconciledInvoices') }}</p>
          <p class="text-xl font-bold text-amber-600 mt-1">{{ unreconciledInvoices.length }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('reconciliation.reconciledTransactions') }}</p>
          <p class="text-xl font-bold text-green-600 mt-1">{{ reconciledTxs.length }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('reconciliation.unreconciledTransactions') }}</p>
          <p class="text-xl font-bold text-amber-600 mt-1">{{ unreconciledTxs.length }}</p>
        </CardContent>
      </Card>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Unreconciled Invoices -->
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <AlertCircle class="h-4 w-4 text-amber-500" />
            {{ t('reconciliation.unreconciledInvoicesCard') }}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="!unreconciledInvoices.length" class="text-center py-4 text-gray-400">{{ t('reconciliation.allReconciled') }}</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-500">
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableNumber') }}</th>
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableDate') }}</th>
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableCompany') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('reconciliation.tableAmount') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="inv in unreconciledInvoices" :key="inv.id" class="border-b last:border-0 hover:bg-gray-50">
                  <td class="py-2.5 font-mono text-xs">{{ inv.invoice_number }}</td>
                  <td class="py-2.5">{{ inv.invoice_date ? new Date(inv.invoice_date).toLocaleDateString() : '-' }}</td>
                  <td class="py-2.5 text-xs truncate max-w-[120px]">{{ companyName(inv) }}</td>
                  <td class="py-2.5 text-right font-medium">€{{ Number(inv.total_amount || 0).toFixed(2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <!-- Reconciled Pairs -->
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <CheckCircle class="h-4 w-4 text-green-500" />
            {{ t('reconciliation.reconciledPairs') }}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="!reconciledInvoices.length" class="text-center py-4 text-gray-400">{{ t('reconciliation.noReconciled') }}</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-500">
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableInvoice') }}</th>
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableDate') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('reconciliation.tableAmount') }}</th>
                  <th class="pb-2 font-medium">{{ t('reconciliation.tableMatch') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="inv in reconciledInvoices" :key="inv.id" class="border-b last:border-0 hover:bg-gray-50">
                  <td class="py-2.5 font-mono text-xs">{{ inv.invoice_number }}</td>
                  <td class="py-2.5">{{ inv.invoice_date ? new Date(inv.invoice_date).toLocaleDateString() : '-' }}</td>
                  <td class="py-2.5 text-right font-medium">€{{ Number(inv.total_amount || 0).toFixed(2) }}</td>
                  <td class="py-2.5 text-xs text-gray-500 truncate max-w-[140px]">
                    <span v-if="linkedTransaction(inv.id)" class="flex items-center gap-1">
                      <Link class="h-3 w-3 text-green-500 flex-shrink-0" />
                      {{ new Date(linkedTransaction(inv.id).transaction_date).toLocaleDateString() }}
                      · €{{ Math.abs(linkedTransaction(inv.id).amount).toFixed(2) }}
                    </span>
                    <span v-else-if="inv.reconciliation_method === 'cash'" class="flex items-center gap-1 text-emerald-600">
                      <Banknote class="h-3 w-3 flex-shrink-0" /> Cash
                    </span>
                    <span v-else-if="inv.reconciliation_method === 'employee'" class="flex items-center gap-1 text-purple-600">
                      <User class="h-3 w-3 flex-shrink-0" /> Employee
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Unreconciled Bank Transactions -->
    <Card v-if="unreconciledTxs.length">
      <CardHeader><CardTitle>{{ t('reconciliation.unreconciledBankCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('reconciliation.tableDate') }}</th>
                <th class="pb-2 font-medium">{{ t('reconciliation.tableDescription') }}</th>
                <th class="pb-2 font-medium">{{ t('common.category') }}</th>
                <th class="pb-2 font-medium text-right">{{ t('reconciliation.tableAmount') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in unreconciledTxs" :key="tx.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-2 whitespace-nowrap">{{ new Date(tx.transaction_date).toLocaleDateString() }}</td>
                <td class="py-2 text-xs text-gray-700 max-w-xs truncate">{{ tx.description }}</td>
                <td class="py-2 text-xs">{{ tx.category || '-' }}</td>
                <td class="py-2 text-right font-medium" :class="tx.amount < 0 ? 'text-red-600' : 'text-green-600'">
                  €{{ Number(tx.amount).toFixed(2) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>

    <!-- Paid Expense Reports -->
    <Card v-if="paidExpenseReports?.length">
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <Receipt class="h-4 w-4 text-purple-500" />
          Expense Report Payments
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                <th class="pb-2 pr-4">Report ID</th>
                <th class="pb-2 pr-4">Employee</th>
                <th class="pb-2 pr-4">Title</th>
                <th class="pb-2 pr-4">Items</th>
                <th class="pb-2 pr-4 text-right">Total</th>
                <th class="pb-2">Paid</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in paidExpenseReports" :key="r.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-2.5 pr-4 font-mono text-xs text-gray-500">{{ r.expense_id ?? `#${r.id}` }}</td>
                <td class="py-2.5 pr-4 text-gray-700 text-xs">{{ r.employee_name ?? '—' }}</td>
                <td class="py-2.5 pr-4 text-gray-800 truncate max-w-[180px]">{{ r.title }}</td>
                <td class="py-2.5 pr-4 text-gray-500 text-xs">{{ r.items?.length ?? 0 }} invoice(s)</td>
                <td class="py-2.5 pr-4 text-right font-semibold text-purple-700">
                  €{{ Number(r.total_amount).toFixed(2) }}
                </td>
                <td class="py-2.5 text-xs text-gray-500 whitespace-nowrap">
                  <span class="flex items-center gap-1">
                    <CheckCircle class="h-3 w-3 text-green-500 flex-shrink-0" />
                    {{ r.paid_at ? new Date(r.paid_at).toLocaleDateString() : '—' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
