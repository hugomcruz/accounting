<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { CheckCircle, XCircle, Landmark, MessageSquare, X, Send, Pencil, Trash2, ExternalLink, Receipt } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { bankApi, invoicesApi } from '@/services/queries'

const { t } = useI18n()

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

const filterMonth = ref(String(currentMonth).padStart(2, '0'))
const filterYear = ref(String(currentYear))
const filterStartDate = ref('')
const filterEndDate = ref('')
const filterCategory = ref('')
const filterReconciled = ref('')
const filterAccount = ref('')

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

const years = Array.from({ length: 5 }, (_, i) => currentYear + i)

const months = [
  { value: '01', label: 'January' }, { value: '02', label: 'February' },
  { value: '03', label: 'March' }, { value: '04', label: 'April' },
  { value: '05', label: 'May' }, { value: '06', label: 'June' },
  { value: '07', label: 'July' }, { value: '08', label: 'August' },
  { value: '09', label: 'September' }, { value: '10', label: 'October' },
  { value: '11', label: 'November' }, { value: '12', label: 'December' },
]

const queryParams = computed(() => ({
  month: filterMonth.value || undefined,
  year: filterYear.value || undefined,
  start_date: filterStartDate.value || undefined,
  end_date: filterEndDate.value || undefined,
  category: filterCategory.value || undefined,
  is_reconciled: filterReconciled.value !== '' ? filterReconciled.value === 'true' : undefined,
  account_number: filterAccount.value || undefined,
}))

const queryClient = useQueryClient()

const { data: accounts } = useQuery({
  queryKey: ['bank-accounts'],
  queryFn: async () => (await bankApi.getAccounts()).data,
})

function accountLogo(tx: any): string | null {
  if (!accounts.value) return null
  const acc = accounts.value.find((a: any) => a.account_number === tx.account_number)
  return acc?.logo_path ?? null
}

const { data: transactions, isLoading } = useQuery({
  queryKey: ['bank-transactions-all', queryParams],
  queryFn: async () => {
    const res = await bankApi.getTransactions(queryParams.value)
    return res.data
  },
})

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
    queryClient.invalidateQueries({ queryKey: ['bank-transactions-all'] })
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
    queryClient.invalidateQueries({ queryKey: ['bank-transactions-all'] })
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

const income = computed(() =>
  transactions.value?.filter((t: any) => Number(t.amount) > 0).reduce((s: number, t: any) => s + Number(t.amount), 0) ?? 0
)
const expenses = computed(() =>
  transactions.value?.filter((t: any) => Number(t.amount) < 0).reduce((s: number, t: any) => s + Math.abs(Number(t.amount)), 0) ?? 0
)
const net = computed(() => income.value - expenses.value)

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
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('bank.transactionsTitle') }}</h1>
      <p class="mt-1 text-gray-500">{{ t('bank.transactionsSubtitle') }}</p>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('bank.filtersCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.monthLabel') }}</label>
            <select v-model="filterMonth" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option v-for="m in months" :key="m.value" :value="m.value">{{ t('common.months.' + m.label.toLowerCase()) }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.yearLabel') }}</label>
            <select v-model="filterYear" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option v-for="y in years" :key="y" :value="String(y)">{{ y }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.startDate') }}</label>
            <input v-model="filterStartDate" type="date" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.endDate') }}</label>
            <input v-model="filterEndDate" type="date" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.categoryLabel') }}</label>
            <select v-model="filterCategory" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option value="income">{{ t('common.income') }}</option>
              <option value="expense">{{ t('common.expense') }}</option>
              <option value="transfer">{{ t('common.transfer') }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.reconciledLabel') }}</label>
            <select v-model="filterReconciled" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option value="true">{{ t('common.yes') }}</option>
              <option value="false">{{ t('common.no') }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('bank.tableAccount') }}</label>
            <select v-model="filterAccount" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option v-for="acc in accounts" :key="acc.account_number" :value="acc.account_number">
                {{ acc.account_name || acc.account_number }}
              </option>
            </select>
          </div>
        </div>
      </CardContent>
    </Card>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('bank.transactionsCard') }}</p>
          <p class="text-xl font-bold text-gray-900 mt-1">{{ transactions?.length ?? 0 }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('common.income') }}</p>
          <p class="text-xl font-bold text-green-600 mt-1">€{{ income.toFixed(2) }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">{{ t('common.expense') }}</p>
          <p class="text-xl font-bold text-red-600 mt-1">€{{ expenses.toFixed(2) }}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-4">
          <p class="text-xs text-gray-500 uppercase tracking-wide">Net</p>
          <p class="text-xl font-bold mt-1" :class="net >= 0 ? 'text-green-600' : 'text-red-600'">
            {{ net >= 0 ? '+' : '' }}€{{ net.toFixed(2) }}
          </p>
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('bank.transactionsCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!transactions?.length" class="text-center py-6 text-gray-400">{{ t('bank.noTransactions') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('bank.tableDate') }}</th>
                <th class="pb-2 font-medium">{{ t('bank.tableAccount') }}</th>
                <th class="pb-2 font-medium">{{ t('bank.tableDescription') }}</th>
                <th class="pb-2 font-medium">{{ t('bank.tableCategory') }}</th>
                <th class="pb-2 font-medium text-right">{{ t('bank.tableAmount') }}</th>
                <th class="pb-2 font-medium text-center">{{ t('bank.tableReconciled') }}</th>
                <th class="pb-2 font-medium text-center">{{ t('bank.tableNotes') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in transactions" :key="tx.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-2.5">{{ new Date(tx.date || tx.transaction_date).toLocaleDateString() }}</td>
                <td class="py-2.5">
                  <div class="flex items-center gap-1.5">
                    <img v-if="accountLogo(tx)" :src="accountLogo(tx)!" class="h-4 w-4 object-contain flex-shrink-0" />
                    <Landmark v-else class="h-3.5 w-3.5 text-gray-300 flex-shrink-0" />
                    <span class="text-gray-500 text-xs">{{ tx.account_name || tx.account_number || '-' }}</span>
                  </div>
                </td>
                <td class="py-2.5 max-w-xs truncate">{{ tx.description }}</td>
                <td class="py-2.5">
                  <span v-if="tx.category" :class="categoryColor(tx.category)"
                    class="px-2 py-0.5 rounded-full text-xs font-medium capitalize">
                    {{ tx.category }}
                  </span>
                </td>
                <td class="py-2.5 text-right font-medium" :class="Number(tx.amount) >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ Number(tx.amount) >= 0 ? '+' : '' }}€{{ Math.abs(Number(tx.amount)).toFixed(2) }}
                </td>
                <td class="py-2.5 text-center">
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
                <td class="py-2.5 text-center">
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
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/30" @click="closeNotes" />
        <!-- Panel -->
        <div class="relative z-10 bg-white w-full max-w-md flex flex-col shadow-2xl h-full">
          <!-- Header -->
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
          <!-- Notes list -->
          <div class="flex-1 overflow-y-auto p-4 space-y-3">
            <div v-if="notesLoading" class="text-center text-sm text-gray-400 pt-8">{{ t('common.loading') }}</div>
            <div v-else-if="!notes?.length" class="text-center text-sm text-gray-400 pt-8">{{ t('bank.notesEmpty') }}</div>
            <div v-for="note in notes" :key="note.id" class="group bg-gray-50 rounded-lg p-3">
              <!-- Edit mode -->
              <template v-if="editingNoteId === note.id">
                <textarea
                  v-model="editingNoteBody"
                  rows="3"
                  class="w-full text-sm border border-blue-300 rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <div class="flex gap-2 mt-2 justify-end">
                  <button @click="cancelEdit" class="text-xs px-3 py-1 rounded border text-gray-600 hover:bg-gray-100">{{ t('bank.noteCancelEdit') }}</button>
                  <button @click="saveEdit(note.id)" :disabled="updateNoteMutation.isPending.value"
                    class="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                    {{ t('bank.noteSaveEdit') }}
                  </button>
                </div>
              </template>
              <!-- View mode -->
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
          <!-- Input -->
          <div class="border-t p-3">
            <div class="flex gap-2 items-end">
              <textarea
                v-model="newNoteBody"
                :placeholder="t('bank.notePlaceholder')"
                rows="2"
                class="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none"
                @keydown.ctrl.enter="postNote"
              />
              <button
                @click="postNote"
                :disabled="!newNoteBody.trim() || addNoteMutation.isPending.value"
                class="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 shrink-0"
                :title="t('bank.notePost')"
              >
                <Send class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

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
