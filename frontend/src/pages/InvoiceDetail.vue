<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ArrowLeft, FileText, Upload, CheckCircle, Clock, X, ExternalLink, Plus, Trash2, Banknote, User, DollarSign, Building2, Pencil, Send, MessageSquare } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { invoicesApi, bankApi, invoicePaymentsApi, invoiceCommentsApi, hrApi } from '@/services/queries'
import { formatCurrency, formatDate } from '@/lib/utils'
import type { InvoiceDirectPayment } from '@/types'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const id = Number(route.params.id)
const fileUrl = ref('')
const isUploading = ref(false)
const uploadError = ref('')
const queryClient = useQueryClient()
const authStore = useAuthStore()

const showTxModal = ref(false)
const txLoading = ref(false)
const txData = ref<Record<string, unknown> | null>(null)

async function openTxModal() {
  if (!invoice.value?.bank_transaction_id && !invoice.value?.expense_report) return
  showTxModal.value = true
  txLoading.value = true
  txData.value = null
  try {
    if (invoice.value?.bank_transaction_id) {
      const res = await bankApi.getTransaction(invoice.value.bank_transaction_id)
      txData.value = res.data
    }
  } finally {
    txLoading.value = false
  }
}

// Payments
const showAddPayment = ref(false)
const paymentForm = ref({
  payment_date: new Date().toISOString().slice(0, 10),
  amount: '',
  payment_type: 'cash' as 'cash' | 'employee' | 'company_account' | 'other',
  reference: '',
  employee_id: '' as number | '',
  bank_transaction_id: '' as number | '',
  notes: '',
})
const paymentError = ref('')

// Bank transaction search for company_account payments
const txSearchQuery = ref('')
const { data: txSearchResults } = useQuery({
  queryKey: ['bank-tx-search', txSearchQuery],
  queryFn: async () => {
    if (!txSearchQuery.value || txSearchQuery.value.length < 2) return []
    const res = await bankApi.getTransactions({ search: txSearchQuery.value, limit: 20 })
    return (res.data as Record<string, unknown>[])
  },
  enabled: computed(() => paymentForm.value.payment_type === 'company_account'),
})

const { data: employees } = useQuery({
  queryKey: ['employees'],
  queryFn: async () => {
    const res = await hrApi.getEmployees()
    return (res.data as { id: number; first_name: string; last_name: string }[])
  },
})

const addPaymentMutation = useMutation({
  mutationFn: (data: Record<string, unknown>) => invoicePaymentsApi.add(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    showAddPayment.value = false
    paymentError.value = ''
    txSearchQuery.value = ''
    paymentForm.value = {
      payment_date: new Date().toISOString().slice(0, 10),
      amount: '',
      payment_type: 'cash',
      reference: '',
      employee_id: '',
      bank_transaction_id: '',
      notes: '',
    }
  },
  onError: (err: unknown) => {
    const axiosError = err as { response?: { data?: { detail?: string } } }
    paymentError.value = axiosError.response?.data?.detail || 'Failed to add payment'
  },
})

const deletePaymentMutation = useMutation({
  mutationFn: (paymentId: number) => invoicePaymentsApi.delete(id, paymentId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['invoice', id] }),
})

function submitPayment() {
  paymentError.value = ''
  const amt = parseFloat(String(paymentForm.value.amount))
  if (!amt || amt <= 0) { paymentError.value = 'Enter a valid amount'; return }
  if (paymentForm.value.payment_type === 'company_account' && !paymentForm.value.bank_transaction_id) {
    paymentError.value = 'Select a bank transaction'; return
  }
  const data: Record<string, unknown> = {
    payment_date: new Date(paymentForm.value.payment_date).toISOString(),
    amount: amt,
    payment_type: paymentForm.value.payment_type,
    reference: paymentForm.value.reference || null,
    notes: paymentForm.value.notes || null,
    employee_id: paymentForm.value.payment_type === 'employee' && paymentForm.value.employee_id ? paymentForm.value.employee_id : null,
    bank_transaction_id: paymentForm.value.payment_type === 'company_account' ? paymentForm.value.bank_transaction_id : null,
  }
  addPaymentMutation.mutate(data)
}

const paymentTypeLabel = (type: string) => ({ cash: 'Cash', employee: 'Employee', company_account: 'Company Account', other: 'Other' }[type] ?? type)

const { data: invoice, isLoading } = useQuery({
  queryKey: ['invoice', id],
  queryFn: async () => {
    const response = await invoicesApi.getById(id)
    return response.data
  },
  enabled: !!id,
})

const backRoute = computed(() =>
  invoice.value?.invoice_type === 'sale' ? '/invoices/sales' : '/invoices/purchases'
)

watch(invoice, async (inv) => {
  if (inv?.file_path) {
    try {
      const res = await invoicesApi.getFileUrl(id)
      fileUrl.value = res.data.url
    } catch {
      fileUrl.value = ''
    }
  }
}, { immediate: true })

async function onAttachFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  isUploading.value = true
  uploadError.value = ''
  try {
    const res = await invoicesApi.attachFile(id, file)
    fileUrl.value = res.data.url
    await queryClient.invalidateQueries({ queryKey: ['invoice', id] })
  } catch (err: unknown) {
    const axiosError = err as { response?: { data?: { detail?: string } } }
    uploadError.value = axiosError.response?.data?.detail || 'Upload failed'
  } finally {
    isUploading.value = false
    ;(e.target as HTMLInputElement).value = ''
  }
}

function parseQRData(raw?: string) {
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

// --- Invoice field editing ---
const showEdit = ref(false)
const editError = ref('')
const editForm = ref({
  notes: '',
  due_date: '',
  status: '' as string,
  is_foreign_currency: false,
  foreign_currency_code: '',
  original_total_amount: '' as number | '',
  original_tax_amount: '' as number | '',
  total_amount: '' as number | '',
  tax_amount: '' as number | '',
})

function startEdit() {
  if (!invoice.value) return
  const inv = invoice.value as Record<string, unknown>
  editForm.value = {
    notes: (inv.notes as string) ?? '',
    due_date: inv.due_date ? String(inv.due_date).slice(0, 10) : '',
    status: (inv.status as string) ?? '',
    is_foreign_currency: Boolean(inv.is_foreign_currency),
    foreign_currency_code: (inv.foreign_currency_code as string) ?? '',
    original_total_amount: inv.original_total_amount != null ? (inv.original_total_amount as number) : '',
    original_tax_amount: inv.original_tax_amount != null ? (inv.original_tax_amount as number) : '',
    total_amount: inv.total_amount != null ? (inv.total_amount as number) : '',
    tax_amount: inv.tax_amount != null ? (inv.tax_amount as number) : '',
  }
  showEdit.value = true
  editError.value = ''
}

const autoExchangeRate = computed(() => {
  const orig = parseFloat(String(editForm.value.original_total_amount))
  const eur = parseFloat(String(editForm.value.total_amount))
  if (orig > 0 && eur > 0) return (orig / eur).toFixed(6)
  return null
})

const updateInvoiceMutation = useMutation({
  mutationFn: () => {
    const payload: Record<string, unknown> = {}
    if (editForm.value.notes !== ((invoice.value as Record<string, unknown>).notes ?? '')) payload.notes = editForm.value.notes || null
    if (editForm.value.due_date) payload.due_date = new Date(editForm.value.due_date).toISOString()
    else payload.due_date = null
    if (editForm.value.status) payload.status = editForm.value.status
    payload.is_foreign_currency = editForm.value.is_foreign_currency
    if (editForm.value.is_foreign_currency) {
      payload.foreign_currency_code = editForm.value.foreign_currency_code || null
      payload.original_total_amount = editForm.value.original_total_amount !== '' ? Number(editForm.value.original_total_amount) : null
      payload.original_tax_amount = editForm.value.original_tax_amount !== '' ? Number(editForm.value.original_tax_amount) : null
      payload.total_amount = editForm.value.total_amount !== '' ? Number(editForm.value.total_amount) : undefined
      payload.tax_amount = editForm.value.tax_amount !== '' ? Number(editForm.value.tax_amount) : undefined
      if (autoExchangeRate.value) payload.exchange_rate = parseFloat(autoExchangeRate.value)
    } else {
      payload.foreign_currency_code = null
      payload.original_total_amount = null
      payload.original_tax_amount = null
      payload.exchange_rate = null
    }
    return invoicesApi.update(id, payload as Partial<import('@/types').Invoice>)
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    showEdit.value = false
    editError.value = ''
  },
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { detail?: string } } }
    editError.value = e.response?.data?.detail || 'Failed to save changes'
  },
})

// ─── Comments ─────────────────────────────────────────────────────────────────

interface InvoiceComment {
  id: number
  invoice_id: number
  user_id: number | null
  username: string
  body: string
  created_at: string
  updated_at: string
}

const { data: comments, isLoading: commentsLoading } = useQuery({
  queryKey: ['invoice-comments', id],
  queryFn: async () => (await invoiceCommentsApi.getAll(id)).data as InvoiceComment[],
  enabled: !!id,
})

const newCommentBody = ref('')
const commentError = ref('')

const addCommentMutation = useMutation({
  mutationFn: (body: string) => invoiceCommentsApi.add(id, body),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-comments', id] })
    newCommentBody.value = ''
    commentError.value = ''
  },
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { detail?: string } } }
    commentError.value = e.response?.data?.detail || 'Failed to post comment'
  },
})

function submitComment() {
  const body = newCommentBody.value.trim()
  if (!body) return
  addCommentMutation.mutate(body)
}

// Inline edit
const editingCommentId = ref<number | null>(null)
const editingCommentBody = ref('')

function startEditComment(c: InvoiceComment) {
  editingCommentId.value = c.id
  editingCommentBody.value = c.body
}

const updateCommentMutation = useMutation({
  mutationFn: ({ commentId, body }: { commentId: number; body: string }) =>
    invoiceCommentsApi.update(id, commentId, body),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-comments', id] })
    editingCommentId.value = null
    editingCommentBody.value = ''
  },
})

function saveCommentEdit(commentId: number) {
  const body = editingCommentBody.value.trim()
  if (!body) return
  updateCommentMutation.mutate({ commentId, body })
}

const deleteCommentMutation = useMutation({
  mutationFn: (commentId: number) => invoiceCommentsApi.delete(id, commentId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['invoice-comments', id] }),
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { detail?: string } } }
    alert(e.response?.data?.detail || 'Could not delete comment')
  },
})

function canDeleteComment(c: InvoiceComment) {
  if (c.user_id === null) return false
  const age = Date.now() - new Date(c.created_at).getTime()
  return c.user_id === authStore.user?.id && age < 60 * 60 * 1000
}

function canEditComment(c: InvoiceComment) {
  return c.user_id !== null && c.user_id === authStore.user?.id
}

function wasEdited(c: InvoiceComment) {
  return Math.abs(new Date(c.updated_at).getTime() - new Date(c.created_at).getTime()) > 2000
}

function formatCommentDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <button
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        @click="router.push(backRoute)"
      >
        <ArrowLeft class="h-5 w-5" />
      </button>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('invoiceDetail.title') }}</h1>
    </div>

    <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>

    <div v-else-if="!invoice" class="text-center py-8 text-gray-500">{{ t('invoiceDetail.notFound') }}</div>

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">

        <!-- Left column: file preview (~40%) — hidden for sale invoices -->
        <div v-if="invoice.invoice_type !== 'sale'" class="lg:col-span-2">
          <!-- File exists -->
          <Card v-if="invoice.file_path">
            <CardHeader>
              <div class="flex items-center justify-between">
                <CardTitle>{{ t('invoiceDetail.invoiceFile') }}</CardTitle>
                <a
                  v-if="fileUrl"
                  :href="fileUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-800 font-medium transition-colors"
                  :title="t('invoiceDetail.openNewWindow')"
                >
                  <ExternalLink class="h-4 w-4" />
                  {{ t('invoiceDetail.openNewWindow') }}
                </a>
              </div>
            </CardHeader>
            <CardContent>
              <div v-if="fileUrl">
                <iframe
                  v-if="invoice.file_path?.endsWith('.pdf')"
                  :src="fileUrl"
                  class="w-full border-0 rounded-lg"
                  style="height: 520px;"
                  :title="t('invoiceDetail.invoicePreview')"
                />
                <img
                  v-else
                  :src="fileUrl"
                  alt="Invoice"
                  class="w-full rounded-lg object-contain border"
                  style="max-height: 520px;"
                />
              </div>
              <div v-else class="text-center py-8 text-gray-400">{{ t('invoiceDetail.loadingFile') }}</div>
            </CardContent>
          </Card>

          <!-- No file: allow attaching one -->
          <Card v-else>
            <CardHeader><CardTitle>{{ t('invoiceDetail.invoiceFile') }}</CardTitle></CardHeader>
            <CardContent>
              <div class="text-center py-6">
                <FileText class="mx-auto h-12 w-12 text-gray-300" />
                <p class="mt-2 text-sm text-gray-500">{{ t('invoiceDetail.noFile') }}</p>
                <p class="text-xs text-gray-400 mt-1 mb-4">{{ t('invoiceDetail.attachHint') }}</p>
                <label class="cursor-pointer inline-block">
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    class="hidden"
                    :disabled="isUploading"
                    @change="onAttachFile"
                  />
                  <Button as="span" :disabled="isUploading">
                    <Upload class="h-4 w-4 mr-2 inline" />
                    {{ isUploading ? t('invoiceDetail.uploading') : t('invoiceDetail.attachFile') }}
                  </Button>
                </label>
                <p v-if="uploadError" class="mt-3 text-sm text-red-600">{{ uploadError }}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Right column: details (~60%), full width for sale invoices -->
        <div :class="invoice.invoice_type === 'sale' ? 'lg:col-span-5' : 'lg:col-span-3'" class="space-y-6">
          <!-- Main info -->
          <Card>
            <CardHeader>
              <div class="flex items-start justify-between">
                <div>
                  <CardTitle>{{ invoice.invoice_number }}</CardTitle>
                  <p class="text-sm text-gray-500 mt-1">{{ formatDate(invoice.invoice_date) }}</p>
                </div>
                <div class="flex items-center gap-2 flex-wrap justify-end">
                  <span
                    :class="invoice.invoice_type === 'sale'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-blue-100 text-blue-800'"
                    class="inline-flex px-3 py-1 rounded-full text-sm font-medium"
                  >
                    {{ invoice.invoice_type === 'sale' ? t('common.sale') : t('common.purchase') }}
                  </span>
                  <button
                    v-if="invoice.is_reconciled && !invoice.is_partial"
                    class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-800 hover:bg-emerald-200 transition-colors cursor-pointer"
                    @click="openTxModal"
                  >
                    <CheckCircle class="h-3.5 w-3.5" />
                    {{ t('invoiceDetail.reconcileView') }}
                  </button>
                  <button
                    v-else-if="invoice.is_partial"
                    class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800 hover:bg-amber-200 transition-colors cursor-pointer"
                    @click="openTxModal"
                  >
                    <CheckCircle class="h-3.5 w-3.5" />
                    {{ t('invoices.reconcilePartial') }} &mdash; {{ formatCurrency(invoice.reconciled_amount ?? 0) }} / {{ formatCurrency(invoice.total_amount) }}
                  </button>
                  <span v-else class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-500">
                    <Clock class="h-3.5 w-3.5" />
                    {{ t('invoiceDetail.notReconciled') }}
                  </span>
                  <button
                    v-if="!showEdit"
                    class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
                    @click="startEdit"
                  >
                    <Pencil class="h-3.5 w-3.5" />
                    {{ t('common.edit') }}
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <!-- View mode -->
              <template v-if="!showEdit">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <p class="text-sm text-gray-500">{{ t('invoiceDetail.totalAmountEur') }}</p>
                    <p class="text-xl font-bold text-gray-900">{{ formatCurrency(invoice.total_amount) }}</p>
                  </div>
                  <div>
                    <p class="text-sm text-gray-500">{{ t('invoiceDetail.taxAmount') }}</p>
                    <p class="text-lg font-medium text-gray-900">{{ formatCurrency(invoice.tax_amount) }}</p>
                  </div>
                  <div>
                    <p class="text-sm text-gray-500">{{ t('common.status') }}</p>
                    <p class="text-lg font-medium text-gray-900 capitalize">{{ invoice.status ?? '-' }}</p>
                  </div>
                </div>

                <!-- Foreign currency display -->
                <div v-if="(invoice as Record<string, unknown>).is_foreign_currency" class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <p class="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">{{ t('invoiceDetail.foreignCurrencyLabel') }}</p>
                  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                    <div>
                      <p class="text-xs text-gray-500">{{ t('invoiceDetail.currency') }}</p>
                      <p class="font-semibold text-gray-900">{{ (invoice as Record<string, unknown>).foreign_currency_code ?? '—' }}</p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500">{{ t('invoiceDetail.originalTotal') }}</p>
                      <p class="font-semibold text-gray-900">
                        {{ (invoice as Record<string, unknown>).original_total_amount != null ? Number((invoice as Record<string, unknown>).original_total_amount).toFixed(2) : '—' }}
                        {{ (invoice as Record<string, unknown>).foreign_currency_code }}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500">{{ t('invoiceDetail.originalTax') }}</p>
                      <p class="font-semibold text-gray-900">
                        {{ (invoice as Record<string, unknown>).original_tax_amount != null ? Number((invoice as Record<string, unknown>).original_tax_amount).toFixed(2) : '—' }}
                        {{ (invoice as Record<string, unknown>).foreign_currency_code }}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-500">{{ t('invoiceDetail.exchangeRate') }}</p>
                      <p class="font-semibold text-gray-900">
                        <template v-if="(invoice as Record<string, unknown>).exchange_rate">
                          1 EUR = {{ Number((invoice as Record<string, unknown>).exchange_rate).toFixed(4) }} {{ (invoice as Record<string, unknown>).foreign_currency_code }}
                        </template>
                        <template v-else>—</template>
                      </p>
                    </div>
                  </div>
                </div>

                <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div v-if="invoice.atcud">
                    <p class="text-sm text-gray-500">{{ t('invoiceDetail.atcud') }}</p>
                    <p class="text-sm font-mono text-gray-900">{{ invoice.atcud }}</p>
                  </div>
                  <div v-if="invoice.notes">
                    <p class="text-sm text-gray-500">{{ t('common.notes') }}</p>
                    <p class="text-sm text-gray-900">{{ invoice.notes }}</p>
                  </div>
                </div>
              </template>

              <!-- Edit mode -->
              <template v-else>
                <div class="space-y-4">
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editStatusLabel') }}</label>
                      <select v-model="editForm.status" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                        <option value="draft">{{ t('invoiceDetail.statusOptions.draft') }}</option>
                        <option value="issued">{{ t('invoiceDetail.statusOptions.issued') }}</option>
                        <option value="paid">{{ t('invoiceDetail.statusOptions.paid') }}</option>
                        <option value="cancelled">{{ t('invoiceDetail.statusOptions.cancelled') }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editDueDate') }}</label>
                      <input v-model="editForm.due_date" type="date" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div class="sm:col-span-2">
                      <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editNotes') }}</label>
                      <input v-model="editForm.notes" type="text" :placeholder="t('invoiceDetail.editOptionalNotes')" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                  </div>

                  <!-- Foreign currency toggle -->
                  <div class="flex items-center gap-3 pt-1">
                    <input id="fc-toggle" v-model="editForm.is_foreign_currency" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label for="fc-toggle" class="text-sm font-medium text-gray-700">{{ t('invoiceDetail.editForeignCurrency') }}</label>
                  </div>

                  <!-- Foreign currency fields -->
                  <div v-if="editForm.is_foreign_currency" class="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-3">
                    <p class="text-xs font-semibold text-amber-700 uppercase tracking-wide">{{ t('invoiceDetail.editForeignDetails') }}</p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editCurrencyCode') }}</label>
                        <input v-model="editForm.foreign_currency_code" type="text" maxlength="3" placeholder="USD" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm uppercase focus:outline-none focus:ring-2 focus:ring-amber-400" />
                      </div>
                      <div>
                        <!-- spacer -->
                      </div>
                      <div>
                        <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editOriginalTotal', { code: editForm.foreign_currency_code || 'FC' }) }}</label>
                        <input v-model="editForm.original_total_amount" type="number" step="0.01" min="0" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
                      </div>
                      <div>
                        <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editOriginalTax', { code: editForm.foreign_currency_code || 'FC' }) }}</label>
                        <input v-model="editForm.original_tax_amount" type="number" step="0.01" min="0" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
                      </div>
                      <div>
                        <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editEurTotal') }}</label>
                        <input v-model="editForm.total_amount" type="number" step="0.01" min="0" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                      </div>
                      <div>
                        <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.editEurTax') }}</label>
                        <input v-model="editForm.tax_amount" type="number" step="0.01" min="0" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                      </div>
                    </div>
                    <div v-if="autoExchangeRate" class="text-sm text-amber-800 bg-amber-100 rounded px-3 py-2">
                      <span class="font-medium">{{ t('invoiceDetail.editExchangeRate') }}</span>
                      1 EUR = {{ autoExchangeRate }} {{ editForm.foreign_currency_code }}
                    </div>
                    <p v-else-if="editForm.original_total_amount && editForm.total_amount" class="text-xs text-red-600">
                      {{ t('invoiceDetail.editExchangeHint') }}
                    </p>
                  </div>

                  <p v-if="editError" class="text-xs text-red-600">{{ editError }}</p>
                  <div class="flex gap-2 pt-1">
                    <Button size="sm" :disabled="updateInvoiceMutation.isPending.value" @click="updateInvoiceMutation.mutate()">
                      {{ updateInvoiceMutation.isPending.value ? t('common.saving') : t('common.saveChanges') }}
                    </Button>
                    <Button variant="outline" size="sm" @click="showEdit = false; editError = ''">{{ t('common.cancel') }}</Button>
                  </div>
                </div>
              </template>
            </CardContent>
          </Card>

          <!-- QR Data -->
          <Card v-if="invoice.qr_code_data">
            <CardHeader>
              <CardTitle>{{ t('invoiceDetail.qrCodeData') }}</CardTitle>
            </CardHeader>
            <CardContent>
              <template v-if="parseQRData(invoice.qr_code_data)">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <template v-for="(val, key) in parseQRData(invoice.qr_code_data)" :key="key">
                    <div v-if="val !== null && val !== undefined">
                      <p class="text-xs text-gray-500 uppercase mb-0.5">{{ String(key).replace(/_/g, ' ') }}</p>
                      <p class="font-medium text-gray-900">{{ val }}</p>
                    </div>
                  </template>
                </div>
              </template>
              <p v-else class="text-sm text-gray-500">{{ t('invoiceDetail.cantParseQr') }}</p>
            </CardContent>
          </Card>

          <!-- Payments -->
          <Card>
            <CardHeader>
              <div class="flex items-center justify-between">
                <div>
                <CardTitle>{{ t('invoiceDetail.payments') }}</CardTitle>
                <p v-if="(invoice.payments?.length ?? 0) > 0" class="text-sm text-gray-500 mt-0.5">
                    {{ t('invoiceDetail.paid') }} {{ formatCurrency(invoice.total_paid ?? 0) }}
                    <span v-if="(invoice.remaining_amount ?? 0) > 0.01" class="text-amber-600"> · {{ t('invoiceDetail.remaining') }} {{ formatCurrency(invoice.remaining_amount ?? 0) }}</span>
                    <span v-else class="text-emerald-600"> · {{ t('invoiceDetail.fullyPaid') }}</span>
                  </p>
                </div>
                <Button variant="outline" size="sm" @click="showAddPayment = !showAddPayment">
                  <Plus class="h-4 w-4 mr-1" />
                  {{ t('invoiceDetail.addPayment') }}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <!-- Add payment form -->
              <div v-if="showAddPayment" class="mb-5 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
                <h3 class="text-sm font-semibold text-gray-700">{{ t('invoiceDetail.newPayment') }}</h3>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.paymentDate') }}</label>
                    <input v-model="paymentForm.payment_date" type="date" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </div>
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.paymentAmount') }}</label>
                    <input v-model="paymentForm.amount" type="number" step="0.01" min="0.01" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </div>
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.paymentType') }}</label>
                    <select v-model="paymentForm.payment_type" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                      <option value="cash">{{ t('invoiceDetail.payCash') }}</option>
                      <option value="employee">{{ t('invoiceDetail.payEmployee') }}</option>
                      <option value="company_account">{{ t('invoiceDetail.payCompany') }}</option>
                      <option value="other">{{ t('invoiceDetail.payOther') }}</option>
                    </select>
                  </div>
                  <div v-if="paymentForm.payment_type === 'employee'">
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.payEmployeeLabel') }}</label>
                    <select v-model="paymentForm.employee_id" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                      <option value="">{{ t('invoiceDetail.selectEmployee') }}</option>
                      <option v-for="emp in employees" :key="emp.id" :value="emp.id">{{ emp.first_name }} {{ emp.last_name }}</option>
                    </select>
                  </div>
                  <div v-else-if="paymentForm.payment_type === 'company_account'" class="col-span-2">
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.bankTxLabel') }}</label>
                    <input
                      v-model="txSearchQuery"
                      type="text"
                      :placeholder="t('invoiceDetail.bankTxPlaceholder')"
                      class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 mb-1"
                    />
                    <div v-if="txSearchResults?.length" class="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-40 overflow-y-auto text-xs">
                      <button
                        v-for="tx in txSearchResults"
                        :key="(tx as any).id"
                        type="button"
                        :class="[
                          'w-full text-left px-3 py-2 hover:bg-blue-50 transition-colors flex items-center justify-between gap-2',
                          paymentForm.bank_transaction_id === (tx as any).id ? 'bg-blue-50 font-medium' : ''
                        ]"
                        @click="paymentForm.bank_transaction_id = (tx as any).id; paymentForm.amount = Math.abs((tx as any).amount); paymentForm.payment_date = (tx as any).transaction_date?.slice(0,10) ?? paymentForm.payment_date"
                      >
                        <span class="truncate">{{ (tx as any).description }}</span>
                        <span class="flex-shrink-0 font-semibold" :class="(tx as any).amount < 0 ? 'text-red-600' : 'text-green-600'">
                          {{ (tx as any).amount < 0 ? '-' : '+' }}{{ Math.abs((tx as any).amount).toFixed(2) }}€
                        </span>
                      </button>
                    </div>
                    <p v-if="paymentForm.bank_transaction_id" class="mt-1 text-xs text-blue-700 font-medium">
                      {{ t('invoiceDetail.bankTxSelected', { n: paymentForm.bank_transaction_id }) }}
                    </p>
                  </div>
                  <div v-else>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('invoiceDetail.payReference') }}</label>
                    <input v-model="paymentForm.reference" type="text" :placeholder="t('invoiceDetail.optionalReference')" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </div>
                  <div class="col-span-2">
                    <label class="block text-xs text-gray-500 mb-1">{{ t('common.notes') }}</label>
                    <input v-model="paymentForm.notes" type="text" :placeholder="t('invoiceDetail.optionalNotes')" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </div>
                </div>
                <p v-if="paymentError" class="text-xs text-red-600">{{ paymentError }}</p>
                <div class="flex gap-2 pt-1">
                  <Button size="sm" :disabled="addPaymentMutation.isPending.value" @click="submitPayment">
                    {{ addPaymentMutation.isPending.value ? t('common.saving') : t('invoiceDetail.savePayment') }}
                  </Button>
                  <Button variant="outline" size="sm" @click="showAddPayment = false; paymentError = ''">{{ t('common.cancel') }}</Button>
                </div>
              </div>

              <!-- Payment list -->
              <div v-if="(invoice.payments?.length ?? 0) === 0 && !showAddPayment" class="text-center py-6 text-gray-400 text-sm">
                {{ t('invoiceDetail.noPayments') }}
              </div>
              <div v-else-if="(invoice.payments?.length ?? 0) > 0" class="divide-y divide-gray-100">
                <div
                  v-for="p in invoice.payments"
                  :key="(p as InvoiceDirectPayment).id"
                  class="flex items-start justify-between py-3"
                >
                  <div class="flex items-start gap-3">
                    <div :class="(p as InvoiceDirectPayment).payment_type === 'cash' ? 'bg-emerald-100 text-emerald-700' : (p as InvoiceDirectPayment).payment_type === 'employee' ? 'bg-purple-100 text-purple-700' : (p as InvoiceDirectPayment).payment_type === 'company_account' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'" class="mt-0.5 rounded-full p-1.5">
                      <Banknote v-if="(p as InvoiceDirectPayment).payment_type === 'cash'" class="h-3.5 w-3.5" />
                      <User v-else-if="(p as InvoiceDirectPayment).payment_type === 'employee'" class="h-3.5 w-3.5" />
                      <Building2 v-else-if="(p as InvoiceDirectPayment).payment_type === 'company_account'" class="h-3.5 w-3.5" />
                      <DollarSign v-else class="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <p class="text-sm font-medium text-gray-900">{{ formatCurrency((p as InvoiceDirectPayment).amount) }}</p>
                      <p class="text-xs text-gray-500">{{ formatDate((p as InvoiceDirectPayment).payment_date) }} · {{ paymentTypeLabel((p as InvoiceDirectPayment).payment_type) }}</p>
                      <p v-if="(p as InvoiceDirectPayment).employee_name" class="text-xs text-purple-600">{{ (p as InvoiceDirectPayment).employee_name }}</p>
                      <p v-if="(p as InvoiceDirectPayment).reference" class="text-xs text-gray-400">{{ (p as InvoiceDirectPayment).reference }}</p>
                      <router-link
                        v-if="(p as InvoiceDirectPayment).bank_transaction_id"
                        :to="`/bank/transactions/${(p as InvoiceDirectPayment).bank_transaction_id}`"
                        class="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-0.5"
                      >
                        <Building2 class="h-3 w-3" />
                        Bank tx #{{ (p as InvoiceDirectPayment).bank_transaction_id }}
                      </router-link>
                      <p v-if="(p as InvoiceDirectPayment).notes" class="text-xs text-gray-400">{{ (p as InvoiceDirectPayment).notes }}</p>
                    </div>
                  </div>
                  <button
                    class="p-1 text-gray-300 hover:text-red-500 transition-colors"
                    :title="t('common.delete')"
                    :disabled="deletePaymentMutation.isPending.value"
                    @click="deletePaymentMutation.mutate((p as InvoiceDirectPayment).id)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Comments -->
          <Card>
            <CardHeader>
              <div class="flex items-center gap-2">
                <MessageSquare class="h-4 w-4 text-gray-500" />
                <CardTitle>{{ t('invoiceDetail.commentsTitle') }}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <!-- Thread -->
              <div v-if="commentsLoading" class="text-center py-4 text-gray-400 text-sm">{{ t('common.loading') }}</div>
              <div v-else-if="!comments?.length" class="text-center py-4 text-gray-400 text-sm">
                {{ t('invoiceDetail.commentsEmpty') }}
              </div>
              <div v-else class="space-y-4 mb-5">
                <div
                  v-for="c in comments"
                  :key="c.id"
                  class="flex gap-3"
                >
                  <!-- Avatar -->
                  <div class="flex-shrink-0 h-8 w-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-semibold uppercase">
                    {{ c.username.slice(0, 2) }}
                  </div>

                  <!-- Bubble -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-baseline gap-2 flex-wrap">
                      <span class="text-sm font-semibold text-gray-900">{{ c.username }}</span>
                      <span class="text-xs text-gray-400">{{ formatCommentDate(c.created_at) }}</span>
                      <span v-if="wasEdited(c)" class="text-xs text-gray-400 italic">({{ t('invoiceDetail.commentsEdited') }})</span>
                    </div>

                    <!-- View mode -->
                    <template v-if="editingCommentId !== c.id">
                      <p class="mt-1 text-sm text-gray-800 whitespace-pre-wrap break-words">{{ c.body }}</p>
                      <div class="flex gap-3 mt-1.5">
                        <button
                          v-if="canEditComment(c)"
                          class="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                          @click="startEditComment(c)"
                        >
                          {{ t('invoiceDetail.commentsEdit') }}
                        </button>
                        <button
                          v-if="canDeleteComment(c)"
                          class="text-xs text-gray-400 hover:text-red-500 transition-colors"
                          :disabled="deleteCommentMutation.isPending.value"
                          @click="deleteCommentMutation.mutate(c.id)"
                        >
                          {{ t('invoiceDetail.commentsDelete') }}
                        </button>
                      </div>
                    </template>

                    <!-- Edit mode -->
                    <template v-else>
                      <textarea
                        v-model="editingCommentBody"
                        rows="2"
                        class="mt-1 w-full px-3 py-2 border border-blue-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
                        @keydown.enter.ctrl="saveCommentEdit(c.id)"
                      />
                      <div class="flex gap-2 mt-1.5">
                        <button
                          class="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                          :disabled="updateCommentMutation.isPending.value"
                          @click="saveCommentEdit(c.id)"
                        >
                          {{ t('invoiceDetail.commentsEditSave') }}
                        </button>
                        <button
                          class="text-xs px-3 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
                          @click="editingCommentId = null"
                        >
                          {{ t('invoiceDetail.commentsEditCancel') }}
                        </button>
                      </div>
                    </template>
                  </div>
                </div>
              </div>

              <!-- New comment input -->
              <div class="flex gap-3 items-start pt-4 border-t border-gray-100">
                <div class="flex-shrink-0 h-8 w-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-semibold uppercase">
                  {{ authStore.user?.username?.slice(0, 2) ?? '?' }}
                </div>
                <div class="flex-1">
                  <textarea
                    v-model="newCommentBody"
                    :placeholder="t('invoiceDetail.commentsPlaceholder')"
                    rows="2"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
                    @keydown.enter.ctrl="submitComment"
                  />
                  <p v-if="commentError" class="text-xs text-red-600 mt-1">{{ commentError }}</p>
                  <div class="flex justify-end mt-2">
                    <button
                      class="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      :disabled="!newCommentBody.trim() || addCommentMutation.isPending.value"
                      @click="submitComment"
                    >
                      <Send class="h-3.5 w-3.5" />
                      {{ t('invoiceDetail.commentsSend') }}
                    </button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

      </div>
    </template>

    <!-- Bank Transaction Modal -->
    <Teleport to="body">
      <div
        v-if="showTxModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/50" @click="showTxModal = false" />

        <!-- Panel -->
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
            <div v-else-if="txData || invoice?.expense_report" class="space-y-4">
              <div v-if="txData" class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
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

              <!-- Expense Report section -->
              <div v-if="invoice?.expense_report" :class="txData ? 'border-t pt-4' : ''">
                <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">{{ t('invoices.bankTxModal.expenseReport') }}</p>
                <div class="bg-gray-50 rounded-lg p-3 space-y-2 text-sm">
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-medium text-gray-900">{{ invoice.expense_report.title }}</span>
                    <span
                      class="px-2 py-0.5 rounded-full text-xs font-medium capitalize"
                      :class="{
                        'bg-green-100 text-green-700': invoice.expense_report.status === 'paid',
                        'bg-blue-100 text-blue-700': invoice.expense_report.status === 'approved',
                        'bg-yellow-100 text-yellow-700': invoice.expense_report.status === 'submitted',
                        'bg-gray-100 text-gray-600': invoice.expense_report.status === 'draft',
                      }"
                    >{{ invoice.expense_report.status }}</span>
                  </div>
                  <div v-if="invoice.expense_report.expense_id" class="text-gray-500">
                    {{ invoice.expense_report.expense_id }}
                  </div>
                  <div v-if="invoice.expense_report.employee_name" class="text-gray-600">
                    {{ t('invoices.bankTxModal.expenseEmployee') }}: {{ invoice.expense_report.employee_name }}
                  </div>
                  <div v-if="invoice.expense_report.paid_at" class="text-gray-600">
                    {{ t('invoices.bankTxModal.expensePaidAt') }}: {{ formatDate(String(invoice.expense_report.paid_at)) }}
                  </div>
                </div>
              </div>
            </div>
            <p v-else class="text-center py-8 text-gray-400">{{ t('invoices.bankTxModal.couldNotLoad') }}</p>
          </div>

          <!-- Footer -->
          <div class="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
            <router-link
              v-if="invoice?.bank_transaction_id"
              :to="`/bank?highlight=${invoice.bank_transaction_id}`"
              class="inline-flex items-center gap-1.5 text-sm text-emerald-700 hover:text-emerald-900 font-medium"
              @click="showTxModal = false"
            >
              <ExternalLink class="h-4 w-4" />
              {{ t('invoices.bankTxModal.openInBank') }}
            </router-link>
            <router-link
              v-if="invoice?.expense_report"
              :to="`/expenses/reports/${invoice.expense_report.id}`"
              class="inline-flex items-center gap-1.5 text-sm text-blue-700 hover:text-blue-900 font-medium"
              @click="showTxModal = false"
            >
              <ExternalLink class="h-4 w-4" />
              {{ t('invoices.bankTxModal.openExpenseReport') }}
            </router-link>
            <Button variant="outline" @click="showTxModal = false">{{ t('common.close') }}</Button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
