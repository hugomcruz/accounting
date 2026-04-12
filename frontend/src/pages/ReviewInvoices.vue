<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { AlertCircle, CheckCircle, Clock, FileText, X, Play, Upload, Trash2, FileScan, FileWarning, ZoomIn, ZoomOut, RotateCcw } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { invoiceQueueApi } from '@/services/queries'
import { formatDateTime, formatCurrency, parsePortugueseNumber, formatPortugueseNumber } from '@/lib/utils'
import type { InvoiceProcessingQueue } from '@/types'

const queryClient = useQueryClient()
const { t } = useI18n()
const filter = ref('')
const selectedItem = ref<InvoiceProcessingQueue | null>(null)
const editMode = ref(false)
const fileUrl = ref('')
const zoom = ref(1)
const isPdf = computed(() => !!selectedItem.value?.filename?.toLowerCase().endsWith('.pdf'))

// Bulk upload state
const bulkDragOver = ref(false)
const bulkUploadResult = ref<any>(null)

const bulkUploadMutation = useMutation({
  mutationFn: (files: File[]) => invoiceQueueApi.uploadBulk(files),
  onSuccess: (response) => {
    bulkUploadResult.value = response.data
    queryClient.invalidateQueries({ queryKey: ['invoice-queue'] })
  },
})

function onBulkDrop(e: DragEvent) {
  bulkDragOver.value = false
  const files = Array.from(e.dataTransfer?.files ?? []).filter(f =>
    /\.(pdf|png|jpg|jpeg)$/i.test(f.name)
  )
  if (files.length) bulkUploadMutation.mutate(files)
}

function onBulkFileInput(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files ?? [])
  if (files.length) bulkUploadMutation.mutate(files)
  ;(e.target as HTMLInputElement).value = ''
}

const formData = ref({
  nif_emitente: '',
  nif_adquirente: '',
  identificacao_documento: '',
  data_documento: '',
  total_documento: '',
  total_impostos: '',
  atcud: '',
  // Foreign currency
  is_foreign_currency: false,
  foreign_currency_code: '',
  original_total_amount: '' as number | '',
  exchange_rate: '' as number | '',
})

// Bidirectional: fill EUR total → compute rate; fill rate → compute EUR total
function onEurTotalInput() {
  const orig = parseFloat(String(formData.value.original_total_amount))
  const eur = parsePortugueseNumber(formData.value.total_documento)
  if (orig > 0 && eur > 0) {
    formData.value.exchange_rate = parseFloat((orig / eur).toFixed(6))
  }
}
function onExchangeRateInput() {
  const orig = parseFloat(String(formData.value.original_total_amount))
  const rate = parseFloat(String(formData.value.exchange_rate))
  if (orig > 0 && rate > 0) {
    formData.value.total_documento = formatPortugueseNumber(parseFloat((orig / rate).toFixed(2)))
  }
}
function onOriginalTotalInput() {
  // If rate already set, recalculate EUR; if EUR already set, recalculate rate
  const orig = parseFloat(String(formData.value.original_total_amount))
  const rate = parseFloat(String(formData.value.exchange_rate))
  const eur = parsePortugueseNumber(formData.value.total_documento)
  if (orig > 0 && rate > 0) {
    formData.value.total_documento = formatPortugueseNumber(parseFloat((orig / rate).toFixed(2)))
  } else if (orig > 0 && eur > 0) {
    formData.value.exchange_rate = parseFloat((orig / eur).toFixed(6))
  }
}

const { data: queueData, isLoading } = useQuery({
  queryKey: ['invoice-queue', filter],
  queryFn: async () => {
    const params = filter.value ? { status: filter.value } : undefined
    const response = await invoiceQueueApi.getAll(params)
    return response.data
  },
})

const queueItems = computed(() => queueData.value ?? [])

watch(() => selectedItem.value?.id, async (id) => {
  zoom.value = 1
  if (id) {
    try {
      const response = await invoiceQueueApi.getFileUrl(id)
      fileUrl.value = response.data.url
    } catch {
      fileUrl.value = ''
    }
  } else {
    fileUrl.value = ''
  }
})

const processMutation = useMutation({
  mutationFn: (id: number) => invoiceQueueApi.processItem(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-queue'] })
    selectedItem.value = null
    alert(t('review.processSuccess'))
  },
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { detail?: string } } }
    alert(e.response?.data?.detail || t('review.processError'))
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => invoiceQueueApi.deleteItem(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoice-queue'] })
    selectedItem.value = null
  },
})

function getStatusClass(status: string) {
  const map: Record<string, string> = {
    pending: 'bg-blue-100 text-blue-800',
    processing: 'bg-yellow-100 text-yellow-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    needs_review: 'bg-orange-100 text-orange-800',
  }
  return map[status] ?? map.pending
}

function getStatusIcon(status: string) {
  if (status === 'completed') return CheckCircle
  if (status === 'failed' || status === 'needs_review') return AlertCircle
  return Clock
}

function parseQRData(raw?: string) {
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

function startEdit() {
  const qr = parseQRData(selectedItem.value?.qr_data)
  formData.value = {
    nif_emitente: qr?.nif_emitente || '',
    nif_adquirente: qr?.nif_adquirente || '',
    identificacao_documento: qr?.identificacao_documento || '',
    data_documento: qr?.data_documento || '',
    total_documento: qr?.total_documento ? formatPortugueseNumber(qr.total_documento) : '',
    total_impostos: qr?.total_impostos ? formatPortugueseNumber(qr.total_impostos) : '',
    atcud: qr?.atcud || '',
    is_foreign_currency: Boolean(qr?.is_foreign_currency),
    foreign_currency_code: qr?.foreign_currency_code || '',
    original_total_amount: qr?.original_total_amount ?? '',
    exchange_rate: qr?.exchange_rate ?? '',
  }
  editMode.value = true
}

function startManualEntry() {
  formData.value = {
    nif_emitente: '',
    nif_adquirente: '',
    identificacao_documento: '',
    data_documento: new Date().toISOString().split('T')[0],
    total_documento: '0,00',
    total_impostos: '0,00',
    atcud: '',
    is_foreign_currency: false,
    foreign_currency_code: '',
    original_total_amount: '',
    exchange_rate: '',
  }
  editMode.value = true
}

async function saveEdit() {
  if (!formData.value.nif_emitente || !formData.value.identificacao_documento ||
      !formData.value.data_documento || !formData.value.total_documento) {
    alert(t('review.errorRequired'))
    return
  }
  const updated: Record<string, unknown> = {
    nif_emitente: formData.value.nif_emitente,
    nif_adquirente: formData.value.nif_adquirente,
    identificacao_documento: formData.value.identificacao_documento,
    data_documento: formData.value.data_documento,
    total_documento: parsePortugueseNumber(formData.value.total_documento),
    total_impostos: parsePortugueseNumber(formData.value.total_impostos),
    atcud: formData.value.atcud,
    is_foreign_currency: formData.value.is_foreign_currency,
    foreign_currency_code: formData.value.is_foreign_currency ? formData.value.foreign_currency_code || null : null,
    original_total_amount: formData.value.is_foreign_currency && formData.value.original_total_amount !== '' ? Number(formData.value.original_total_amount) : null,
    exchange_rate: formData.value.is_foreign_currency && formData.value.exchange_rate !== '' ? Number(formData.value.exchange_rate) : null,
  }
  try {
    await invoiceQueueApi.updateItem(selectedItem.value!.id, updated)
    if (selectedItem.value) {
      selectedItem.value = {
        ...selectedItem.value,
        qr_data: JSON.stringify(updated),
        has_qr_data: true,
      }
    }
    editMode.value = false
    queryClient.invalidateQueries({ queryKey: ['invoice-queue'] })
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    alert(e.response?.data?.detail || t('review.errorSave'))
  }
}

function confirmDelete() {
  if (confirm(t('review.deleteConfirm'))) {
    deleteMutation.mutate(selectedItem.value!.id)
  }
}

function confirmDeleteCard(e: MouseEvent, id: number) {
  e.stopPropagation()
  if (confirm(t('review.deleteQueueConfirm'))) {
    deleteMutation.mutate(id)
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('review.title') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('review.subtitle') }}</p>
    </div>

    <!-- Bulk Upload -->
    <Card>
      <CardHeader><CardTitle>{{ t('review.bulkUpload') }}</CardTitle></CardHeader>
      <CardContent>
        <div
          class="border-2 border-dashed rounded-xl p-8 text-center transition-colors"
          :class="bulkDragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'"
          @dragover.prevent="bulkDragOver = true"
          @dragleave="bulkDragOver = false"
          @drop.prevent="onBulkDrop"
        >
          <Upload class="h-10 w-10 mx-auto text-gray-400 mb-2" />
          <p class="text-gray-600 mb-1">{{ t('review.dragDrop') }}</p>
          <label class="cursor-pointer text-blue-600 hover:underline font-medium">
            {{ t('review.browseFiles') }}
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" multiple class="hidden" @change="onBulkFileInput" />
          </label>
          <p class="text-xs text-gray-400 mt-1">{{ t('review.fileTypes') }}</p>
        </div>

        <!-- Upload in progress -->
        <div v-if="bulkUploadMutation.isPending.value" class="mt-4 flex items-center gap-2 text-blue-600">
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          {{ t('review.uploadingProcessing') }}
        </div>

        <!-- Upload result summary -->
        <div v-if="bulkUploadResult && !bulkUploadMutation.isPending.value" class="mt-4 space-y-3">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="p-3 bg-gray-50 rounded-lg text-center">
              <p class="text-xl font-bold text-gray-900">{{ bulkUploadResult.total_files }}</p>
              <p class="text-xs text-gray-500">{{ t('review.uploaded') }}</p>
            </div>
            <div class="p-3 bg-green-50 rounded-lg text-center">
              <p class="text-xl font-bold text-green-700">{{ bulkUploadResult.auto_processed ?? 0 }}</p>
              <p class="text-xs text-green-600">{{ t('review.autoProcessed') }}</p>
            </div>
            <div class="p-3 bg-orange-50 rounded-lg text-center">
              <p class="text-xl font-bold text-orange-700">{{ bulkUploadResult.needs_review ?? 0 }}</p>
              <p class="text-xs text-orange-600">{{ t('review.needsReview') }}</p>
            </div>
            <div class="p-3 bg-red-50 rounded-lg text-center">
              <p class="text-xl font-bold text-red-700">{{ bulkUploadResult.failed ?? 0 }}</p>
              <p class="text-xs text-red-600">{{ t('review.failed') }}</p>
            </div>
          </div>

          <!-- Per-file results -->
          <div class="space-y-1 max-h-48 overflow-y-auto">
            <div
              v-for="r in bulkUploadResult.results"
              :key="r.filename"
              class="flex items-center gap-2 text-sm p-2 rounded"
              :class="r.auto_processed ? 'bg-green-50' : r.status === 'error' ? 'bg-red-50' : 'bg-orange-50'"
            >
              <CheckCircle v-if="r.auto_processed" class="h-4 w-4 text-green-500 shrink-0" />
              <AlertCircle v-else-if="r.status === 'error'" class="h-4 w-4 text-red-500 shrink-0" />
              <Clock v-else class="h-4 w-4 text-orange-500 shrink-0" />
              <span class="truncate flex-1 font-medium">{{ r.filename }}</span>
              <span class="shrink-0 text-xs text-gray-500">{{ r.message }}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <div class="flex items-center justify-between flex-wrap gap-2">
          <CardTitle>{{ t('review.processingQueue') }}</CardTitle>
          <div class="flex gap-2 flex-wrap">
            <Button
              v-for="opt in [
                { label: t('review.filterAll'), value: '' },
                { label: t('review.filterNeedsReview'), value: 'needs_review' },
                { label: t('review.filterPending'), value: 'pending' },
                { label: t('review.filterFailed'), value: 'failed' },
                { label: t('review.filterCompleted'), value: 'completed' },
              ]"
              :key="opt.value"
              :variant="filter === opt.value ? 'primary' : 'secondary'"
              size="sm"
              @click="filter = opt.value"
            >
              {{ opt.label }}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <!-- Loading -->
        <div v-if="isLoading" class="text-center py-8 text-gray-500">{{ t('common.loading') }}</div>

        <!-- Empty -->
        <div v-else-if="queueItems.length === 0 && !selectedItem" class="text-center py-12">
          <FileText class="mx-auto h-12 w-12 text-gray-400" />
          <h3 class="mt-2 text-sm font-medium text-gray-900">{{ t('review.noItems') }}</h3>
          <p class="mt-1 text-sm text-gray-500">{{ t('review.noItemsDesc') }}</p>
        </div>

        <!-- Detail view -->
        <div v-else-if="selectedItem" class="space-y-4">
          <Button variant="secondary" size="sm" @click="selectedItem = null; editMode = false">
            {{ t('review.backToList') }}
          </Button>

          <div class="flex items-start justify-between">
            <div>
              <h3 class="text-lg font-semibold text-gray-900">{{ selectedItem.filename }}</h3>
              <p class="text-sm text-gray-500 mt-1">
                {{ t('review.uploaded2') }} {{ formatDateTime(selectedItem.uploaded_at) }}
                <span :class="['ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', getStatusClass(selectedItem.status)]">
                  {{ selectedItem.status.replace('_', ' ') }}
                </span>
              </p>
            </div>
            <button class="text-gray-400 hover:text-gray-600" @click="selectedItem = null; editMode = false">
              <X class="h-5 w-5" />
            </button>
          </div>

          <div v-if="selectedItem.error_message" class="bg-red-50 border border-red-200 rounded-lg p-3">
            <p class="text-sm text-red-800">{{ selectedItem.error_message }}</p>
          </div>

          <div v-if="selectedItem.invoice_id" class="bg-green-50 border border-green-200 rounded-lg p-3">
            <p class="text-sm text-green-800">{{ t('review.invoiceCreated', { n: selectedItem.invoice_id }) }}</p>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Preview -->
            <div class="border rounded-lg overflow-hidden bg-white">
              <div class="bg-gray-100 px-4 py-2 border-b flex items-center justify-between">
                <h4 class="font-medium text-gray-900 text-sm">{{ t('review.invoicePreview') }}</h4>
              </div>
              <!-- PDF: native browser viewer (zoom + text copy built-in) -->
              <iframe
                v-if="fileUrl && isPdf"
                :src="fileUrl"
                class="w-full border-0"
                style="height: 600px;"
                title="Invoice PDF"
              />
              <!-- Image: zoom controls overlay + width-based scaling for proper scroll -->
              <div v-else-if="fileUrl" class="relative bg-gray-50 overflow-auto" style="height: 600px;">
                <!-- Floating zoom toolbar -->
                <div class="sticky top-2 left-0 right-0 flex justify-center z-10 pointer-events-none">
                  <div class="flex items-center gap-1 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg shadow px-2 py-1 pointer-events-auto">
                    <button
                      @click="zoom = Math.max(0.25, +(zoom - 0.25).toFixed(2))"
                      class="p-1 rounded hover:bg-gray-100 text-gray-600 disabled:opacity-40"
                      :disabled="zoom <= 0.25"
                      title="Zoom out"
                    ><ZoomOut class="h-4 w-4" /></button>
                    <span class="text-xs text-gray-600 w-12 text-center">{{ Math.round(zoom * 100) }}%</span>
                    <button
                      @click="zoom = Math.min(4, +(zoom + 0.25).toFixed(2))"
                      class="p-1 rounded hover:bg-gray-100 text-gray-600 disabled:opacity-40"
                      :disabled="zoom >= 4"
                      title="Zoom in"
                    ><ZoomIn class="h-4 w-4" /></button>
                    <button
                      @click="zoom = 1"
                      class="p-1 rounded hover:bg-gray-100 text-gray-600 ml-1"
                      title="Reset zoom"
                    ><RotateCcw class="h-4 w-4" /></button>
                  </div>
                </div>
                <!-- Image sized by zoom so scroll area expands properly -->
                <div class="flex justify-center p-4">
                  <img
                    :src="fileUrl"
                    alt="Invoice"
                    :style="{
                      width: zoom <= 1 ? 'auto' : `${zoom * 100}%`,
                      maxWidth: zoom <= 1 ? '100%' : 'none',
                      height: 'auto',
                      transition: 'width 0.15s ease',
                    }"
                  />
                </div>
              </div>
              <!-- Empty state -->
              <div v-else class="flex items-center justify-center bg-gray-50" style="height: 600px;">
                <div class="text-center text-gray-500">
                  <FileText class="mx-auto h-12 w-12 text-gray-400 mb-2" />
                  <p>{{ t('review.loadingPreview') }}</p>
                </div>
              </div>
            </div>

            <!-- Invoice data -->
            <div class="border rounded-lg bg-white">
              <div class="bg-gray-100 px-4 py-2 border-b flex items-center justify-between">
                <h4 class="font-medium text-gray-900 text-sm">{{ t('review.invoiceData') }}</h4>
                <Button
                  v-if="!editMode && selectedItem.has_qr_data"
                  variant="secondary"
                  size="sm"
                  @click="startEdit"
                >
                  {{ t('review.editBtn') }}
                </Button>
              </div>

              <div class="p-4 max-h-[600px] overflow-y-auto">
                <!-- Read-only QR data view -->
                <template v-if="!editMode && selectedItem.has_qr_data">
                  <template v-if="parseQRData(selectedItem.qr_data)">
                    <div class="space-y-3 text-sm">
                      <template v-for="(val, key) in parseQRData(selectedItem.qr_data)" :key="key">
                        <div v-if="val !== null && val !== undefined && val !== ''">
                          <p class="text-xs text-gray-500">{{ String(key).replace(/_/g, ' ') }}</p>
                          <p class="font-medium">{{ val }}</p>
                        </div>
                      </template>
                    </div>
                  </template>
                  <p v-else class="text-sm text-gray-500">{{ t('review.cantParseQr') }}</p>
                </template>

                <!-- No data placeholder -->
                <template v-else-if="!editMode && !selectedItem.has_qr_data">
                  <div class="text-center py-8">
                    <p class="text-gray-500 mb-4">{{ t('review.noData') }}</p>
                    <Button variant="secondary" @click="startManualEntry">{{ t('review.enterManually') }}</Button>
                  </div>
                </template>

                <!-- Edit form -->
                <div v-if="editMode" class="space-y-3">
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.supplierNif') }}</label>
                    <input v-model="formData.nif_emitente" type="text" placeholder="123456789"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.customerNif') }}</label>
                    <input v-model="formData.nif_adquirente" type="text" placeholder="123456789"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.invoiceNumber') }}</label>
                    <input v-model="formData.identificacao_documento" type="text" placeholder="FT 2024/001"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.dateLabel') }}</label>
                    <input v-model="formData.data_documento" type="date"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>
                  <div v-if="!formData.is_foreign_currency">
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.totalAmount') }}</label>
                    <input v-model="formData.total_documento" type="text" placeholder="100,00"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                    <p class="text-xs text-gray-400 mt-0.5">{{ t('review.commaHint') }}</p>
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.taxAmount') }}</label>
                    <input v-model="formData.total_impostos" type="text" placeholder="23,00"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.atcud') }}</label>
                    <input v-model="formData.atcud" type="text" placeholder="ATCUD-1234"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                  </div>

                  <!-- Foreign Currency Section -->
                  <div class="pt-2 border-t border-gray-100">
                    <div class="flex items-center gap-2 mb-2">
                      <input id="fc-toggle-rv" v-model="formData.is_foreign_currency" type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                      <label for="fc-toggle-rv" class="text-xs font-medium text-gray-700">{{ t('review.foreignCurrencyCheck') }}</label>
                    </div>
                    <div v-if="formData.is_foreign_currency" class="space-y-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
                      <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('review.currencyCode') }}</label>
                        <select v-model="formData.foreign_currency_code"
                          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm">
                          <option value="">{{ t('review.selectCurrency') }}</option>
                          <option>USD</option>
                          <option>GBP</option>
                          <option>SGD</option>
                          <option>CHF</option>
                          <option>JPY</option>
                          <option>CAD</option>
                          <option>AUD</option>
                          <option>SEK</option>
                          <option>DKK</option>
                          <option>NOK</option>
                          <option>PLN</option>
                          <option>CZK</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">
                          {{ t('review.originalTotal', { code: formData.foreign_currency_code || 'FC' }) }} <span class="text-red-500">*</span>
                        </label>
                        <input v-model="formData.original_total_amount" type="number" step="0.01" min="0" placeholder="0.00"
                          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
                          @input="onOriginalTotalInput" />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">
                          {{ t('review.eurTotal') }} <span class="text-xs text-gray-400">(fills exchange rate automatically)</span>
                        </label>
                        <input v-model="formData.total_documento" type="text" placeholder="0,00"
                          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
                          @input="onEurTotalInput" />
                        <p class="text-xs text-gray-400 mt-0.5">{{ t('review.commaHint') }}</p>
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">
                          {{ t('review.exchangeRate') }} <span class="text-xs text-gray-400">(1 EUR = X {{ formData.foreign_currency_code || 'FC' }}) — fills EUR total automatically</span>
                        </label>
                        <input v-model="formData.exchange_rate" type="number" step="0.000001" min="0" placeholder="1.000000"
                          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
                          @input="onExchangeRateInput" />
                      </div>
                      <div v-if="formData.exchange_rate && formData.foreign_currency_code" class="text-xs text-amber-800 bg-amber-100 rounded px-2 py-1.5">
                        1 EUR = {{ Number(formData.exchange_rate).toFixed(4) }} {{ formData.foreign_currency_code }}
                      </div>
                    </div>
                  </div>
                  <div class="flex gap-2 pt-2">
                    <Button class="flex-1" @click="saveEdit">{{ t('review.saveChanges') }}</Button>
                    <Button variant="secondary" class="flex-1" @click="editMode = false">{{ t('common.cancel') }}</Button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Action buttons -->
          <div class="flex gap-3">
            <Button
              v-if="(selectedItem.status === 'pending' || selectedItem.status === 'needs_review') && !editMode"
              class="flex-1"
              :disabled="processMutation.isPending.value || !selectedItem.has_qr_data"
              @click="processMutation.mutate(selectedItem.id)"
            >
              <Play class="h-4 w-4 mr-2" />
              {{ processMutation.isPending.value ? t('review.processing') : t('review.process') }}
            </Button>
            <Button
              v-if="selectedItem.status === 'failed' && !editMode"
              class="flex-1"
              :disabled="processMutation.isPending.value"
              @click="processMutation.mutate(selectedItem.id)"
            >
              <Play class="h-4 w-4 mr-2" />
              {{ processMutation.isPending.value ? t('review.retrying') : t('review.retry') }}
            </Button>
            <Button
              v-if="!editMode"
              variant="secondary"
              :disabled="deleteMutation.isPending.value"
              @click="confirmDelete"
            >
              <X class="h-4 w-4 mr-2" />
              {{ t('common.delete') }}
            </Button>
          </div>
        </div>

        <!-- Grid list -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <div
            v-for="item in queueItems"
            :key="item.id"
            class="relative p-4 border rounded-lg cursor-pointer transition-colors hover:border-primary-300 hover:shadow-md group"
            @click="selectedItem = item"
          >
            <!-- Delete button (top-right, visible on hover) -->
            <button
              class="absolute top-2 right-2 p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Delete"
              @click="confirmDeleteCard($event, item.id)"
            >
              <Trash2 class="h-4 w-4" />
            </button>

            <!-- Icon + filename -->
            <div class="flex items-start gap-3 mb-3 pr-6">
              <component
                :is="item.has_qr_data ? FileScan : FileWarning"
                :class="item.has_qr_data ? 'text-blue-500' : 'text-orange-400'"
                class="h-8 w-8 shrink-0 mt-0.5"
              />
              <span class="text-sm font-medium text-gray-900 truncate leading-tight">{{ item.filename }}</span>
            </div>

            <!-- Status badge -->
            <div class="mb-2">
              <span :class="['inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', getStatusClass(item.status)]">
                <component :is="getStatusIcon(item.status)" class="w-3 h-3 mr-1" />
                {{ item.status.replace('_', ' ') }}
              </span>
            </div>

            <p class="text-xs text-gray-400">{{ formatDateTime(item.uploaded_at) }}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
