<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { CheckCircle, ExternalLink, X, Undo2, Eye, AlertTriangle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { invoicesApi, bankApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'
import type { Invoice } from '@/types'

const { t } = useI18n()
const queryClient = useQueryClient()
const filterMethod = ref<'all' | 'bank' | 'partial'>('all')
const search = ref('')

const { data: invoicesData, isLoading } = useQuery({
  queryKey: ['reconciled-invoices'],
  queryFn: async () => {
    const res = await invoicesApi.getAll({ reconciled_only: true, limit: 500 })
    return res.data
  },
})

const reconciliations = computed((): Invoice[] => invoicesData.value ?? [])

const filtered = computed(() => {
  let list = reconciliations.value
  if (filterMethod.value === 'partial') {
    list = list.filter(r => r.is_partial)
  } else if (filterMethod.value === 'bank') {
    list = list.filter(r => r.is_reconciled && !r.is_partial)
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(r =>
      r.invoice_number?.toLowerCase().includes(q) ||
      (r.supplier_name ?? r.customer_name ?? '').toLowerCase().includes(q)
    )
  }
  return list
})

const stats = computed(() => ({
  total: reconciliations.value.length,
  bank: reconciliations.value.filter(r => r.is_reconciled && !r.is_partial).length,
  partial: reconciliations.value.filter(r => r.is_partial).length,
}))

// Bank transaction modal
const showTxModal = ref(false)
const txLoading = ref(false)
const txData = ref<Record<string, unknown> | null>(null)
const modalInvoice = ref<Invoice | null>(null)

async function openTxModal(inv: Invoice) {
  if (!inv.bank_transaction_id) return
  modalInvoice.value = inv
  showTxModal.value = true
  txLoading.value = true
  txData.value = null
  try {
    const res = await bankApi.getTransaction(inv.bank_transaction_id)
    txData.value = res.data
  } finally {
    txLoading.value = false
  }
}

// Undo bank reconciliation
const undoConfirm = ref<number | null>(null)

const undoBankMutation = useMutation({
  mutationFn: (txId: number) => bankApi.unreconcileTransaction(txId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['reconciled-invoices'] })
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
    undoConfirm.value = null
  },
})

function doUndo(inv: Invoice) {
  if (inv.bank_transaction_id) {
    undoBankMutation.mutate(inv.bank_transaction_id)
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('reconciliation.overviewTitle') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('reconciliation.overviewSubtitle') }}</p>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-3 gap-4">
      <Card>
        <CardContent class="pt-5">
          <p class="text-sm text-gray-500">{{ t('reconciliation.totalReconciled') }}</p>
          <p class="text-3xl font-bold text-gray-900 mt-1">{{ stats.total }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-5">
          <div class="flex items-center gap-2 text-emerald-700 mb-1">
            <CheckCircle class="h-4 w-4" />
            <p class="text-sm font-medium">{{ t('reconciliation.bankFull') }}</p>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ stats.bank }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-5">
          <div class="flex items-center gap-2 text-amber-700 mb-1">
            <AlertTriangle class="h-4 w-4" />
            <p class="text-sm font-medium">{{ t('common.partial') }}</p>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ stats.partial }}</p>
        </CardContent>
      </Card>
    </div>

    <!-- Reconciliations table -->
    <Card>
      <CardHeader>
        <div class="flex items-center justify-between flex-wrap gap-4">
          <CardTitle>{{ t('reconciliation.reconciledInvoicesCard') }}</CardTitle>
          <div class="flex items-center gap-3 flex-wrap">
            <input
              v-model="search"
              type="text"
              :placeholder="t('reconciliation.searchPlaceholder')"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <div class="flex gap-1">
              <button
                v-for="opt in [
                  { label: t('common.all'), value: 'all' },
                  { label: t('reconciliation.filterFull'), value: 'bank' },
                  { label: t('reconciliation.filterPartial'), value: 'partial' },
                ]"
                :key="opt.value"
                :class="filterMethod === opt.value
                  ? (opt.value === 'partial' ? 'bg-amber-500 text-white' : 'bg-primary-600 text-white')
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'"
                class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                @click="filterMethod = opt.value as 'all' | 'bank' | 'partial'"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="filtered.length === 0" class="text-center py-12 text-gray-400">
          {{ t('reconciliation.noReconciliations') }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableInvoice') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableDate') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableParty') }}</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableAmount') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableBankStatus') }}</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{{ t('reconciliation.tableTransaction') }}</th>
                <th class="px-6 py-3" />
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr
                v-for="inv in filtered"
                :key="inv.id"
                class="hover:bg-gray-50 transition-colors"
              >
                <!-- Invoice # + type -->
                <td class="px-6 py-4 text-sm">
                  <router-link
                    :to="`/invoices/${inv.id}`"
                    class="font-medium text-primary-700 hover:underline"
                  >
                    {{ inv.invoice_number }}
                  </router-link>
                  <span
                    :class="inv.invoice_type === 'sale' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'"
                    class="ml-2 inline-flex px-1.5 py-0.5 rounded text-xs font-medium"
                  >
                    {{ inv.invoice_type === 'sale' ? t('common.sale') : t('common.purchase') }}
                  </span>
                </td>

                <!-- Date -->
                <td class="px-6 py-4 text-sm text-gray-500">{{ formatDate(inv.invoice_date) }}</td>

                <!-- Party -->
                <td class="px-6 py-4 text-sm text-gray-700">
                  {{ inv.supplier_name ?? inv.customer_name ?? '—' }}
                </td>

                <!-- Amount -->
                <td class="px-6 py-4 text-sm font-medium text-gray-900 text-right">
                  {{ formatCurrency(inv.total_amount) }}
                </td>

                <!-- Bank status badge -->
                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                    :class="inv.is_partial ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'"
                  >
                    <CheckCircle class="h-3 w-3" />
                    {{ inv.is_partial ? `${t('reconciliation.filterPartial')} — ${formatCurrency(inv.reconciled_amount ?? 0)} / ${formatCurrency(inv.total_amount)}` : t('common.full') }}
                  </span>
                </td>

                <!-- Transaction link -->
                <td class="px-6 py-4 text-sm text-gray-600">
                  <button
                    class="flex items-center gap-1.5 text-emerald-700 hover:text-emerald-900 hover:underline transition-colors"
                    @click="openTxModal(inv)"
                  >
                    <Eye class="h-3.5 w-3.5" />
                    {{ (inv.linked_transaction_ids?.length ?? 0) > 1 ? `${inv.linked_transaction_ids!.length} transactions` : t('reconciliation.viewTransaction') }}
                  </button>
                </td>

                <!-- Actions -->
                <td class="px-6 py-4 text-sm text-right whitespace-nowrap">
                  <template v-if="undoConfirm === inv.id">
                    <span class="text-xs text-gray-600 mr-2">{{ t('reconciliation.undo') }}</span>
                    <button
                      class="text-xs font-semibold text-red-600 hover:text-red-800 mr-2"
                      :disabled="undoBankMutation.isPending.value"
                      @click="doUndo(inv)"
                    >
                      {{ t('common.confirm') }}
                    </button>
                    <button
                      class="text-xs font-medium text-gray-500 hover:text-gray-700"
                      @click="undoConfirm = null"
                    >
                      {{ t('common.cancel') }}
                    </button>
                  </template>
                  <button
                    v-else
                    class="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600 transition-colors"
                    :title="t('reconciliation.undoReconciliation')"
                    @click="undoConfirm = inv.id"
                  >
                    <Undo2 class="h-4 w-4" />
                    Undo
                  </button>
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
              <div v-if="txData.balance_after !== null">
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
        <div class="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
          <router-link
            v-if="modalInvoice?.bank_transaction_id"
            :to="`/bank?highlight=${modalInvoice.bank_transaction_id}`"
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
  </Teleport>
</template>
