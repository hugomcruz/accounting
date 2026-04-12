<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import {
  ArrowLeft, Plus, Send, Check, X, Trash2, Upload,
  FileText, Edit2, Save, AlertCircle, Sparkles, Loader2,
  RotateCcw, Receipt,
} from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { expensesApi } from '@/services/queries'
import { useAuthStore } from '@/stores/auth'
import type { ExpenseReport, ExpenseItem } from '@/types'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const { t } = useI18n()
const auth = useAuthStore()
const isUser = computed(() => auth.isUser)
const reportId = Number(route.params.id)

// ─── Query ───────────────────────────────────────────────────────────────────
const { data: report, isLoading } = useQuery({
  queryKey: ['expense-report', reportId],
  queryFn: async () => {
    const res = await expensesApi.getReport(reportId)
    return res.data as ExpenseReport
  },
})

const isDraft = computed(() => report.value?.status === 'draft')
const isSubmitted = computed(() => report.value?.status === 'submitted')
const isRejected = computed(() => report.value?.status === 'rejected')
const isPaid = computed(() => report.value?.status === 'paid')

// ─── Edit report title/description ───────────────────────────────────────────
const editing = ref(false)
const editForm = ref({ title: '', description: '' })

function startEdit() {
  editForm.value = { title: report.value!.title, description: report.value!.description ?? '' }
  editing.value = true
}

const updateMutation = useMutation({
  mutationFn: () => expensesApi.updateReport(reportId, {
    title: editForm.value.title,
    description: editForm.value.description || undefined,
  }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] })
    editing.value = false
  },
})

// ─── Add item ────────────────────────────────────────────────────────────────
// ─── Multi-file staged upload ─────────────────────────────────────────────────

interface StagedItem {
  _id: string
  file: File
  file_path: string | null
  file_url: string | null
  qr_data_json: string | null
  qr_extracted: boolean
  parsing: boolean
  error: string | null
  description: string
  category: string
  amount: number | ''
  currency: string
  eur_amount: number | ''
  expense_date: string
  notes: string
}

const multiFileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)
const stagedItems = ref<StagedItem[]>([])
const showAddArea = ref(false)
const savingStaged = ref(false)
const stagedErrors = ref<Record<string, string>>({})

function parseQRDate(d: string): string {
  if (d && d.length === 8) {
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
  }
  return d
}

async function processStagedFile(itemId: string, file: File) {
  // Always look up through stagedItems.value so mutations go via the reactive proxy
  const getItem = () => stagedItems.value.find(i => i._id === itemId)
  try {
    const res = await expensesApi.parseInvoice(file, reportId)
    const data = res.data
    const item = getItem()
    if (!item) return
    item.file_path = data.file_path
    if (data.qr_data) {
      item.qr_extracted = true
      item.qr_data_json = JSON.stringify(data.qr_data)
      const qr = data.qr_data as Record<string, unknown>
      if (qr.total_documento) item.amount = qr.total_documento as number
      if (typeof qr.data_documento === 'string' && qr.data_documento) {
        item.expense_date = parseQRDate(qr.data_documento)
      }
    }
  } catch {
    const item = getItem()
    if (item) item.error = 'Failed to read invoice'
  } finally {
    const item = getItem()
    if (item) item.parsing = false
  }
}

function addFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    const item: StagedItem = {
      _id: Math.random().toString(36).slice(2),
      file,
      file_path: null,
      file_url: null,
      qr_data_json: null,
      qr_extracted: false,
      parsing: true,
      error: null,
      description: file.name.replace(/\.[^/.]+$/, ''),
      category: '',
      amount: '',
      currency: 'EUR',
      eur_amount: '',
      expense_date: new Date().toISOString().slice(0, 10),
      notes: '',
    }
    stagedItems.value.push(item)
    processStagedFile(item._id, item.file)
  }
}

function onMultiDrop(e: DragEvent) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) addFiles(files)
}

function onMultiFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) addFiles(files)
  ;(e.target as HTMLInputElement).value = ''
}

function removeStagedItem(id: string) {
  stagedItems.value = stagedItems.value.filter(i => i._id !== id)
}

const canSaveStaged = computed(() =>
  stagedItems.value.some(i =>
    !i.parsing && !!i.description && !!i.amount && !!i.expense_date &&
    (i.currency === 'EUR' || !!i.eur_amount)
  )
)

async function saveAllStaged() {
  savingStaged.value = true
  stagedErrors.value = {}
  const toSave = stagedItems.value.filter(i => !i.parsing && !!i.description && !!i.amount && !!i.expense_date)
  for (const item of toSave) {
    try {
      const fd = new FormData()
      fd.append('description', item.description)
      fd.append('amount', String(item.amount))
      fd.append('expense_date', item.expense_date)
      if (item.category) fd.append('category', item.category)
      fd.append('currency', item.currency)
      if (item.currency !== 'EUR' && item.eur_amount !== '') fd.append('eur_amount', String(item.eur_amount))
      if (item.notes) fd.append('notes', item.notes)
      if (item.file_path) {
        fd.append('file_path', item.file_path)
        fd.append('original_filename', item.file.name)
        if (item.qr_data_json) fd.append('qr_data_json', item.qr_data_json)
      } else {
        fd.append('file', item.file)
      }
      await expensesApi.addItem(reportId, fd)
      stagedItems.value = stagedItems.value.filter(i => i._id !== item._id)
    } catch (e: any) {
      stagedErrors.value[item._id] = e?.response?.data?.detail ?? 'Failed to save'
    }
  }
  savingStaged.value = false
  queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] })
  if (stagedItems.value.length === 0) showAddArea.value = false
}

// ─── Receipt preview modal ────────────────────────────────────────────────────
const previewUrl = ref<string | null>(null)
const previewIsPdf = ref(false)
const previewLoading = ref(false)

function openStagedPreview(item: StagedItem) {
  const url = URL.createObjectURL(item.file)
  previewUrl.value = url
  previewIsPdf.value = item.file.name.toLowerCase().endsWith('.pdf')
}

async function openSavedPreview(itemId: number, filename: string) {
  previewLoading.value = true
  previewUrl.value = null
  previewIsPdf.value = filename.toLowerCase().endsWith('.pdf')
  try {
    const res = await expensesApi.fetchItemBlob(itemId)
    previewUrl.value = URL.createObjectURL(res.data as Blob)
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null
  previewIsPdf.value = false
  previewLoading.value = false
}

// ─── Delete item ─────────────────────────────────────────────────────────────
const deleteItemMutation = useMutation({
  mutationFn: (itemId: number) => expensesApi.deleteItem(itemId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] }),
})

function confirmDeleteItem(item: ExpenseItem) {
  if (confirm(t('expenseDetail.removeConfirm', { desc: item.description }))) deleteItemMutation.mutate(item.id)
}
// ─── Edit item ─────────────────────────────────────────────────────────────────
const editingItem = ref<ExpenseItem | null>(null)
const editFileInput = ref<HTMLInputElement | null>(null)
const editParseLoading = ref(false)
const editParsedFilePath = ref<string | null>(null)
const editParsedQrDataJson = ref<string | null>(null)
const editQrExtracted = ref(false)
const editPreviewUrl = ref<string | null>(null)
const editPreviewIsPdf = ref(false)
const editItemForm = ref({
  description: '',
  category: '',
  amount: '' as number | '',
  currency: 'EUR',
  eur_amount: '' as number | '',
  expense_date: '',
  notes: '',
  newFile: null as File | null,
})

const autoEditExchangeRate = computed(() => {
  if (editItemForm.value.currency === 'EUR') return null
  const fc = parseFloat(String(editItemForm.value.amount))
  const eur = parseFloat(String(editItemForm.value.eur_amount))
  if (fc > 0 && eur > 0) return (fc / eur).toFixed(6)
  return null
})

const canUpdateItem = computed(() =>
  !!editItemForm.value.description && !!editItemForm.value.amount && !!editItemForm.value.expense_date &&
  (editItemForm.value.currency === 'EUR' || !!editItemForm.value.eur_amount)
)

function setEditPreview(url: string | null, isPdf: boolean) {
  if (editPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(editPreviewUrl.value)
  editPreviewUrl.value = url
  editPreviewIsPdf.value = isPdf
}

async function startEditItem(item: ExpenseItem) {
  editingItem.value = item
  editParsedFilePath.value = null
  editParsedQrDataJson.value = null
  editQrExtracted.value = false
  editItemForm.value = {
    description: item.description,
    category: item.category ?? '',
    amount: item.amount,
    currency: item.currency,
    eur_amount: item.eur_amount ?? '',
    expense_date: item.expense_date.slice(0, 10),
    notes: item.notes ?? '',
    newFile: null,
  }
  const fname = (item.original_filename ?? '').toLowerCase()
  const isPdf = fname.endsWith('.pdf')
  setEditPreview(null, isPdf)
  editParseLoading.value = true
  try {
    const res = await expensesApi.fetchItemBlob(item.id)
    setEditPreview(URL.createObjectURL(res.data as Blob), isPdf)
  } catch {
    // leave preview empty
  } finally {
    editParseLoading.value = false
  }
}

function cancelEditItem() {
  setEditPreview(null, false)
  editingItem.value = null
}

async function processEditFile(file: File) {
  editItemForm.value.newFile = file
  editParsedFilePath.value = null
  editParsedQrDataJson.value = null
  editQrExtracted.value = false
  editParseLoading.value = true
  try {
    const res = await expensesApi.parseInvoice(file, reportId)
    const data = res.data
    editParsedFilePath.value = data.file_path
    const fileUrl = (data as any).file_url ?? null
    const isPdf = file.name.toLowerCase().endsWith('.pdf')
    setEditPreview(fileUrl, isPdf)
    if (data.qr_data) {
      editQrExtracted.value = true
      editParsedQrDataJson.value = JSON.stringify(data.qr_data)
      const qr = data.qr_data as Record<string, unknown>
      if (qr.total_documento) editItemForm.value.amount = qr.total_documento as number
      if (typeof qr.data_documento === 'string' && qr.data_documento) {
        editItemForm.value.expense_date = parseQRDate(qr.data_documento)
      }
    }
  } catch {
    // parse failed
  } finally {
    editParseLoading.value = false
  }
}

function onEditFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) return
  processEditFile(file)
}

const updateItemMutation = useMutation({
  mutationFn: () => {
    const fd = new FormData()
    fd.append('description', editItemForm.value.description)
    fd.append('amount', String(editItemForm.value.amount))
    fd.append('expense_date', editItemForm.value.expense_date)
    if (editItemForm.value.category) fd.append('category', editItemForm.value.category)
    fd.append('currency', editItemForm.value.currency)
    if (editItemForm.value.currency !== 'EUR' && editItemForm.value.eur_amount !== '') {
      fd.append('eur_amount', String(editItemForm.value.eur_amount))
      if (autoEditExchangeRate.value) fd.append('exchange_rate', autoEditExchangeRate.value)
    }
    if (editItemForm.value.notes) fd.append('notes', editItemForm.value.notes)
    if (editParsedFilePath.value) {
      fd.append('file_path', editParsedFilePath.value)
      fd.append('original_filename', editItemForm.value.newFile?.name ?? '')
      if (editParsedQrDataJson.value) fd.append('qr_data_json', editParsedQrDataJson.value)
    } else if (editItemForm.value.newFile) {
      fd.append('file', editItemForm.value.newFile)
    }
    return expensesApi.updateItem(editingItem.value!.id, fd)
  },
  onSuccess: () => {
    setEditPreview(null, false)
    queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] })
    editingItem.value = null
    editParsedFilePath.value = null
    editParsedQrDataJson.value = null
    editQrExtracted.value = false
    if (editFileInput.value) editFileInput.value.value = ''
  },
})
// ─── Submit ───────────────────────────────────────────────────────────────────
const submitMutation = useMutation({
  mutationFn: () => expensesApi.submitReport(reportId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] }),
})

// ─── Approve / Reject ────────────────────────────────────────────────────────
const showRejectModal = ref(false)
const rejectNotes = ref('')

const approveMutation = useMutation({
  mutationFn: () => expensesApi.approveReport(reportId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] }),
})

const rejectMutation = useMutation({
  mutationFn: () => expensesApi.rejectReport(reportId, rejectNotes.value || undefined),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] })
    showRejectModal.value = false
    rejectNotes.value = ''
  },
})

const reviseMutation = useMutation({
  mutationFn: () => expensesApi.reviseReport(reportId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expense-report', reportId] }),
})

// ─── Helpers ─────────────────────────────────────────────────────────────────
const statusConfig: Record<string, { label: string; classes: string }> = {
  draft:     { label: 'Draft',     classes: 'bg-gray-100 text-gray-600' },
  submitted: { label: 'Submitted', classes: 'bg-blue-100 text-blue-700' },
  approved:  { label: 'Approved',  classes: 'bg-green-100 text-green-700' },
  rejected:  { label: 'Rejected',  classes: 'bg-red-100 text-red-700' },
  paid:      { label: 'Paid',      classes: 'bg-purple-100 text-purple-700' },
}

const categories = ['Travel', 'Meals', 'Accommodation', 'Office Supplies', 'Software', 'Other']

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString()
}

function fmtAmount(v: number, currency = 'EUR') {
  return new Intl.NumberFormat('pt-PT', { style: 'currency', currency }).format(v)
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <button class="text-gray-400 hover:text-gray-600" @click="router.back()">
        <ArrowLeft class="h-5 w-5" />
      </button>
      <div class="flex-1 min-w-0">
        <div v-if="!editing" class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-gray-900 truncate">{{ report?.title }}</h1>
          <span
            v-if="report"
            :class="['px-2 py-0.5 rounded-full text-xs font-medium', statusConfig[report.status]?.classes]"
          >
            {{ statusConfig[report.status]?.label }}
          </span>
          <span v-if="report?.expense_id" class="px-2 py-0.5 rounded text-xs font-mono font-medium bg-gray-100 text-gray-500 select-all">
            {{ report.expense_id }}
          </span>
          <button v-if="isDraft" class="text-gray-400 hover:text-primary-600" @click="startEdit">
            <Edit2 class="h-4 w-4" />
          </button>
        </div>
        <div v-else class="flex items-center gap-2">
          <input
            v-model="editForm.title"
            class="flex-1 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <Button class="py-1.5 px-3 text-sm" :disabled="updateMutation.isPending.value" @click="updateMutation.mutate()">
            <Save class="h-3.5 w-3.5 mr-1" /> {{ t('common.save') }}
          </Button>
          <Button variant="secondary" class="py-1.5 px-3 text-sm" @click="editing = false">{{ t('common.cancel') }}</Button>
        </div>
        <p v-if="report" class="text-sm text-gray-500 mt-0.5">
          {{ report.employee_name }} ·
          Created {{ fmt(report.created_at) }}
          <span v-if="report.submitted_at"> · Submitted {{ fmt(report.submitted_at) }}</span>
          <span v-if="report.approved_at"> · Approved {{ fmt(report.approved_at) }}</span>
          <span v-if="report.paid_at" class="text-purple-700 font-medium"> · Paid {{ fmt(report.paid_at) }}</span>
        </p>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-16 text-gray-400">{{ t('expenseDetail.loading') }}</div>

    <template v-else-if="report">
      <!-- Description -->
      <div v-if="report.description && !editing" class="text-sm text-gray-600 bg-gray-50 rounded-lg px-4 py-3">
        {{ report.description }}
      </div>
      <div v-if="editing" class="bg-gray-50 rounded-lg px-4 py-3">
        <label class="block text-xs font-medium text-gray-500 mb-1">Description</label>
        <textarea
          v-model="editForm.description"
          rows="2"
          class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
        />
      </div>

      <!-- Reviewer notes (rejected) -->
      <div
        v-if="report.status === 'rejected' && report.notes"
        class="flex gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700"
      >
        <AlertCircle class="h-4 w-4 flex-shrink-0 mt-0.5" />
        <span><strong>{{ t('expenseDetail.rejectionNote') }}</strong> {{ report.notes }}</span>
      </div>

      <!-- Action bar -->
      <div class="flex flex-wrap gap-2">
        <!-- Draft: add item + submit -->
        <template v-if="isDraft">
          <Button @click="showAddArea = !showAddArea">
            <Plus class="h-4 w-4 mr-1" /> {{ t('expenseDetail.addExpense') }}
          </Button>
          <Button
            v-if="report.items.length > 0"
            variant="secondary"
            :disabled="submitMutation.isPending.value"
            @click="submitMutation.mutate()"
          >
            <Send class="h-4 w-4 mr-1" />
            {{ submitMutation.isPending.value ? t('expenseDetail.submitting') : t('expenseDetail.submitApproval') }}
          </Button>
        </template>

        <!-- Submitted: approve / reject (hidden for user role) -->
        <template v-if="isSubmitted && !isUser">
          <Button
            class="bg-green-600 hover:bg-green-700"
            :disabled="approveMutation.isPending.value"
            @click="approveMutation.mutate()"
          >
            <Check class="h-4 w-4 mr-1" /> {{ t('expenseDetail.approve') }}
          </Button>
          <Button
            variant="secondary"
            class="text-red-600 border-red-300 hover:bg-red-50"
            @click="showRejectModal = true"
          >
            <X class="h-4 w-4 mr-1" /> {{ t('expenseDetail.reject') }}
          </Button>
        </template>

        <!-- Rejected: revise (move back to draft for editing) -->
        <template v-if="isRejected">
          <Button
            variant="secondary"
            :disabled="reviseMutation.isPending.value"
            @click="reviseMutation.mutate()"
          >
            <RotateCcw class="h-4 w-4 mr-1" />
            {{ reviseMutation.isPending.value ? t('expenseDetail.revising') : t('expenseDetail.revise') }}
          </Button>
        </template>
      </div>

      <!-- ── Add expenses area ──────────────────────────────────────────────── -->
      <Card v-if="showAddArea && isDraft">
        <CardHeader>
          <div class="flex items-center justify-between">
            <CardTitle class="text-base">{{ t('expenseDetail.addExpense') }}</CardTitle>
            <button class="text-gray-400 hover:text-gray-600" @click="showAddArea = false; stagedItems = []">
              <X class="h-4 w-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent class="space-y-4">

          <!-- Multi-file drop zone -->
          <div
            class="flex flex-col items-center justify-center gap-2 px-4 py-8 border-2 border-dashed rounded-lg cursor-pointer transition-colors text-sm"
            :class="isDragging ? 'border-primary-500 bg-primary-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'"
            @click="multiFileInput?.click()"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onMultiDrop"
          >
            <Upload class="h-7 w-7 text-gray-400" />
            <span class="text-gray-600 font-medium">
              {{ isDragging ? t('expenseDetail.dropHere') : t('expenseDetail.clickOrDragMultiple') }}
            </span>
            <span class="text-xs text-gray-400">{{ t('expenseDetail.fileTypes') }}</span>
            <input ref="multiFileInput" type="file" multiple accept=".pdf,.png,.jpg,.jpeg" class="hidden" @change="onMultiFileChange" />
          </div>

          <!-- Staged items table -->
          <div v-if="stagedItems.length" class="overflow-x-auto rounded-lg border border-gray-200">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <th class="px-3 py-2">Receipt</th>
                  <th class="px-3 py-2 min-w-[180px]">{{ t('expenseDetail.descriptionRequired') }}</th>
                  <th class="px-3 py-2 min-w-[130px]">{{ t('expenseDetail.categoryLabel') }}</th>
                  <th class="px-3 py-2 min-w-[130px]">{{ t('expenseDetail.dateRequired') }}</th>
                  <th class="px-3 py-2 min-w-[150px]">{{ t('expenseDetail.amountRequired') }}</th>
                  <th class="px-3 py-2 min-w-[80px]">{{ t('expenseDetail.notesLabel') }}</th>
                  <th class="px-3 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="item in stagedItems" :key="item._id" class="hover:bg-gray-50">
                  <!-- File status / receipt preview -->
                  <td class="px-3 py-2">
                    <div class="flex items-center gap-1.5">
                      <template v-if="item.parsing">
                        <Loader2 class="h-4 w-4 animate-spin text-primary-500 flex-shrink-0" />
                        <span class="text-xs text-gray-400 truncate max-w-[80px]" :title="item.file.name">{{ item.file.name }}</span>
                      </template>
                      <template v-else>
                        <button
                          class="inline-flex w-7 h-7 rounded bg-blue-50 items-center justify-center hover:bg-blue-100 transition-colors flex-shrink-0"
                          :title="item.file.name"
                          @click="openStagedPreview(item)"
                        >
                          <Receipt class="h-3.5 w-3.5 text-blue-600" />
                        </button>
                        <Sparkles v-if="item.qr_extracted" class="h-3 w-3 text-green-500 flex-shrink-0" :title="t('expenseDetail.qrDetected')" />
                        <span class="text-xs text-gray-400 truncate max-w-[80px]" :title="item.file.name">{{ item.file.name }}</span>
                      </template>
                    </div>
                    <p v-if="item.error" class="text-xs text-red-500 mt-0.5">{{ item.error }}</p>
                    <p v-if="stagedErrors[item._id]" class="text-xs text-red-500 mt-0.5">{{ stagedErrors[item._id] }}</p>
                  </td>
                  <!-- Description -->
                  <td class="px-3 py-2">
                    <input v-model="item.description" type="text" placeholder="Description"
                      class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </td>
                  <!-- Category -->
                  <td class="px-3 py-2">
                    <select v-model="item.category"
                      class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                      <option value="">—</option>
                      <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
                    </select>
                  </td>
                  <!-- Date -->
                  <td class="px-3 py-2">
                    <input v-model="item.expense_date" type="date"
                      class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </td>
                  <!-- Amount + currency -->
                  <td class="px-3 py-2">
                    <div class="flex gap-1">
                      <input v-model="item.amount" type="number" min="0" step="0.01" placeholder="0.00"
                        class="w-24 px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                      <select v-model="item.currency"
                        class="px-1 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                        <option>EUR</option><option>USD</option><option>GBP</option><option>CHF</option>
                        <option>JPY</option><option>CAD</option><option>AUD</option>
                      </select>
                    </div>
                    <div v-if="item.currency !== 'EUR'" class="mt-1">
                      <input v-model="item.eur_amount" type="number" min="0" step="0.01" placeholder="EUR equiv."
                        class="w-full px-2 py-1 border border-amber-300 rounded text-xs focus:outline-none focus:ring-2 focus:ring-amber-400" />
                    </div>
                  </td>
                  <!-- Notes -->
                  <td class="px-3 py-2">
                    <input v-model="item.notes" type="text" placeholder="Notes"
                      class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  </td>
                  <!-- Remove -->
                  <td class="px-3 py-2 text-center">
                    <button class="text-gray-300 hover:text-red-500 transition-colors" @click="removeStagedItem(item._id)">
                      <Trash2 class="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="flex gap-2 justify-end">
            <Button variant="secondary" @click="showAddArea = false; stagedItems = []">{{ t('common.cancel') }}</Button>
            <Button :disabled="!canSaveStaged || savingStaged" @click="saveAllStaged">
              <Loader2 v-if="savingStaged" class="h-4 w-4 mr-1.5 animate-spin" />
              {{ savingStaged ? t('expenseDetail.savingItem') : t('expenseDetail.saveExpenses', { n: stagedItems.filter(i => !i.parsing && !!i.amount).length }) }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- ── Expense items table ─────────────────────────────────────────────── -->
      <Card>
        <CardHeader>
          <div class="flex items-center justify-between">
            <CardTitle class="text-base">{{ t('expenseDetail.itemsCard') }}</CardTitle>
            <span class="text-sm font-semibold text-gray-900">
              {{ t('expenseDetail.itemsTotal', { amount: fmtAmount(report.total_amount) }) }}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div v-if="!report.items.length" class="text-sm text-gray-400 text-center py-6">
            {{ t('expenseDetail.noItems') }}
            <span v-if="isDraft"> {{ t('expenseDetail.noItemsHint') }}</span>
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <th class="pb-2 font-medium w-8"></th>
                  <th class="pb-2 font-medium">{{ t('expenseDetail.dateRequired') }}</th>
                  <th class="pb-2 font-medium">{{ t('expenseDetail.descriptionRequired') }}</th>
                  <th class="pb-2 font-medium">{{ t('expenseDetail.categoryLabel') }}</th>
                  <th class="pb-2 font-medium text-right">{{ t('expenseDetail.amountRequired') }}</th>
                  <th class="pb-2 font-medium hidden md:table-cell">{{ t('expenseDetail.notesLabel') }}</th>
                  <th v-if="isDraft" class="pb-2 font-medium w-16"></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in report.items"
                  :key="item.id"
                  class="border-b last:border-0 hover:bg-gray-50 transition-colors"
                  :class="isDraft ? 'cursor-pointer' : ''"
                  @click="isDraft ? startEditItem(item) : undefined"
                >
                  <td class="py-2.5 pr-2" @click.stop>
                    <button
                      class="inline-flex w-7 h-7 rounded bg-blue-50 items-center justify-center hover:bg-blue-100 transition-colors"
                      :title="t('expenseDetail.viewReceipt')"
                      @click="openSavedPreview(item.id, item.original_filename ?? '')"
                    >
                      <Receipt class="h-3.5 w-3.5 text-blue-600" />
                    </button>
                  </td>
                  <td class="py-2.5 pr-3 text-gray-500 whitespace-nowrap text-xs">{{ fmt(item.expense_date) }}</td>
                  <td class="py-2.5 pr-3">
                    <p class="font-medium text-gray-900 truncate max-w-xs">{{ item.description }}</p>
                  </td>
                  <td class="py-2.5 pr-3">
                    <span v-if="item.category" class="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs font-medium">
                      {{ item.category }}
                    </span>
                    <span v-else class="text-xs text-gray-300">—</span>
                  </td>
                  <td class="py-2.5 pr-3 text-right font-semibold text-gray-900 whitespace-nowrap">
                    {{ fmtAmount(item.amount, item.currency) }}
                    <template v-if="item.currency !== 'EUR' && item.eur_amount">
                      <br /><span class="text-xs font-normal text-gray-400">≈ {{ fmtAmount(item.eur_amount) }}</span>
                    </template>
                  </td>
                  <td class="py-2.5 pr-3 text-xs text-gray-400 hidden md:table-cell max-w-[160px]">
                    <span class="truncate block">{{ item.notes || '—' }}</span>
                  </td>
                  <td v-if="isDraft" class="py-2.5 text-right" @click.stop>
                    <div class="flex items-center justify-end gap-1">
                      <button class="text-gray-300 hover:text-primary-500 transition-colors p-1" :title="t('expenseDetail.editItem')" @click="startEditItem(item)">
                        <Edit2 class="h-3.5 w-3.5" />
                      </button>
                      <button class="text-gray-300 hover:text-red-500 transition-colors p-1" :title="t('expenseDetail.removeItem')" @click="confirmDeleteItem(item)">
                        <Trash2 class="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <!-- Edit expense item form -->
      <Card v-if="editingItem && isDraft">
        <CardHeader>
          <div class="flex items-center justify-between">
            <CardTitle class="text-base">{{ t('expenseDetail.editItemCard') }}</CardTitle>
            <button class="text-gray-400 hover:text-gray-600" @click="cancelEditItem">
              <X class="h-4 w-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Left: file preview -->
            <div class="flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">{{ t('expenseDetail.invoicePreview') }}</p>
                <button
                  v-if="!editParseLoading"
                  class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
                  @click="editFileInput?.click()"
                >
                  <Upload class="h-3.5 w-3.5" /> {{ t('expenseDetail.replaceFile') }}
                </button>
              </div>
              <input ref="editFileInput" type="file" accept=".pdf,.png,.jpg,.jpeg" class="hidden" @change="onEditFileChange" />
              <div class="border rounded-lg overflow-hidden bg-gray-50 flex-1" style="min-height: 420px; max-height: 600px">
                <div v-if="editParseLoading" class="flex items-center justify-center h-full" style="min-height: 420px">
                  <Loader2 class="h-8 w-8 animate-spin text-primary-500" />
                </div>
                <template v-else-if="editPreviewUrl">
                  <iframe
                    v-if="editPreviewIsPdf"
                    :src="editPreviewUrl"
                    class="w-full h-full border-0"
                    style="min-height: 420px"
                    title="Invoice Preview"
                  />
                  <img v-else :src="editPreviewUrl" class="w-full h-full object-contain" :alt="editingItem.original_filename ?? undefined" />
                </template>
                <div v-else class="flex items-center justify-center h-full text-gray-400 text-sm" style="min-height: 420px">
                  <FileText class="h-10 w-10" />
                </div>
              </div>
              <div v-if="editQrExtracted" class="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1.5">
                <Sparkles class="h-3.5 w-3.5 flex-shrink-0" />
                {{ t('expenseDetail.qrDetected') }}
              </div>
            </div>

            <!-- Right: form fields -->
            <div class="space-y-3">
              <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">{{ t('expenseDetail.expenseDetails') }}</p>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.descriptionRequired') }}</label>
                <input v-model="editItemForm.description" type="text" :placeholder="t('expenseDetail.descriptionPlaceholder')"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>

              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.categoryLabel') }}</label>
                  <select v-model="editItemForm.category"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                    <option value="">{{ t('expenseDetail.selectCategory') }}</option>
                    <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.dateRequired') }}</label>
                  <input v-model="editItemForm.expense_date" type="date"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.amountRequired') }}</label>
                <div class="flex gap-2">
                  <input v-model="editItemForm.amount" type="number" min="0" step="0.01" placeholder="0.00"
                    class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  <select v-model="editItemForm.currency"
                    class="px-2 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                    <option>EUR</option><option>USD</option><option>GBP</option><option>CHF</option>
                    <option>JPY</option><option>CAD</option><option>AUD</option><option>SEK</option>
                    <option>DKK</option><option>NOK</option><option>PLN</option><option>CZK</option>
                  </select>
                </div>
              </div>

              <div v-if="editItemForm.currency !== 'EUR'">
                <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.eurEquivalent') }}</label>
                <input v-model="editItemForm.eur_amount" type="number" min="0" step="0.01" placeholder="0.00"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                <div v-if="autoEditExchangeRate" class="mt-1.5 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                  Exchange rate: 1 EUR = {{ autoEditExchangeRate }} {{ editItemForm.currency }}
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('expenseDetail.notesLabel') }}</label>
                <input v-model="editItemForm.notes" type="text" :placeholder="t('expenseDetail.notesPlaceholder')"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
            </div>
          </div>

          <p v-if="updateItemMutation.isError.value" class="text-sm text-red-600 flex items-center gap-1">
            <AlertCircle class="h-4 w-4" />
            {{ (updateItemMutation.error.value as any)?.response?.data?.detail ?? t('expenseDetail.failedUpdate') }}
          </p>
          <div class="flex gap-2 justify-end">
            <Button variant="secondary" @click="cancelEditItem">{{ t('common.cancel') }}</Button>
            <Button
              :disabled="!canUpdateItem || updateItemMutation.isPending.value"
              @click="updateItemMutation.mutate()"
            >
              {{ updateItemMutation.isPending.value ? t('expenseDetail.savingItem') : t('common.save') }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </template>

    <!-- Reject modal -->
    <Teleport to="body">
      <div
        v-if="showRejectModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        @click.self="showRejectModal = false"
      >
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900">{{ t('expenseDetail.rejectModal') }}</h2>
          <p class="text-sm text-gray-500">{{ t('expenseDetail.rejectHint') }}</p>
          <textarea
            v-model="rejectNotes"
            rows="3"
            :placeholder="t('expenseDetail.rejectPlaceholder')"
            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <div class="flex gap-2 justify-end">
            <Button variant="secondary" @click="showRejectModal = false">{{ t('common.cancel') }}</Button>
            <Button
              class="bg-red-600 hover:bg-red-700"
              :disabled="rejectMutation.isPending.value"
              @click="rejectMutation.mutate()"
            >
              {{ rejectMutation.isPending.value ? t('expenseDetail.rejecting') : t('expenseDetail.confirmReject') }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Receipt preview modal ──────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="previewUrl !== null || previewLoading"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        @click.self="closePreview"
      >
        <div class="relative bg-white rounded-xl shadow-2xl flex flex-col" style="width: min(92vw, 860px); max-height: 90vh">
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-3 border-b">
            <span class="text-sm font-medium text-gray-700">{{ t('expenseDetail.invoicePreview') }}</span>
            <button class="text-gray-400 hover:text-gray-700 transition-colors" @click="closePreview">
              <X class="h-5 w-5" />
            </button>
          </div>
          <!-- Body -->
          <div class="flex-1 overflow-hidden" style="min-height: 200px">
            <div v-if="previewLoading" class="flex items-center justify-center h-64">
              <Loader2 class="h-8 w-8 animate-spin text-primary-500" />
            </div>
            <template v-else-if="previewUrl">
              <iframe
                v-if="previewIsPdf"
                :src="previewUrl"
                class="w-full border-0"
                style="height: calc(90vh - 60px)"
                title="Receipt preview"
              />
              <img
                v-else
                :src="previewUrl"
                class="w-full h-full object-contain"
                style="max-height: calc(90vh - 60px)"
                alt="Receipt preview"
              />
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
