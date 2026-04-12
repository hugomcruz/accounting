<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { FileText, CheckCircle, Clock, X, ExternalLink, Upload, ClipboardList, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { invoicesApi, bankApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'
import type { Invoice } from '@/types'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const isAccountant = computed(() => auth.isAccountant)
const search = ref('')

const PAGE_SIZE = 50
const page = ref(1)

const now = new Date()
const selectedYear = ref(now.getFullYear())
const selectedMonth = ref(now.getMonth() + 1) // 1-12, 0 = all

const YEAR_RANGE = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i)
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

function monthBounds(): { start: string; end: string } | null {
  if (!selectedMonth.value) return null
  const y = selectedYear.value
  const m = selectedMonth.value
  const start = new Date(y, m - 1, 1)
  const end = new Date(y, m, 0, 23, 59, 59)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

const bounds = computed(() => monthBounds())

const { data: invoicesData, isLoading } = useQuery({
  queryKey: computed(() => ['invoices', 'purchase', selectedYear.value, selectedMonth.value, page.value, search.value]),
  queryFn: async () => {
    const params: Record<string, unknown> = {
      invoice_type: 'purchase',
      limit: PAGE_SIZE,
      skip: (page.value - 1) * PAGE_SIZE,
      order_by: 'invoice_date',
    }
    if (bounds.value) {
      params.start_date = bounds.value.start
      params.end_date = bounds.value.end
    }
    const response = await invoicesApi.getAll(params as any)
    return response.data as Invoice[]
  },
})

const filteredInvoices = computed(() => {
  const all = invoicesData.value ?? []
  if (!search.value) return all
  const q = search.value.toLowerCase()
  return all.filter((inv: Invoice) =>
    inv.invoice_number?.toLowerCase().includes(q) ||
    inv.supplier_name?.toLowerCase().includes(q) ||
    String(inv.total_amount).includes(q)
  )
})

const hasNextPage = computed(() => (invoicesData.value?.length ?? 0) === PAGE_SIZE)

function setMonth(m: number) {
  selectedMonth.value = m
  page.value = 1
}
function setYear(y: number) {
  selectedYear.value = y
  page.value = 1
}
function onSearch() { page.value = 1 }

const showTxModal = ref(false)
const txLoading = ref(false)
const txData = ref<Record<string, unknown> | null>(null)
const activeTxInvoiceId = ref<number | null>(null)

async function openTxModal(bankTransactionId: number, invoiceId: number) {
  showTxModal.value = true
  txLoading.value = true
  txData.value = null
  activeTxInvoiceId.value = invoiceId
  try {
    const res = await bankApi.getTransaction(bankTransactionId)
    txData.value = res.data
  } finally {
    txLoading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between flex-wrap gap-4">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">{{ t('invoices.purchasesTitle') }}</h1>
        <p class="mt-2 text-gray-600">{{ t('invoices.purchasesSubtitle') }}</p>
      </div>
      <div v-if="!isAccountant" class="flex items-center gap-3">
        <Button variant="outline" @click="router.push('/upload')">
          <Upload class="h-4 w-4 mr-2" />
          {{ t('nav.upload') }}
        </Button>
        <Button variant="outline" @click="router.push('/invoices/review')">
          <ClipboardList class="h-4 w-4 mr-2" />
          {{ t('nav.bulkInvoices') }}
        </Button>
      </div>
    </div>

    <Card>
      <CardHeader>
        <div class="flex items-center justify-between flex-wrap gap-3">
          <CardTitle>{{ t('invoices.purchasesTitle') }}</CardTitle>
          <div class="flex items-center gap-2 flex-wrap">
            <select
              :value="selectedYear"
              @change="setYear(Number(($event.target as HTMLSelectElement).value))"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option v-for="y in YEAR_RANGE" :key="y" :value="y">{{ y }}</option>
            </select>
            <select
              :value="selectedMonth"
              @change="setMonth(Number(($event.target as HTMLSelectElement).value))"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option :value="0">{{ t('invoices.allMonths') }}</option>
              <option v-for="m in MONTHS" :key="m" :value="m">
                {{ new Date(selectedYear, m - 1).toLocaleString('default', { month: 'long' }) }}
              </option>
            </select>
            <input
              v-model="search"
              type="text"
              :placeholder="t('invoices.searchPlaceholder')"
              @input="onSearch"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>

        <div v-else-if="filteredInvoices.length === 0" class="text-center py-12">
          <FileText class="mx-auto h-12 w-12 text-gray-400" />
          <h3 class="mt-2 text-sm font-medium text-gray-900">{{ t('invoices.noInvoices') }}</h3>
          <p class="mt-1 text-sm text-gray-500">{{ t('invoices.noInvoicesDesc') }}</p>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableDate') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableSupplier') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableInvoiceNumber') }}</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableAmount') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableStatus') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableFile') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableReconciled') }}</th>
                <th class="px-6 py-3" />
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr
                v-for="invoice in filteredInvoices"
                :key="invoice.id"
                class="hover:bg-gray-50 cursor-pointer transition-colors"
                @click="router.push(`/invoices/${invoice.id}`)"
              >
                <td class="px-6 py-4 text-sm text-gray-500">{{ formatDate(invoice.invoice_date) }}</td>
                <td class="px-6 py-4 text-sm text-gray-700">{{ invoice.supplier_name ?? '-' }}</td>
                <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ invoice.invoice_number }}</td>
                <td class="px-6 py-4 text-sm font-medium text-gray-900 text-right">{{ formatCurrency(invoice.total_amount) }}</td>
                <td class="px-6 py-4 text-sm text-gray-500 capitalize">{{ invoice.status ?? '-' }}</td>
                <td class="px-6 py-4 text-sm">
                  <span v-if="invoice.file_path" class="inline-flex items-center gap-1 text-green-700">
                    <FileText class="h-4 w-4" />
                    <span class="text-xs">{{ t('invoices.fileAttached') }}</span>
                  </span>
                  <span v-else class="text-xs text-gray-400">—</span>
                </td>
                <td class="px-6 py-4 text-sm" @click.stop>
                  <button
                    v-if="invoice.is_reconciled && invoice.bank_transaction_id && !invoice.is_partial"
                    class="flex items-center gap-1.5 text-green-700 hover:text-green-900 transition-colors"
                    @click="openTxModal(invoice.bank_transaction_id!, invoice.id)"
                  >
                    <CheckCircle class="h-4 w-4 text-green-500 flex-shrink-0" />
                    <span class="text-xs font-medium hover:underline">{{ t('invoices.reconcileView') }}</span>
                  </button>
                  <button
                    v-else-if="invoice.is_partial && invoice.bank_transaction_id"
                    class="flex flex-col gap-0.5 text-left"
                    @click="openTxModal(invoice.bank_transaction_id!, invoice.id)"
                  >
                    <span class="flex items-center gap-1 text-amber-700 hover:text-amber-900 transition-colors">
                      <CheckCircle class="h-4 w-4 flex-shrink-0" />
                      <span class="text-xs font-medium hover:underline">{{ t('invoices.reconcilePartial') }}</span>
                    </span>
                    <span class="text-xs text-amber-600">{{ formatCurrency(invoice.reconciled_amount ?? 0) }} / {{ formatCurrency(invoice.total_amount) }}</span>
                  </button>
                  <span v-else class="flex items-center gap-1.5 text-gray-400">
                    <Clock class="h-4 w-4" />
                    <span class="text-xs">{{ t('invoices.reconcilePending') }}</span>
                  </span>
                </td>
                <td class="px-4 py-4 text-right" @click.stop>
                  <a
                    :href="`/invoices/${invoice.id}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center justify-center p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
                    :title="t('invoices.openInNewTab')"
                  >
                    <ExternalLink class="h-4 w-4" />
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="!isLoading && filteredInvoices.length > 0" class="flex items-center justify-between px-2 pt-4 border-t border-gray-100">
          <span class="text-sm text-gray-500">{{ t('invoices.page') }} {{ page }}</span>
          <div class="flex gap-2">
            <Button variant="outline" size="sm" :disabled="page === 1" @click="page--">
              <ChevronLeft class="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" :disabled="!hasNextPage" @click="page++">
              <ChevronRight class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>

  <!-- Bank Transaction Modal -->
  <Teleport to="body">
    <div v-if="showTxModal" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/50" @click="showTxModal = false" />
      <div class="relative z-10 bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div class="flex items-center justify-between px-6 py-4 border-b">
          <h2 class="text-lg font-semibold text-gray-900">{{ t('invoices.bankTxModal.title') }}</h2>
          <button class="p-1 rounded hover:bg-gray-100 transition-colors" @click="showTxModal = false">
            <X class="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div class="px-6 py-5">
          <div v-if="txLoading" class="text-center py-8 text-gray-400">{{ t('common.loading') }}</div>
          <div v-else-if="txData" class="space-y-4">
            <div class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.date') }}</p>
                <p class="font-medium text-gray-900">{{ formatDate(String(txData.transaction_date)) }}</p>
              </div>
              <div>
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.amount') }}</p>
                <p
                  class="font-semibold text-base"
                  :class="Number(txData.amount) >= 0 ? 'text-emerald-600' : 'text-red-600'"
                >
                  {{ formatCurrency(Number(txData.amount)) }}
                </p>
              </div>
              <div class="col-span-2">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.description') }}</p>
                <p class="font-medium text-gray-900">{{ txData.description }}</p>
              </div>
              <div v-if="txData.category">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('invoices.bankTxModal.category') }}</p>
                <p class="font-medium text-gray-900 capitalize">{{ txData.category }}</p>
              </div>
              <div v-if="txData.balance_after !== null && txData.balance_after !== undefined">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('invoices.bankTxModal.balanceAfter') }}</p>
                <p class="font-medium text-gray-900">{{ formatCurrency(Number(txData.balance_after)) }}</p>
              </div>
              <div v-if="txData.value_date">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('invoices.bankTxModal.valueDate') }}</p>
                <p class="font-medium text-gray-900">{{ formatDate(String(txData.value_date)) }}</p>
              </div>
              <div v-if="txData.notes" class="col-span-2">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.notes') }}</p>
                <p class="text-gray-900">{{ txData.notes }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-center py-8 text-gray-400">{{ t('invoices.bankTxModal.couldNotLoad') }}</p>
        </div>
        <div class="flex justify-between items-center px-6 py-4 border-t bg-gray-50">
          <router-link
            v-if="txData"
            :to="`/invoices/${activeTxInvoiceId}`"
            class="text-sm text-primary-700 hover:text-primary-900 font-medium"
            @click="showTxModal = false"
          >
            {{ t('invoices.bankTxModal.openInvoice') }}
          </router-link>
          <div class="flex items-center gap-3 ml-auto">
            <router-link
              v-if="txData?.id"
              :to="`/bank?highlight=${txData.id}`"
              class="inline-flex items-center gap-1.5 text-sm text-emerald-700 hover:text-emerald-900 font-medium"
              @click="showTxModal = false"
            >
              <ExternalLink class="h-4 w-4" />
              {{ t('invoices.bankTxModal.openInBank') }}
            </router-link>
            <Button variant="outline" @click="showTxModal = false">{{ t('common.close') }}</Button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
