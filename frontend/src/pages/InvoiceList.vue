<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { FileText, CheckCircle, Clock, X, ExternalLink } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { invoicesApi, bankApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'

const { t } = useI18n()
const router = useRouter()
const filterType = ref('')
const search = ref('')

const { data: invoicesData, isLoading } = useQuery({
  queryKey: ['invoices', filterType],
  queryFn: async () => {
    const params: Record<string, string> = { limit: '200' }
    if (filterType.value) params.invoice_type = filterType.value
    const response = await invoicesApi.getAll(params)
    return response.data
  },
})

const filteredInvoices = computed(() => {
  const all = invoicesData.value ?? []
  if (!search.value) return all
  const q = search.value.toLowerCase()
  return all.filter(inv =>
    inv.invoice_number?.toLowerCase().includes(q) ||
    String(inv.total_amount).includes(q)
  )
})

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
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('invoices.title') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('invoices.subtitle') }}</p>
    </div>

    <Card>
      <CardHeader>
        <div class="flex items-center justify-between flex-wrap gap-4">
          <CardTitle>{{ t('invoices.allInvoices') }}</CardTitle>
          <div class="flex items-center gap-3 flex-wrap">
            <input
              v-model="search"
              type="text"
              :placeholder="t('invoices.searchPlaceholder')"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <div class="flex gap-1">
              <button
                v-for="opt in [{ label: t('common.all'), value: '' }, { label: t('invoices.sales'), value: 'sale' }, { label: t('invoices.purchases'), value: 'purchase' }]"
                :key="opt.value"
                :class="filterType === opt.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'"
                class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                @click="filterType = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
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
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('common.type') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableDate') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableSupplier') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableInvoiceNumber') }}</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableAmount') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('invoices.tableStatus') }}</th>
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
                <td class="px-6 py-4 text-sm">
                  <span
                    :class="invoice.invoice_type === 'sale'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-blue-100 text-blue-800'"
                    class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium"
                  >
                    {{ invoice.invoice_type === 'sale' ? t('common.sale') : t('common.purchase') }}
                  </span>
                </td>
                <td class="px-6 py-4 text-sm text-gray-500">{{ formatDate(invoice.invoice_date) }}</td>
                <td class="px-6 py-4 text-sm text-gray-700">{{ invoice.supplier_name ?? invoice.customer_name ?? '-' }}</td>
                <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ invoice.invoice_number }}</td>
                <td class="px-6 py-4 text-sm font-medium text-gray-900 text-right">
                  {{ formatCurrency(invoice.total_amount) }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-500 capitalize">{{ invoice.status ?? '-' }}</td>
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
      </CardContent>
    </Card>
  </div>

  <!-- Bank Transaction Modal -->
  <Teleport to="body">
    <div v-if="showTxModal" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/50" @click="showTxModal = false" />
      <div class="relative z-10 bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b">
          <h2 class="text-lg font-semibold text-gray-900">{{ t('invoices.bankTxModal.title') }}</h2>
          <button class="p-1 rounded hover:bg-gray-100 transition-colors" @click="showTxModal = false">
            <X class="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <!-- Body -->
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
        <!-- Footer -->
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
