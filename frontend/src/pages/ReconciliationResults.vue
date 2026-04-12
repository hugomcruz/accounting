<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  CreditCard, Receipt, FileText, ChevronRight, Loader2, ArrowRight, ExternalLink,
} from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { bankApi, invoicesApi, expensesApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'

const { t } = useI18n()
const router = useRouter()

// ── View mode ───────────────────────────────────────────────────────────────
type ViewMode = 'bank' | 'invoice' | 'expensereport'
const viewMode = ref<ViewMode>('bank')

// ── Tree pattern ────────────────────────────────────────────────────────────
type TreePattern =
  | 'bank-er-invoices'
  | 'bank-invoice'
  | 'invoice-er-bank'
  | 'invoice-bank'
  | 'er-bank-invoices'

interface TreeState {
  pattern: TreePattern | null
  bankTx: any | null
  expenseReport: any | null
  selectedInvoice: any | null
}

// ── Data queries ────────────────────────────────────────────────────────────
const { data: reconciledTxsData, isLoading: loadingTxs } = useQuery({
  queryKey: ['reconciled-bank-transactions'],
  queryFn: async () => (await bankApi.getTransactions({ is_reconciled: true, limit: 500 })).data,
})

const { data: reconciledInvoicesData, isLoading: loadingInvoices } = useQuery({
  queryKey: ['reconciled-invoices'],
  queryFn: async () => (await invoicesApi.getAll({ reconciled_only: true, limit: 500 })).data,
})

const { data: paidExpenseReportsData, isLoading: loadingERs } = useQuery({
  queryKey: ['paid-expense-reports'],
  queryFn: async () => (await expensesApi.listReports({ status: 'paid' })).data,
})

// ── Search ──────────────────────────────────────────────────────────────────
const searchQuery = ref('')

const filteredTxs = computed(() => {
  const list: any[] = reconciledTxsData.value ?? []
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter(tx =>
    (tx.description ?? '').toLowerCase().includes(q) ||
    (tx.account_name ?? '').toLowerCase().includes(q),
  )
})

const filteredInvoices = computed(() => {
  const list: any[] = reconciledInvoicesData.value ?? []
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter(inv =>
    (inv.invoice_number ?? '').toLowerCase().includes(q) ||
    (inv.supplier_name ?? inv.customer_name ?? '').toLowerCase().includes(q),
  )
})

const filteredERs = computed(() => {
  const list: any[] = paidExpenseReportsData.value ?? []
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter(er =>
    (er.expense_id ?? '').toLowerCase().includes(q) ||
    (er.title ?? '').toLowerCase().includes(q) ||
    (er.employee_name ?? '').toLowerCase().includes(q),
  )
})

// ── Selection & tree state ──────────────────────────────────────────────────
const selectedId = ref<number | null>(null)
const detailLoading = ref(false)
const tree = ref<TreeState>({ pattern: null, bankTx: null, expenseReport: null, selectedInvoice: null })

function clearTree() {
  selectedId.value = null
  tree.value = { pattern: null, bankTx: null, expenseReport: null, selectedInvoice: null }
}

// ── Select bank transaction ─────────────────────────────────────────────────
async function selectBankTx(tx: any) {
  if (selectedId.value === tx.id) return
  selectedId.value = tx.id
  detailLoading.value = true
  tree.value = { pattern: null, bankTx: null, expenseReport: null, selectedInvoice: null }
  try {
    if (tx.expense_report_id) {
      const erRes = await expensesApi.getReport(tx.expense_report_id)
      tree.value = { pattern: 'bank-er-invoices', bankTx: tx, expenseReport: erRes.data, selectedInvoice: null }
      return
    }
    if (tx.invoice_id) {
      const invRes = await invoicesApi.getById(tx.invoice_id)
      const inv = invRes.data as any
      if (inv.expense_report?.id) {
        const erRes = await expensesApi.getReport(inv.expense_report.id)
        tree.value = { pattern: 'bank-er-invoices', bankTx: tx, expenseReport: erRes.data, selectedInvoice: inv }
      } else {
        tree.value = { pattern: 'bank-invoice', bankTx: tx, expenseReport: null, selectedInvoice: inv }
      }
      return
    }
    tree.value = { pattern: 'bank-invoice', bankTx: tx, expenseReport: null, selectedInvoice: null }
  } finally {
    detailLoading.value = false
  }
}

// ── Select invoice ──────────────────────────────────────────────────────────
async function selectInvoice(inv: any) {
  if (selectedId.value === inv.id) return
  selectedId.value = inv.id
  detailLoading.value = true
  tree.value = { pattern: null, bankTx: null, expenseReport: null, selectedInvoice: null }
  try {
    const invRes = await invoicesApi.getById(inv.id)
    const fullInv = invRes.data as any
    if (fullInv.expense_report?.id) {
      const erRes = await expensesApi.getReport(fullInv.expense_report.id)
      const er = erRes.data as any
      let bankTx = null
      if (er.bank_transaction_id) {
        const txRes = await bankApi.getTransaction(er.bank_transaction_id)
        bankTx = txRes.data
      }
      tree.value = { pattern: 'invoice-er-bank', bankTx, expenseReport: er, selectedInvoice: fullInv }
    } else {
      let bankTx = null
      if (fullInv.bank_transaction_id) {
        const txRes = await bankApi.getTransaction(fullInv.bank_transaction_id)
        bankTx = txRes.data
      }
      tree.value = { pattern: 'invoice-bank', bankTx, expenseReport: null, selectedInvoice: fullInv }
    }
  } finally {
    detailLoading.value = false
  }
}

// ── Select expense report ───────────────────────────────────────────────────
async function selectExpenseReport(er: any) {
  if (selectedId.value === er.id) return
  selectedId.value = er.id
  detailLoading.value = true
  tree.value = { pattern: null, bankTx: null, expenseReport: null, selectedInvoice: null }
  try {
    const erRes = await expensesApi.getReport(er.id)
    const fullEr = erRes.data as any
    let bankTx = null
    if (fullEr.bank_transaction_id) {
      const txRes = await bankApi.getTransaction(fullEr.bank_transaction_id)
      bankTx = txRes.data
    }
    tree.value = { pattern: 'er-bank-invoices', bankTx, expenseReport: fullEr, selectedInvoice: null }
  } finally {
    detailLoading.value = false
  }
}

// ── Mode switch ─────────────────────────────────────────────────────────────
function switchMode(mode: ViewMode) {
  viewMode.value = mode
  searchQuery.value = ''
  clearTree()
}

const isListLoading = computed(() => {
  if (viewMode.value === 'bank') return loadingTxs.value
  if (viewMode.value === 'invoice') return loadingInvoices.value
  return loadingERs.value
})

function erLabel(er: any): string {
  return er?.expense_id || `ER-${er?.id}`
}

function erItems(er: any): any[] {
  return er?.items ?? []
}

function siblingItems(er: any, selectedInv: any): any[] {
  return erItems(er).filter((item: any) => item.invoice_id !== selectedInv?.id)
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('reconciliation.resultsTitle') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('reconciliation.resultsSubtitle') }}</p>
    </div>

    <!-- Mode tabs -->
    <div class="flex gap-2 flex-wrap">
      <Button :variant="viewMode === 'bank' ? 'default' : 'outline'" size="sm" @click="switchMode('bank')">
        <CreditCard class="mr-1.5 h-3.5 w-3.5" />{{ t('reconciliation.byBankTx') }}
      </Button>
      <Button :variant="viewMode === 'invoice' ? 'default' : 'outline'" size="sm" @click="switchMode('invoice')">
        <Receipt class="mr-1.5 h-3.5 w-3.5" />{{ t('reconciliation.byInvoice') }}
      </Button>
      <Button :variant="viewMode === 'expensereport' ? 'default' : 'outline'" size="sm" @click="switchMode('expensereport')">
        <FileText class="mr-1.5 h-3.5 w-3.5" />{{ t('reconciliation.byExpenseReport') }}
      </Button>
    </div>

    <!-- Master-detail -->
    <div class="flex gap-4" style="min-height: 600px;">

      <!-- Left panel -->
      <Card class="flex flex-col overflow-hidden flex-none" style="width: 36%; max-height: calc(100vh - 220px);">
        <CardHeader class="flex-none border-b border-gray-100 pb-3">
          <CardTitle class="text-base">
            <span v-if="viewMode === 'bank'">{{ t('reconciliation.byBankTx') }}</span>
            <span v-else-if="viewMode === 'invoice'">{{ t('reconciliation.byInvoice') }}</span>
            <span v-else>{{ t('reconciliation.byExpenseReport') }}</span>
          </CardTitle>
          <input v-model="searchQuery" type="text" :placeholder="t('reconciliation.searchPlaceholder')"
            class="mt-2 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </CardHeader>

        <CardContent class="flex-1 overflow-y-auto p-0">
          <div v-if="isListLoading" class="flex justify-center p-8">
            <Loader2 class="h-6 w-6 animate-spin text-gray-400" />
          </div>

          <!-- Bank tx list -->
          <template v-else-if="viewMode === 'bank'">
            <div v-for="tx in filteredTxs" :key="tx.id" @click="selectBankTx(tx)"
              :class="['list-row border-l-[3px]', selectedId === tx.id ? 'bg-blue-50 border-l-blue-500' : 'border-l-transparent']">
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 truncate">{{ tx.description }}</p>
                <p class="text-xs text-gray-400 mt-0.5 flex items-center gap-1 flex-wrap">
                  <span>{{ formatDate(tx.transaction_date) }}</span>
                  <span v-if="tx.account_name"> · {{ tx.account_name }}</span>
                  <span v-if="tx.expense_report_id" class="tag-badge bg-orange-100 text-orange-700">ER</span>
                  <span v-else-if="tx.invoice_id" class="tag-badge bg-green-100 text-green-700">INV</span>
                </p>
              </div>
              <div class="flex items-center gap-1 ml-2 flex-none">
                <span :class="tx.amount < 0 ? 'text-red-600' : 'text-green-600'" class="text-sm font-semibold">
                  {{ formatCurrency(Math.abs(tx.amount)) }}
                </span>
                <ChevronRight class="h-3.5 w-3.5 text-gray-300" />
              </div>
            </div>
            <div v-if="filteredTxs.length === 0" class="list-empty">{{ t('reconciliation.noReconciliations') }}</div>
          </template>

          <!-- Invoice list -->
          <template v-else-if="viewMode === 'invoice'">
            <div v-for="inv in filteredInvoices" :key="inv.id" @click="selectInvoice(inv)"
              :class="['list-row border-l-[3px]', selectedId === inv.id ? 'bg-blue-50 border-l-blue-500' : 'border-l-transparent']">
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 truncate">{{ inv.invoice_number }}</p>
                <p class="text-xs text-gray-400 mt-0.5">
                  {{ inv.supplier_name ?? inv.customer_name ?? '—' }} · {{ formatDate(inv.invoice_date) }}
                </p>
              </div>
              <div class="flex items-center gap-1 ml-2 flex-none">
                <span class="text-sm font-semibold">{{ formatCurrency(inv.total_amount) }}</span>
                <ChevronRight class="h-3.5 w-3.5 text-gray-300" />
              </div>
            </div>
            <div v-if="filteredInvoices.length === 0" class="list-empty">{{ t('reconciliation.noReconciliations') }}</div>
          </template>

          <!-- Expense report list -->
          <template v-else>
            <div v-for="er in filteredERs" :key="er.id" @click="selectExpenseReport(er)"
              :class="['list-row border-l-[3px]', selectedId === er.id ? 'bg-blue-50 border-l-blue-500' : 'border-l-transparent']">
              <div class="flex-1 min-w-0">
                <p class="text-xs font-mono font-medium text-orange-600">{{ erLabel(er) }}</p>
                <p class="text-sm font-medium text-gray-900 truncate">{{ er.title }}</p>
                <p class="text-xs text-gray-400 mt-0.5">{{ er.employee_name }}</p>
              </div>
              <div class="flex items-center gap-1 ml-2 flex-none">
                <span class="text-sm font-semibold">{{ formatCurrency(er.total_amount) }}</span>
                <ChevronRight class="h-3.5 w-3.5 text-gray-300" />
              </div>
            </div>
            <div v-if="filteredERs.length === 0" class="list-empty">{{ t('reconciliation.noReconciliations') }}</div>
          </template>
        </CardContent>
      </Card>

      <!-- Right panel: tree chart -->
      <Card class="flex-1 flex flex-col overflow-hidden" style="max-height: calc(100vh - 220px);">
        <CardContent class="flex-1 overflow-y-auto p-6">

          <!-- Empty state -->
          <div v-if="!selectedId" class="flex flex-col items-center justify-center h-full gap-3 text-gray-300">
            <ArrowRight class="h-14 w-14" />
            <p class="text-sm text-gray-400">{{ t('reconciliation.selectToView') }}</p>
          </div>

          <!-- Loading -->
          <div v-else-if="detailLoading" class="flex justify-center p-12">
            <Loader2 class="h-6 w-6 animate-spin text-gray-400" />
          </div>

          <!-- Tree -->
          <div v-else-if="tree.pattern" class="max-w-2xl">

            <!-- PATTERN 1 & 2: BankTx as root -->
            <template v-if="tree.pattern === 'bank-er-invoices' || tree.pattern === 'bank-invoice'">
              <div class="n-card n-bank">
                <CreditCard class="n-icon" />
                <div class="n-body">
                  <div class="n-label">{{ t('reconciliation.bankTransaction') }}</div>
                  <div class="n-title">{{ tree.bankTx?.description }}</div>
                  <div class="n-sub">{{ formatDate(tree.bankTx?.transaction_date) }}<span v-if="tree.bankTx?.account_name"> · {{ tree.bankTx.account_name }}</span></div>
                </div>
                <span class="n-amount">{{ formatCurrency(Math.abs(tree.bankTx?.amount ?? 0)) }}</span>
              </div>

              <!-- via Expense Report -->
              <template v-if="tree.pattern === 'bank-er-invoices'">
                <div class="t-children">
                  <div class="t-vline" />
                  <div class="t-row">
                    <div class="t-tick" />
                    <div class="n-card n-er">
                      <FileText class="n-icon" />
                      <div class="n-body">
                        <div class="n-label">{{ t('reconciliation.expenseReport') }}</div>
                        <div class="n-title">{{ erLabel(tree.expenseReport) }} — {{ tree.expenseReport?.title }}</div>
                        <div class="n-sub">{{ tree.expenseReport?.employee_name }}</div>
                      </div>
                      <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/expenses/${tree.expenseReport?.id}`)">
                        <ExternalLink class="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div class="t-children ml-8" v-if="erItems(tree.expenseReport).length">
                    <div class="t-vline" />
                    <div v-for="item in erItems(tree.expenseReport)" :key="item.id" class="t-row">
                      <div class="t-tick" />
                      <div class="n-card n-invoice">
                        <Receipt class="n-icon" />
                        <div class="n-body">
                          <div class="n-label">{{ t('reconciliation.invoice') }}</div>
                          <div class="n-title">{{ item.invoice_number ?? item.description }}</div>
                          <div class="n-sub">{{ formatDate(item.invoice_date ?? item.expense_date) }}<span v-if="item.supplier_name"> · {{ item.supplier_name }}</span></div>
                        </div>
                        <span class="n-amount">{{ formatCurrency(item.eur_amount ?? item.amount) }}</span>
                        <Button v-if="item.invoice_id" variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${item.invoice_id}`)">
                          <ExternalLink class="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- direct Invoice -->
              <template v-else>
                <template v-if="tree.selectedInvoice">
                  <div class="t-children">
                    <div class="t-vline" />
                    <div class="t-row">
                      <div class="t-tick" />
                      <div class="n-card n-invoice">
                        <Receipt class="n-icon" />
                        <div class="n-body">
                          <div class="n-label">{{ t('reconciliation.invoice') }}</div>
                          <div class="n-title">{{ tree.selectedInvoice.invoice_number }}</div>
                          <div class="n-sub">{{ formatDate(tree.selectedInvoice.invoice_date) }}<span v-if="tree.selectedInvoice.supplier_name ?? tree.selectedInvoice.customer_name"> · {{ tree.selectedInvoice.supplier_name ?? tree.selectedInvoice.customer_name }}</span></div>
                        </div>
                        <span class="n-amount">{{ formatCurrency(tree.selectedInvoice.total_amount) }}</span>
                        <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${tree.selectedInvoice.id}`)">
                          <ExternalLink class="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </template>
                <p v-else class="mt-3 ml-4 text-sm text-gray-400 italic">{{ t('reconciliation.noLinkedInvoice') }}</p>
              </template>
            </template>

            <!-- PATTERN 3: Invoice* → ER → (BankTx + siblings) -->
            <template v-else-if="tree.pattern === 'invoice-er-bank'">
              <div class="n-card n-invoice n-selected">
                <Receipt class="n-icon" />
                <div class="n-body">
                  <div class="n-label">{{ t('reconciliation.invoice') }} · {{ t('reconciliation.selected') }}</div>
                  <div class="n-title">{{ tree.selectedInvoice?.invoice_number }}</div>
                  <div class="n-sub">{{ formatDate(tree.selectedInvoice?.invoice_date) }}<span v-if="tree.selectedInvoice?.supplier_name ?? tree.selectedInvoice?.customer_name"> · {{ tree.selectedInvoice?.supplier_name ?? tree.selectedInvoice?.customer_name }}</span></div>
                </div>
                <span class="n-amount">{{ formatCurrency(tree.selectedInvoice?.total_amount ?? 0) }}</span>
                <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${tree.selectedInvoice?.id}`)">
                  <ExternalLink class="h-3.5 w-3.5" />
                </Button>
              </div>

              <div class="t-children">
                <div class="t-vline" />
                <div class="t-row">
                  <div class="t-tick" />
                  <div class="n-card n-er">
                    <FileText class="n-icon" />
                    <div class="n-body">
                      <div class="n-label">{{ t('reconciliation.expenseReport') }}</div>
                      <div class="n-title">{{ erLabel(tree.expenseReport) }} — {{ tree.expenseReport?.title }}</div>
                      <div class="n-sub">{{ tree.expenseReport?.employee_name }}</div>
                    </div>
                    <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/expenses/${tree.expenseReport?.id}`)">
                      <ExternalLink class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                <div class="t-children ml-8">
                  <div class="t-vline" />
                  <div class="t-row" v-if="tree.bankTx">
                    <div class="t-tick" />
                    <div class="n-card n-bank">
                      <CreditCard class="n-icon" />
                      <div class="n-body">
                        <div class="n-label">{{ t('reconciliation.bankTransaction') }}</div>
                        <div class="n-title">{{ tree.bankTx.description }}</div>
                        <div class="n-sub">{{ formatDate(tree.bankTx.transaction_date) }}</div>
                      </div>
                      <span class="n-amount">{{ formatCurrency(Math.abs(tree.bankTx.amount)) }}</span>
                    </div>
                  </div>
                  <div v-for="item in siblingItems(tree.expenseReport, tree.selectedInvoice)" :key="item.id" class="t-row">
                    <div class="t-tick" />
                    <div class="n-card n-invoice-sibling">
                      <Receipt class="n-icon" />
                      <div class="n-body">
                        <div class="n-label">{{ t('reconciliation.invoice') }}</div>
                        <div class="n-title">{{ item.invoice_number ?? item.description }}</div>
                        <div class="n-sub">{{ formatDate(item.invoice_date ?? item.expense_date) }}<span v-if="item.supplier_name"> · {{ item.supplier_name }}</span></div>
                      </div>
                      <span class="n-amount">{{ formatCurrency(item.eur_amount ?? item.amount) }}</span>
                      <Button v-if="item.invoice_id" variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${item.invoice_id}`)">
                        <ExternalLink class="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <!-- PATTERN 4: Invoice → BankTx (direct) -->
            <template v-else-if="tree.pattern === 'invoice-bank'">
              <div class="n-card n-invoice n-selected">
                <Receipt class="n-icon" />
                <div class="n-body">
                  <div class="n-label">{{ t('reconciliation.invoice') }}</div>
                  <div class="n-title">{{ tree.selectedInvoice?.invoice_number }}</div>
                  <div class="n-sub">{{ formatDate(tree.selectedInvoice?.invoice_date) }}<span v-if="tree.selectedInvoice?.supplier_name ?? tree.selectedInvoice?.customer_name"> · {{ tree.selectedInvoice?.supplier_name ?? tree.selectedInvoice?.customer_name }}</span></div>
                </div>
                <span class="n-amount">{{ formatCurrency(tree.selectedInvoice?.total_amount ?? 0) }}</span>
                <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${tree.selectedInvoice?.id}`)">
                  <ExternalLink class="h-3.5 w-3.5" />
                </Button>
              </div>
              <template v-if="tree.bankTx">
                <div class="t-children">
                  <div class="t-vline" />
                  <div class="t-row">
                    <div class="t-tick" />
                    <div class="n-card n-bank">
                      <CreditCard class="n-icon" />
                      <div class="n-body">
                        <div class="n-label">{{ t('reconciliation.bankTransaction') }}</div>
                        <div class="n-title">{{ tree.bankTx.description }}</div>
                        <div class="n-sub">{{ formatDate(tree.bankTx.transaction_date) }}<span v-if="tree.bankTx?.account_name"> · {{ tree.bankTx.account_name }}</span></div>
                      </div>
                      <span class="n-amount">{{ formatCurrency(Math.abs(tree.bankTx.amount)) }}</span>
                    </div>
                  </div>
                </div>
              </template>
              <p v-else class="mt-3 ml-4 text-sm text-gray-400 italic">{{ t('reconciliation.noBankTx') }}</p>
            </template>

            <!-- PATTERN 5: ER → (BankTx + Items) -->
            <template v-else-if="tree.pattern === 'er-bank-invoices'">
              <div class="n-card n-er n-selected">
                <FileText class="n-icon" />
                <div class="n-body">
                  <div class="n-label">{{ t('reconciliation.expenseReport') }}</div>
                  <div class="n-title">{{ erLabel(tree.expenseReport) }} — {{ tree.expenseReport?.title }}</div>
                  <div class="n-sub">{{ tree.expenseReport?.employee_name }}</div>
                </div>
                <span class="n-amount">{{ formatCurrency(tree.expenseReport?.total_amount ?? 0) }}</span>
                <Button variant="ghost" size="sm" class="n-open" @click="router.push(`/expenses/${tree.expenseReport?.id}`)">
                  <ExternalLink class="h-3.5 w-3.5" />
                </Button>
              </div>

              <div class="t-children">
                <div class="t-vline" />
                <div class="t-row" v-if="tree.bankTx">
                  <div class="t-tick" />
                  <div class="n-card n-bank">
                    <CreditCard class="n-icon" />
                    <div class="n-body">
                      <div class="n-label">{{ t('reconciliation.bankTransaction') }}</div>
                      <div class="n-title">{{ tree.bankTx.description }}</div>
                      <div class="n-sub">{{ formatDate(tree.bankTx.transaction_date) }}<span v-if="tree.bankTx?.account_name"> · {{ tree.bankTx.account_name }}</span></div>
                    </div>
                    <span class="n-amount">{{ formatCurrency(Math.abs(tree.bankTx.amount)) }}</span>
                  </div>
                </div>
                <div v-for="item in erItems(tree.expenseReport)" :key="item.id" class="t-row">
                  <div class="t-tick" />
                  <div class="n-card n-invoice">
                    <Receipt class="n-icon" />
                    <div class="n-body">
                      <div class="n-label">{{ t('reconciliation.invoice') }}</div>
                      <div class="n-title">{{ item.invoice_number ?? item.description }}</div>
                      <div class="n-sub">{{ formatDate(item.invoice_date ?? item.expense_date) }}<span v-if="item.supplier_name"> · {{ item.supplier_name }}</span></div>
                    </div>
                    <span class="n-amount">{{ formatCurrency(item.eur_amount ?? item.amount) }}</span>
                    <Button v-if="item.invoice_id" variant="ghost" size="sm" class="n-open" @click="router.push(`/invoices/${item.invoice_id}`)">
                      <ExternalLink class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            </template>

          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.list-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; cursor: pointer;
  border-bottom: 1px solid #f3f4f6; transition: background 0.1s;
}
.list-row:hover { background: #eff6ff; }
.list-empty { padding: 40px 16px; text-align: center; font-size: 14px; color: #9ca3af; }
.tag-badge { display: inline-flex; align-items: center; border-radius: 9999px; padding: 1px 6px; font-size: 10px; font-weight: 600; }

.n-card {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  border-radius: 8px; border: 1px solid; border-left-width: 4px;
}
.n-bank            { background: #eff6ff; border-color: #bfdbfe; border-left-color: #3b82f6; }
.n-er              { background: #fff7ed; border-color: #fed7aa; border-left-color: #f97316; }
.n-invoice         { background: #f0fdf4; border-color: #bbf7d0; border-left-color: #22c55e; }
.n-invoice-sibling { background: #f9fafb; border-color: #e5e7eb; border-left-color: #9ca3af; }
.n-selected        { box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }

.n-icon  { flex-shrink: 0; width: 16px; height: 16px; opacity: 0.65; }
.n-body  { flex: 1; min-width: 0; }
.n-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.55; line-height: 1; margin-bottom: 2px; }
.n-title { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.n-sub   { font-size: 11px; opacity: 0.6; margin-top: 1px; }

.n-bank .n-label, .n-bank .n-title       { color: #1e3a8a; }
.n-er .n-label, .n-er .n-title           { color: #7c2d12; }
.n-invoice .n-label, .n-invoice .n-title { color: #14532d; }

.n-amount { font-size: 14px; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
.n-open   { flex-shrink: 0; padding: 0 6px; height: 28px; opacity: 0.5; }
.n-open:hover { opacity: 1; }

.t-children { position: relative; margin-left: 22px; padding-left: 22px; }
.t-vline    { position: absolute; left: 0; top: 8px; bottom: 16px; width: 2px; background: #d1d5db; }
.t-row      { position: relative; margin-top: 8px; }
.t-tick     { position: absolute; left: -22px; top: 21px; width: 22px; height: 2px; background: #d1d5db; }
</style>
