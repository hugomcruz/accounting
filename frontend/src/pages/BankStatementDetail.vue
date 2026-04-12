<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { ref, computed } from 'vue'
import { ArrowLeft, RefreshCw, CheckCircle, XCircle, ArrowLeftRight, X, MessageSquare, Send, Pencil, Trash2, ExternalLink, Receipt } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { bankApi, invoicesApi } from '@/services/queries'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const id = Number(route.params.id)

// Transfer link modal state
const showTransferModal = ref(false)
const linkingTx = ref<any>(null)
const selectedStatementId = ref<number | null>(null)
const selectedCounterpartId = ref<number | null>(null)

// Notes panel state
const notesTx = ref<any>(null)
const newNoteBody = ref('')
const editingNoteId = ref<number | null>(null)
const editingNoteBody = ref('')

// Reconciliation detail modal
const reconTx = ref<any>(null)
const reconInvoice = ref<any>(null)
const reconLoading = ref(false)

async function openReconModal(tx: any) {
  if (!tx.invoice_id) return
  reconTx.value = tx
  reconInvoice.value = null
  reconLoading.value = true
  try {
    const res = await invoicesApi.getById(tx.invoice_id)
    reconInvoice.value = res.data
  } finally {
    reconLoading.value = false
  }
}

function closeReconModal() {
  reconTx.value = null
  reconInvoice.value = null
}

const { data: statement, isLoading } = useQuery({
  queryKey: ['bank-statement', id],
  queryFn: async () => {
    const res = await bankApi.getStatement(id)
    return res.data
  },
})

const { data: transactions, isLoading: loadingTxs } = useQuery({
  queryKey: ['bank-transactions', id],
  queryFn: async () => {
    const res = await bankApi.getTransactions({ statement_id: id })
    return res.data
  },
})

// All statements for the modal picker (excluding current)
const { data: allStatements } = useQuery({
  queryKey: ['bank-statements'],
  queryFn: async () => {
    const res = await bankApi.getStatements()
    return res.data
  },
})

const otherStatements = computed(() =>
  (allStatements.value ?? []).filter((s: any) => s.id !== id)
)

// Transactions from selected statement in modal
const { data: counterpartTxs } = useQuery({
  queryKey: ['bank-transactions-modal', selectedStatementId],
  queryFn: async () => {
    if (!selectedStatementId.value) return []
    const res = await bankApi.getTransactions({ statement_id: selectedStatementId.value })
    return res.data
  },
  enabled: computed(() => !!selectedStatementId.value),
})

const reconcileMutation = useMutation({
  mutationFn: () => bankApi.reconcileStatement(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-statement', id] })
    queryClient.invalidateQueries({ queryKey: ['bank-transactions', id] })
  },
})

const linkTransferMutation = useMutation({
  mutationFn: ({ txId, counterpartId }: { txId: number; counterpartId: number }) =>
    bankApi.linkTransfer(txId, counterpartId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-transactions', id] })
    queryClient.invalidateQueries({ queryKey: ['bank-transactions-modal', selectedStatementId.value] })
    closeTransferModal()
  },
})

const unlinkTransferMutation = useMutation({
  mutationFn: (txId: number) => bankApi.unlinkTransfer(txId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-transactions', id] })
  },
})

function openTransferModal(tx: any) {
  linkingTx.value = tx
  selectedStatementId.value = null
  selectedCounterpartId.value = null
  showTransferModal.value = true
}

function closeTransferModal() {
  showTransferModal.value = false
  linkingTx.value = null
  selectedStatementId.value = null
  selectedCounterpartId.value = null
}

function confirmLink() {
  if (!linkingTx.value || !selectedCounterpartId.value) return
  linkTransferMutation.mutate({ txId: linkingTx.value.id, counterpartId: selectedCounterpartId.value })
}

const totalTxs = () => transactions.value?.length ?? 0
const reconciledTxs = () => transactions.value?.filter((t: any) => t.is_reconciled).length ?? 0
const reconciledPct = () => totalTxs() ? Math.round((reconciledTxs() / totalTxs()) * 100) : 0

// Notes for selected transaction
const { data: notes, isLoading: notesLoading } = useQuery({
  queryKey: computed(() => ['bank-tx-notes', notesTx.value?.id]),
  queryFn: async () => {
    if (!notesTx.value) return []
    const res = await bankApi.getTransactionNotes(notesTx.value.id)
    return res.data
  },
  enabled: computed(() => !!notesTx.value),
})

const addNoteMutation = useMutation({
  mutationFn: ({ txId, body }: { txId: number; body: string }) =>
    bankApi.addTransactionNote(txId, body),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-tx-notes', notesTx.value?.id] })
    queryClient.invalidateQueries({ queryKey: ['bank-transactions', id] })
    newNoteBody.value = ''
  },
})

const updateNoteMutation = useMutation({
  mutationFn: ({ txId, noteId, body }: { txId: number; noteId: number; body: string }) =>
    bankApi.updateTransactionNote(txId, noteId, body),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-tx-notes', notesTx.value?.id] })
    editingNoteId.value = null
    editingNoteBody.value = ''
  },
})

const deleteNoteMutation = useMutation({
  mutationFn: ({ txId, noteId }: { txId: number; noteId: number }) =>
    bankApi.deleteTransactionNote(txId, noteId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-tx-notes', notesTx.value?.id] })
    queryClient.invalidateQueries({ queryKey: ['bank-transactions', id] })
  },
})

function openNotes(tx: any) {
  notesTx.value = tx
  newNoteBody.value = ''
  editingNoteId.value = null
}

function closeNotes() {
  notesTx.value = null
}

function startEdit(note: any) {
  editingNoteId.value = note.id
  editingNoteBody.value = note.body
}

function cancelEdit() {
  editingNoteId.value = null
  editingNoteBody.value = ''
}

function postNote() {
  if (!newNoteBody.value.trim() || !notesTx.value) return
  addNoteMutation.mutate({ txId: notesTx.value.id, body: newNoteBody.value.trim() })
}

function saveEdit(noteId: number) {
  if (!editingNoteBody.value.trim() || !notesTx.value) return
  updateNoteMutation.mutate({ txId: notesTx.value.id, noteId, body: editingNoteBody.value.trim() })
}

function deleteNote(noteId: number) {
  if (!notesTx.value) return
  if (!confirm(t('bank.noteDeleteConfirm'))) return
  deleteNoteMutation.mutate({ txId: notesTx.value.id, noteId })
}

function categoryColor(cat: string) {
  const map: Record<string, string> = {
    income: 'bg-green-100 text-green-700',
    expense: 'bg-red-100 text-red-700',
    transfer: 'bg-blue-100 text-blue-700',
  }
  return map[cat?.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <button class="p-2 hover:bg-gray-100 rounded-lg" @click="router.push('/bank/statements')">
        <ArrowLeft class="h-5 w-5" />
      </button>
      <div class="flex-1">
        <h1 class="text-3xl font-bold text-gray-900">{{ t('bank.statementDetail') }}</h1>
        <p v-if="statement" class="mt-1 text-gray-500">{{ statement.account_name || statement.account_number }}</p>
      </div>
      <button
        :disabled="reconcileMutation.isPending.value"
        class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        @click="reconcileMutation.mutate()"
      >
        <RefreshCw class="h-4 w-4" :class="reconcileMutation.isPending.value ? 'animate-spin' : ''" />
        {{ reconcileMutation.isPending.value ? t('bank.reconciling') : t('bank.autoReconcile') }}
      </button>
    </div>

    <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>
    <template v-else-if="statement">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent class="pt-4">
            <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('bank.openingBalance') }}</p>
            <p class="text-xl font-bold text-gray-900 mt-1">€{{ Number(statement.opening_balance || 0).toFixed(2) }}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent class="pt-4">
            <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('bank.closingBalance') }}</p>
            <p class="text-xl font-bold text-gray-900 mt-1">€{{ Number(statement.closing_balance || 0).toFixed(2) }}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent class="pt-4">
            <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('bank.totalIn') }}</p>
            <p class="text-xl font-bold text-green-600 mt-1">€{{ Number(statement.total_credits || 0).toFixed(2) }}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent class="pt-4">
            <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('bank.totalOut') }}</p>
            <p class="text-xl font-bold text-red-600 mt-1">€{{ Number(statement.total_debits || 0).toFixed(2) }}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent class="pt-4">
          <div class="flex items-center justify-between mb-2">
            <p class="text-sm font-medium text-gray-700">{{ t('bank.reconciliationProgress') }}</p>
            <p class="text-sm text-gray-500">{{ reconciledTxs() }} / {{ totalTxs() }} ({{ reconciledPct() }}%)</p>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2.5">
            <div class="bg-blue-600 h-2.5 rounded-full transition-all" :style="{ width: reconciledPct() + '%' }"></div>
          </div>
        </CardContent>
      </Card>
    </template>

    <Card>
      <CardHeader><CardTitle>{{ t('bank.transactionsCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="loadingTxs" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!transactions?.length" class="text-center py-6 text-gray-400">{{ t('bank.noTxFound') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('bank.tableDate') }}</th>
                <th class="pb-2 font-medium">{{ t('bank.tableDescription') }}</th>
                <th class="pb-2 font-medium">{{ t('bank.tableCategory') }}</th>
                <th class="pb-2 font-medium text-right">{{ t('bank.tableAmount') }}</th>
                <th class="pb-2 font-medium text-center">{{ t('bank.tableReconciled') }}</th>
                <th class="pb-2 font-medium text-center">{{ t('bank.tableTransfer') }}</th>
                <th class="pb-2 font-medium text-center">{{ t('bank.tableNotes') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in transactions" :key="tx.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-3">{{ new Date(tx.date || tx.transaction_date).toLocaleDateString() }}</td>
                <td class="py-3 max-w-xs truncate">{{ tx.description }}</td>
                <td class="py-3">
                  <span v-if="tx.category" :class="categoryColor(tx.category)"
                    class="px-2 py-0.5 rounded-full text-xs font-medium capitalize">
                    {{ tx.category }}
                  </span>
                </td>
                <td class="py-3 text-right font-medium" :class="Number(tx.amount) >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ Number(tx.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(tx.amount)).toFixed(2) }}
                </td>
                <td class="py-3 text-center">
                  <button v-if="tx.is_reconciled && tx.invoice_id"
                    class="p-0.5 rounded hover:bg-emerald-50 transition-colors mx-auto block"
                    :title="t('bank.viewReconciliation')"
                    @click="openReconModal(tx)"
                  >
                    <CheckCircle class="h-4 w-4 text-green-500" />
                  </button>
                  <CheckCircle v-else-if="tx.is_reconciled" class="h-4 w-4 text-green-500 mx-auto" />
                  <XCircle v-else class="h-4 w-4 text-gray-300 mx-auto" />
                </td>
                <td class="py-3 text-center">
                  <!-- Already linked as transfer -->
                  <div v-if="tx.linked_transaction_id" class="flex items-center justify-center gap-1">
                    <span class="text-xs text-blue-600 font-medium">tx#{{ tx.linked_transaction_id }}</span>
                    <button
                      class="p-1 text-red-400 hover:text-red-600 rounded"
                      :title="t('bank.unlinkTransfer')"
                      @click="unlinkTransferMutation.mutate(tx.id)"
                    >
                      <X class="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <!-- Not linked: show link button -->
                  <button
                    v-else
                    class="p-1 text-gray-400 hover:text-blue-600 rounded"
                    :title="t('bank.linkTransfer')"
                    @click="openTransferModal(tx)"
                  >
                    <ArrowLeftRight class="h-4 w-4" />
                  </button>
                </td>
                <td class="py-3 text-center">
                  <button
                    :title="t('bank.addNote')"
                    class="p-1 rounded hover:bg-gray-100 transition-colors relative"
                    :class="tx.note_count > 0 ? 'text-blue-600' : 'text-gray-300 hover:text-gray-500'"
                    @click="openNotes(tx)"
                  >
                    <MessageSquare class="h-4 w-4" />
                    <span v-if="tx.note_count > 0"
                      class="absolute -top-1 -right-1 bg-blue-600 text-white text-[9px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center leading-none">
                      {{ tx.note_count > 9 ? '9+' : tx.note_count }}
                    </span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>

    <!-- Notes slide-over panel -->
    <Teleport to="body">
      <div v-if="notesTx" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-black/30" @click="closeNotes" />
        <div class="relative z-10 bg-white w-full max-w-md flex flex-col shadow-2xl h-full">
          <div class="flex items-start justify-between p-4 border-b bg-gray-50">
            <div class="min-w-0">
              <h2 class="text-base font-semibold text-gray-900">{{ t('bank.notesTitle') }}</h2>
              <p class="text-xs text-gray-500 mt-0.5 truncate max-w-xs">
                {{ new Date(notesTx.transaction_date).toLocaleDateString() }} ·
                <span :class="Number(notesTx.amount) >= 0 ? 'text-green-600' : 'text-red-600'" class="font-medium">
                  {{ Number(notesTx.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(notesTx.amount)).toFixed(2) }}
                </span>
              </p>
              <p class="text-xs text-gray-400 truncate max-w-xs mt-0.5">{{ notesTx.description }}</p>
            </div>
            <button @click="closeNotes" class="p-1 hover:bg-gray-200 rounded ml-2 shrink-0"><X class="h-4 w-4" /></button>
          </div>
          <div class="flex-1 overflow-y-auto p-4 space-y-3">
            <div v-if="notesLoading" class="text-center text-sm text-gray-400 pt-8">{{ t('common.loading') }}</div>
            <div v-else-if="!notes?.length" class="text-center text-sm text-gray-400 pt-8">{{ t('bank.notesEmpty') }}</div>
            <div v-for="note in notes" :key="note.id" class="group bg-gray-50 rounded-lg p-3">
              <template v-if="editingNoteId === note.id">
                <textarea v-model="editingNoteBody" rows="3"
                  class="w-full text-sm border border-blue-300 rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                <div class="flex gap-2 mt-2 justify-end">
                  <button @click="cancelEdit" class="text-xs px-3 py-1 rounded border text-gray-600 hover:bg-gray-100">{{ t('bank.noteCancelEdit') }}</button>
                  <button @click="saveEdit(note.id)" :disabled="updateNoteMutation.isPending.value"
                    class="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                    {{ t('bank.noteSaveEdit') }}
                  </button>
                </div>
              </template>
              <template v-else>
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs font-semibold text-gray-700">{{ note.username }}</span>
                  <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click="startEdit(note)" class="p-0.5 text-gray-400 hover:text-blue-600 rounded" :title="t('bank.noteEdit')">
                      <Pencil class="h-3 w-3" />
                    </button>
                    <button @click="deleteNote(note.id)" class="p-0.5 text-gray-400 hover:text-red-600 rounded" :title="t('bank.noteDelete')">
                      <Trash2 class="h-3 w-3" />
                    </button>
                  </div>
                </div>
                <p class="text-sm text-gray-800 whitespace-pre-wrap">{{ note.body }}</p>
                <p class="text-[10px] text-gray-400 mt-1">{{ new Date(note.created_at).toLocaleString() }}</p>
              </template>
            </div>
          </div>
          <div class="border-t p-3">
            <div class="flex gap-2 items-end">
              <textarea v-model="newNoteBody" :placeholder="t('bank.notePlaceholder')" rows="2"
                class="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none"
                @keydown.ctrl.enter="postNote" />
              <button @click="postNote" :disabled="!newNoteBody.trim() || addNoteMutation.isPending.value"
                class="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 shrink-0" :title="t('bank.notePost')">
                <Send class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Link Transfer Modal -->
    <div v-if="showTransferModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between p-6 border-b">
          <div>
            <h2 class="text-lg font-semibold">{{ t('bank.linkTransferTitle') }}</h2>
            <p class="text-sm text-gray-500 mt-0.5">
              {{ new Date(linkingTx?.transaction_date).toLocaleDateString() }} ·
              <span :class="Number(linkingTx?.amount) >= 0 ? 'text-green-600' : 'text-red-600'" class="font-medium">
                {{ Number(linkingTx?.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(linkingTx?.amount)).toFixed(2) }}
              </span>
              · {{ linkingTx?.description }}
            </p>
          </div>
          <button @click="closeTransferModal"><X class="h-5 w-5 text-gray-400" /></button>
        </div>
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.selectStatement') }}</label>
            <select
              v-model="selectedStatementId"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              @change="selectedCounterpartId = null"
            >
              <option :value="null">— {{ t('bank.chooseStatement') }} —</option>
              <option v-for="s in otherStatements" :key="s.id" :value="s.id">
                {{ s.company_name || s.account_number }} · {{ new Date(s.period_start).toLocaleDateString() }} – {{ new Date(s.period_end).toLocaleDateString() }}
              </option>
            </select>
          </div>
          <div v-if="selectedStatementId">
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.selectCounterpart') }}</label>
            <div class="border border-gray-200 rounded-lg max-h-56 overflow-y-auto">
              <div v-if="!counterpartTxs?.length" class="p-3 text-sm text-gray-400 text-center">{{ t('bank.noTxFound') }}</div>
              <label
                v-for="ctx in counterpartTxs"
                :key="ctx.id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer border-b last:border-0"
              >
                <input type="radio" :value="ctx.id" v-model="selectedCounterpartId" class="accent-blue-600" />
                <span class="text-xs text-gray-500 w-20 shrink-0">{{ new Date(ctx.transaction_date).toLocaleDateString() }}</span>
                <span class="flex-1 text-sm truncate">{{ ctx.description }}</span>
                <span :class="Number(ctx.amount) >= 0 ? 'text-green-600' : 'text-red-600'" class="text-sm font-medium shrink-0">
                  {{ Number(ctx.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(ctx.amount)).toFixed(2) }}
                </span>
              </label>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-3 px-6 py-4 border-t">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg" @click="closeTransferModal">{{ t('common.cancel') }}</button>
          <button
            :disabled="!selectedCounterpartId || linkTransferMutation.isPending.value"
            class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="confirmLink"
          >
            <ArrowLeftRight class="h-4 w-4" />
            {{ linkTransferMutation.isPending.value ? t('common.saving') : t('bank.confirmLinkTransfer') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reconciliation Detail Modal -->
    <Teleport to="body">
      <div v-if="reconTx" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="closeReconModal" />
        <div class="relative z-10 bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between px-6 py-4 border-b">
            <div>
              <h2 class="text-lg font-semibold text-gray-900">{{ t('bank.reconciliationDetail') }}</h2>
              <p class="text-sm text-gray-500 mt-0.5">
                {{ new Date(reconTx.transaction_date).toLocaleDateString() }} ·
                <span :class="Number(reconTx.amount) >= 0 ? 'text-green-600' : 'text-red-600'" class="font-medium">
                  {{ Number(reconTx.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(reconTx.amount)).toFixed(2) }}
                </span>
              </p>
            </div>
            <button @click="closeReconModal" class="p-1 rounded hover:bg-gray-100"><X class="h-5 w-5 text-gray-500" /></button>
          </div>
          <div class="px-6 py-5">
            <div v-if="reconLoading" class="text-center py-8 text-gray-400">{{ t('common.loading') }}</div>
            <div v-else-if="reconInvoice" class="space-y-4">
              <div class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <div>
                  <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('invoices.tableNumber') }}</p>
                  <p class="font-mono font-medium text-gray-900">{{ reconInvoice.invoice_number }}</p>
                </div>
                <div>
                  <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.amount') }}</p>
                  <p class="font-semibold text-base text-gray-900">€{{ Number(reconInvoice.total_amount).toFixed(2) }}</p>
                </div>
                <div class="col-span-2">
                  <p class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{{ t('common.supplier') }}</p>
                  <p class="font-medium text-gray-900">{{ reconInvoice.supplier_name || reconInvoice.customer_name || '-' }}</p>
                </div>
              </div>
              <div v-if="reconInvoice.expense_report" class="border-t pt-4">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">{{ t('invoices.bankTxModal.expenseReport') }}</p>
                <div class="bg-gray-50 rounded-lg p-3 space-y-2 text-sm">
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-medium text-gray-900">{{ reconInvoice.expense_report.title }}</span>
                    <span class="px-2 py-0.5 rounded-full text-xs font-medium capitalize"
                      :class="{
                        'bg-green-100 text-green-700': reconInvoice.expense_report.status === 'paid',
                        'bg-blue-100 text-blue-700': reconInvoice.expense_report.status === 'approved',
                        'bg-yellow-100 text-yellow-700': reconInvoice.expense_report.status === 'submitted',
                        'bg-gray-100 text-gray-600': reconInvoice.expense_report.status === 'draft',
                      }">{{ reconInvoice.expense_report.status }}</span>
                  </div>
                  <div v-if="reconInvoice.expense_report.expense_id" class="text-gray-500">{{ reconInvoice.expense_report.expense_id }}</div>
                  <div v-if="reconInvoice.expense_report.employee_name" class="text-gray-600">
                    {{ t('invoices.bankTxModal.expenseEmployee') }}: {{ reconInvoice.expense_report.employee_name }}
                  </div>
                  <div v-if="reconInvoice.expense_report.paid_at" class="text-gray-600">
                    {{ t('invoices.bankTxModal.expensePaidAt') }}: {{ new Date(reconInvoice.expense_report.paid_at).toLocaleDateString() }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
            <router-link v-if="reconInvoice?.id" :to="`/invoices/${reconInvoice.id}`"
              class="inline-flex items-center gap-1.5 text-sm text-blue-700 hover:text-blue-900 font-medium"
              @click="closeReconModal">
              <ExternalLink class="h-4 w-4" /> {{ t('bank.viewInvoice') }}
            </router-link>
            <router-link v-if="reconInvoice?.expense_report"
              :to="`/expenses/reports/${reconInvoice.expense_report.id}`"
              class="inline-flex items-center gap-1.5 text-sm text-purple-700 hover:text-purple-900 font-medium"
              @click="closeReconModal">
              <Receipt class="h-4 w-4" /> {{ t('invoices.bankTxModal.openExpenseReport') }}
            </router-link>
            <button @click="closeReconModal" class="px-4 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-100">{{ t('common.close') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
