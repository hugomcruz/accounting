<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMutation, useQuery } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Upload, CheckCircle, AlertCircle, QrCode, FileText, Plus } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import Button from '@/components/ui/Button.vue'
import { uploadApi, invoicePaymentsApi, hrApi } from '@/services/queries'

interface QRData {
  nif_emitente?: string
  nif_adquirente?: string | null
  identificacao_documento?: string
  data_documento?: string
  total_documento?: number
  total_impostos?: number | null
  atcud?: string | null
  is_foreign_currency?: boolean
  foreign_currency_code?: string | null
  original_total_amount?: number | null
  exchange_rate?: number | null
}

interface UploadResult {
  filename: string
  file_path: string
  file_url?: string | null
  qr_data?: QRData | null
  extraction_method?: string | null
  message: string
}

const isDragging = ref(false)
const { t } = useI18n()
const uploadResult = ref<UploadResult | null>(null)
const showManualEntry = ref(false)
const isCreatingInvoice = ref(false)
const invoiceCreated = ref<{ id?: number; invoice_id?: number; invoice_number?: string; invoice_updated?: boolean; supplier_name?: string } | null>(null)
const invoiceNotes = ref('')

// Payment on creation
const addPaymentOnCreate = ref(false)
const paymentForm = ref({
  payment_date: new Date().toISOString().slice(0, 10),
  amount: '' as number | '',
  payment_type: 'cash' as 'cash' | 'employee' | 'other',
  reference: '',
  employee_id: '' as number | '',
  notes: '',
})

const { data: employees } = useQuery({
  queryKey: ['employees'],
  queryFn: async () => {
    const res = await hrApi.getEmployees()
    return (res.data as { id: number; first_name: string; last_name: string }[])
  },
})
const manualData = ref<QRData>({
  nif_emitente: '',
  nif_adquirente: '',
  identificacao_documento: '',
  data_documento: '',
  total_documento: undefined,
  total_impostos: undefined,
  atcud: '',
  is_foreign_currency: false,
  foreign_currency_code: '',
  original_total_amount: undefined,
  exchange_rate: undefined,
})

function onEurTotalInput() {
  const orig = manualData.value.original_total_amount
  const eur = manualData.value.total_documento
  if (orig && eur && eur > 0) {
    manualData.value.exchange_rate = parseFloat((orig / eur).toFixed(6))
  }
}
function onExchangeRateInput() {
  const orig = manualData.value.original_total_amount
  const rate = manualData.value.exchange_rate
  if (orig && rate && rate > 0) {
    manualData.value.total_documento = parseFloat((orig / rate).toFixed(2))
  }
}
function onOriginalTotalInput() {
  const orig = manualData.value.original_total_amount
  const rate = manualData.value.exchange_rate
  const eur = manualData.value.total_documento
  if (orig && rate && rate > 0) {
    manualData.value.total_documento = parseFloat((orig / rate).toFixed(2))
  } else if (orig && eur && eur > 0) {
    manualData.value.exchange_rate = parseFloat((orig / eur).toFixed(6))
  }
}

const uploadMutation = useMutation({
  mutationFn: (file: File) => uploadApi.uploadInvoice(file),
  onSuccess: (response) => {
    uploadResult.value = response.data
    if (!response.data.qr_data) {
      showManualEntry.value = false
    }
  },
})

const hasQRData = computed(() => !!uploadResult.value?.qr_data)
const activeQRData = computed<QRData | null>(() => uploadResult.value?.qr_data ?? null)
const filePreviewUrl = computed(() => uploadResult.value?.file_url ?? '')
const isPdf = computed(() => uploadResult.value?.filename?.toLowerCase().endsWith('.pdf'))

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) processFile(file)
}

function onFileInput(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) processFile(file)
}

function processFile(file: File) {
  uploadResult.value = null
  invoiceCreated.value = null
  showManualEntry.value = false
  uploadMutation.mutate(file)
}

function applyManualData() {
  if (!manualData.value.nif_emitente || !manualData.value.identificacao_documento ||
      !manualData.value.data_documento || !manualData.value.total_documento) {
    alert(t('upload.errorRequired'))
    return
  }
  if (manualData.value.is_foreign_currency && !manualData.value.original_total_amount) {
    alert(t('upload.errorFcAmount'))
    return
  }
  if (uploadResult.value) {
    uploadResult.value = { ...uploadResult.value, qr_data: { ...manualData.value } }
  }
  showManualEntry.value = false
}

async function createInvoice() {
  if (!uploadResult.value) return
  isCreatingInvoice.value = true
  try {
    const response = await uploadApi.processInvoice(
      uploadResult.value.file_path,
      true,
      invoiceNotes.value || undefined,
      activeQRData.value ?? undefined,
    )
    invoiceCreated.value = response.data
    // Add payment if requested
    if (addPaymentOnCreate.value && paymentForm.value.amount) {
      const invoiceId = response.data?.id ?? response.data?.invoice_id
      if (invoiceId) {
        const payData: Record<string, unknown> = {
          payment_date: new Date(paymentForm.value.payment_date).toISOString(),
          amount: Number(paymentForm.value.amount),
          payment_type: paymentForm.value.payment_type,
          reference: paymentForm.value.reference || null,
          notes: paymentForm.value.notes || null,
          employee_id: paymentForm.value.payment_type === 'employee' && paymentForm.value.employee_id
            ? paymentForm.value.employee_id : null,
        }
        await invoicePaymentsApi.add(invoiceId, payData)
      }
    }
  } catch (err: unknown) {
    const axiosError = err as { response?: { data?: { detail?: string } } }
    alert(axiosError.response?.data?.detail || t('upload.errorCreate'))
  } finally {
    isCreatingInvoice.value = false
  }
}

function resetUpload() {
  uploadResult.value = null
  invoiceCreated.value = null
  showManualEntry.value = false
  invoiceNotes.value = ''
  addPaymentOnCreate.value = false
  paymentForm.value = {
    payment_date: new Date().toISOString().slice(0, 10),
    amount: '',
    payment_type: 'cash',
    reference: '',
    employee_id: '',
    notes: '',
  }
  manualData.value = {
    nif_emitente: '',
    nif_adquirente: '',
    identificacao_documento: '',
    data_documento: '',
    total_documento: undefined,
    total_impostos: undefined,
    atcud: '',
    is_foreign_currency: false,
    foreign_currency_code: '',
    original_total_amount: undefined,
    exchange_rate: undefined,
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('upload.title') }}</h1>
      <p class="mt-2 text-gray-600">{{ t('upload.subtitle') }}</p>
    </div>

    <!-- Upload area (shown before result) -->
    <Card v-if="!uploadResult">
      <CardHeader><CardTitle>{{ t('upload.selectFile') }}</CardTitle></CardHeader>
      <CardContent>
        <div
          :class="[
            'border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors',
            isDragging ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
          ]"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="onDrop"
          @click="($refs.fileInput as HTMLInputElement).click()"
        >
          <input ref="fileInput" type="file" accept=".pdf,.png,.jpg,.jpeg" class="hidden" @change="onFileInput" />
          <Upload class="mx-auto h-12 w-12 text-gray-400" />
          <p class="mt-4 text-lg font-medium text-gray-900">
            {{ isDragging ? t('upload.dropHere') : t('upload.dragOrClick') }}
          </p>
          <p class="mt-2 text-sm text-gray-500">{{ t('upload.fileTypes') }}</p>
        </div>

        <div v-if="uploadMutation.isPending.value" class="mt-4 flex items-center justify-center gap-2 text-primary-600">
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ t('upload.uploadingScanning') }}
        </div>

        <div v-if="uploadMutation.isError.value" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-800">
          <AlertCircle class="h-5 w-5 flex-shrink-0" />
          {{ t('upload.uploadFailed') }}
        </div>
      </CardContent>
    </Card>

    <!-- Result section -->
    <template v-if="uploadResult && !invoiceCreated">
      <!-- Invoice created success -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Preview -->
        <Card>
          <CardHeader><CardTitle>{{ t('invoiceDetail.invoicePreview') }}</CardTitle></CardHeader>
          <CardContent>
            <div class="border rounded-lg overflow-hidden bg-gray-50 h-[600px]">
              <iframe
                v-if="isPdf"
                :src="filePreviewUrl"
                class="w-full h-full border-0"
                title="Invoice Preview"
              />
              <img
                v-else
                :src="filePreviewUrl"
                class="w-full h-full object-contain"
                alt="Invoice Preview"
              />
            </div>
          </CardContent>
        </Card>

        <!-- QR Data + Actions -->
        <div class="space-y-4">
          <!-- Extraction badge -->
          <Card>
            <div class="flex items-center gap-3">
              <div v-if="hasQRData" class="flex items-center gap-2 text-green-700 bg-green-50 px-3 py-2 rounded-lg flex-1">
                <QrCode class="h-5 w-5" />
                <span class="text-sm font-medium">
                  {{ t('upload.qrDetected') }}
                  <span v-if="uploadResult?.extraction_method" class="text-xs text-green-600 ml-1">({{ uploadResult.extraction_method }})</span>
                </span>
              </div>
              <div v-else class="flex items-center gap-2 text-amber-700 bg-amber-50 px-3 py-2 rounded-lg flex-1">
                <AlertCircle class="h-5 w-5" />
                <span class="text-sm font-medium">{{ t('upload.noQr') }}</span>
              </div>
              <Button variant="secondary" size="sm" @click="resetUpload">{{ t('upload.uploadAnother') }}</Button>
            </div>
          </Card>

          <!-- Extracted QR data display -->
          <Card v-if="hasQRData && !showManualEntry">
            <CardHeader>
              <div class="flex items-center justify-between">
                <CardTitle>{{ t('upload.extractedData') }}</CardTitle>
                <Button variant="secondary" size="sm" @click="() => { Object.assign(manualData, activeQRData); showManualEntry = true }">{{ t('common.edit') }}</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div class="space-y-3 text-sm">
                <div v-if="activeQRData?.nif_emitente">
                  <p class="text-xs text-gray-500">{{ t('upload.supplierNif') }}</p>
                  <p class="font-medium">{{ activeQRData.nif_emitente }}</p>
                </div>
                <div v-if="activeQRData?.nif_adquirente">
                  <p class="text-xs text-gray-500">{{ t('upload.customerNif') }}</p>
                  <p class="font-medium">{{ activeQRData.nif_adquirente }}</p>
                </div>
                <div v-if="activeQRData?.identificacao_documento">
                  <p class="text-xs text-gray-500">{{ t('upload.invoiceNumber') }}</p>
                  <p class="font-medium">{{ activeQRData.identificacao_documento }}</p>
                </div>
                <div v-if="activeQRData?.data_documento">
                  <p class="text-xs text-gray-500">{{ t('upload.date') }}</p>
                  <p class="font-medium">{{ activeQRData.data_documento }}</p>
                </div>
                <div v-if="activeQRData?.total_documento != null">
                  <p class="text-xs text-gray-500">{{ t('upload.totalAmount') }}</p>
                  <p class="font-medium">€{{ activeQRData.total_documento?.toFixed(2) }}</p>
                </div>
                <div v-if="activeQRData?.total_impostos != null">
                  <p class="text-xs text-gray-500">{{ t('upload.taxAmount') }}</p>
                  <p class="font-medium">€{{ activeQRData.total_impostos?.toFixed(2) }}</p>
                </div>
                <div v-if="activeQRData?.atcud">
                  <p class="text-xs text-gray-500">{{ t('upload.atcud') }}</p>
                  <p class="font-medium font-mono">{{ activeQRData.atcud }}</p>
                </div>
                <div v-if="activeQRData?.is_foreign_currency" class="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                  <p class="text-xs font-semibold text-amber-700">{{ t('upload.foreignCurrencySection') }}</p>
                  <div v-if="activeQRData?.foreign_currency_code">
                    <p class="text-xs text-gray-500">{{ t('upload.currency') }}</p>
                    <p class="font-medium">{{ activeQRData.foreign_currency_code }}</p>
                  </div>
                  <div v-if="activeQRData?.original_total_amount != null">
                    <p class="text-xs text-gray-500">{{ t('upload.originalTotal', { code: activeQRData.foreign_currency_code }) }}</p>
                    <p class="font-medium">{{ activeQRData.original_total_amount?.toFixed(2) }}</p>
                  </div>
                  <div v-if="activeQRData?.exchange_rate != null">
                    <p class="text-xs text-gray-500">{{ t('upload.exchangeRate') }}</p>
                    <p class="font-medium">1 EUR = {{ activeQRData.exchange_rate?.toFixed(4) }} {{ activeQRData.foreign_currency_code }}</p>
                  </div>
                </div>
              </div>
              <div class="mt-4">
                <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.commentsNotes') }}</label>
                <textarea
                  v-model="invoiceNotes"
                  rows="3"
                  :placeholder="t('upload.notesPlaceholder')"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm resize-none"
                />
              </div>

              <!-- Payment section -->
              <div class="mt-4">
                <button
                  type="button"
                  class="flex items-center gap-2 text-sm font-medium text-primary-700 hover:text-primary-900 transition-colors"
                  @click="addPaymentOnCreate = !addPaymentOnCreate"
                >
                  <Plus class="h-4 w-4" />
                  {{ addPaymentOnCreate ? t('upload.removePayment') : t('upload.addPayment') }}
                </button>
                <div v-if="addPaymentOnCreate" class="mt-3 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
                  <div class="grid grid-cols-2 gap-3">
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.paymentDate') }}</label>
                      <input v-model="paymentForm.payment_date" type="date" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.paymentAmount') }}</label>
                      <input v-model="paymentForm.amount" type="number" step="0.01" min="0.01" placeholder="0.00" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.paymentType') }}</label>
                      <select v-model="paymentForm.payment_type" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                        <option value="cash">{{ t('upload.payCash') }}</option>
                        <option value="employee">{{ t('upload.payEmployee') }}</option>
                        <option value="other">{{ t('upload.payOther') }}</option>
                      </select>
                    </div>
                    <div v-if="paymentForm.payment_type === 'employee'">
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.payEmployeeLabel') }}</label>
                      <select v-model="paymentForm.employee_id" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                        <option value="">{{ t('upload.selectEmployee') }}</option>
                        <option v-for="emp in employees" :key="emp.id" :value="emp.id">{{ emp.first_name }} {{ emp.last_name }}</option>
                      </select>
                    </div>
                    <div v-else>
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.payReference') }}</label>
                      <input v-model="paymentForm.reference" type="text" :placeholder="t('common.optional')" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div class="col-span-2">
                      <label class="block text-xs text-gray-500 mb-1">{{ t('upload.payNotes') }}</label>
                      <input v-model="paymentForm.notes" type="text" :placeholder="t('common.optional')" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                  </div>
                </div>
              </div>

              <div class="mt-4">
                <Button class="w-full" :disabled="isCreatingInvoice" @click="createInvoice">
                  {{ isCreatingInvoice ? t('upload.creating') : (addPaymentOnCreate && paymentForm.amount ? t('upload.createWithPayment') : t('upload.createInvoice')) }}
                </Button>
              </div>
            </CardContent>
          </Card>

          <!-- Manual entry form -->
          <Card v-if="showManualEntry || !hasQRData">
            <CardHeader><CardTitle>{{ hasQRData ? t('upload.editData') : t('upload.enterManually') }}</CardTitle></CardHeader>
            <CardContent>
              <div class="space-y-3">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.supplierNifRequired') }}</label>
                  <input v-model="manualData.nif_emitente" type="text" :placeholder="t('upload.supplierNifPlaceholder')"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.customerNif') }}</label>
                  <input v-model="manualData.nif_adquirente" type="text" placeholder="123456789"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.invoiceNumberRequired') }}</label>
                  <input v-model="manualData.identificacao_documento" type="text" :placeholder="t('upload.invoiceNumberPlaceholder')"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.invoiceDateRequired') }}</label>
                  <input v-model="manualData.data_documento" type="date"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div v-if="!manualData.is_foreign_currency">
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.totalAmountRequired') }}</label>
                  <input v-model.number="manualData.total_documento" type="number" step="0.01" :placeholder="t('upload.totalAmountPlaceholder')"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.taxAmountLabel') }}</label>
                  <input v-model.number="manualData.total_impostos" type="number" step="0.01" :placeholder="t('upload.taxAmountPlaceholder')"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.atcud') }}</label>
                  <input v-model="manualData.atcud" type="text" :placeholder="t('upload.atcudPlaceholder')"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm" />
                </div>

                <!-- Foreign Currency Section -->
                <div class="pt-2 border-t border-gray-100">
                  <div class="flex items-center gap-2 mb-2">
                    <input id="fc-toggle-upload" v-model="manualData.is_foreign_currency" type="checkbox"
                      class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label for="fc-toggle-upload" class="text-sm font-medium text-gray-700">{{ t('upload.foreignCurrencyCheck') }}</label>
                  </div>
                  <div v-if="manualData.is_foreign_currency" class="space-y-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
                    <div>
                      <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('upload.currencyCode') }}</label>
                      <select v-model="manualData.foreign_currency_code"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm">
                        <option value="">{{ t('upload.selectCurrency') }}</option>
                        <option>USD</option><option>GBP</option><option>SGD</option><option>CHF</option>
                        <option>JPY</option><option>CAD</option><option>AUD</option><option>SEK</option>
                        <option>DKK</option><option>NOK</option><option>PLN</option><option>CZK</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700 mb-1">
                      {{ t('upload.originalTotal', { code: manualData.foreign_currency_code || 'FC' }) }} <span class="text-red-500">*</span>
                      </label>
                      <input v-model.number="manualData.original_total_amount" type="number" step="0.01" min="0" placeholder="0.00"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
                        @input="onOriginalTotalInput" />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700 mb-1">
                        EUR Total <span class="text-xs text-gray-400">(fills exchange rate automatically)</span>
                      </label>
                      <input v-model.number="manualData.total_documento" type="number" step="0.01" min="0" placeholder="0.00"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
                        @input="onEurTotalInput" />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700 mb-1">
                      {{ t('upload.exchangeRate') }}
                      <span class="text-xs text-gray-400">(1 EUR = X {{ manualData.foreign_currency_code || 'FC' }}) — fills EUR total automatically</span>
                      </label>
                      <input v-model.number="manualData.exchange_rate" type="number" step="0.000001" min="0" placeholder="1.000000"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
                        @input="onExchangeRateInput" />
                    </div>
                    <div v-if="manualData.exchange_rate && manualData.foreign_currency_code" class="text-xs text-amber-800 bg-amber-100 rounded px-2 py-1.5">
                      1 EUR = {{ Number(manualData.exchange_rate).toFixed(4) }} {{ manualData.foreign_currency_code }}
                    </div>
                  </div>
                </div>

                <div class="flex gap-2 pt-2">
                  <Button class="flex-1" @click="applyManualData">{{ t('upload.confirm') }}</Button>
                  <Button variant="secondary" class="flex-1" @click="showManualEntry = false">{{ t('common.cancel') }}</Button>
                </div>
              </div>

              <!-- Create invoice after manual (when no QR + manual confirmed) -->
              <div v-if="!showManualEntry && !hasQRData" class="mt-4">
                <Button class="w-full" :disabled="isCreatingInvoice" @click="createInvoice">
                  {{ isCreatingInvoice ? 'Creating...' : (addPaymentOnCreate && paymentForm.amount ? t('upload.createWithPayment') : t('upload.createInvoice')) }}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </template>

    <!-- Invoice created/updated success -->
    <Card v-if="invoiceCreated">
      <div class="text-center py-8">
        <CheckCircle class="mx-auto h-12 w-12 text-green-500" />
        <h3 class="mt-3 text-lg font-semibold text-gray-900">
          {{ invoiceCreated.invoice_updated ? t('upload.invoiceReplaced') : t('upload.invoiceRecorded') }}
        </h3>
        <p class="mt-1 text-sm text-gray-500">
          <template v-if="invoiceCreated.invoice_updated">
            Invoice <strong>#{{ invoiceCreated.invoice_number }}</strong>
            <template v-if="invoiceCreated.supplier_name"> from <strong>{{ invoiceCreated.supplier_name }}</strong></template>
            was already on record. The file has been replaced with the new upload.
          </template>
          <template v-else>
            Invoice <strong>#{{ invoiceCreated.invoice_number ?? invoiceCreated.invoice_id }}</strong>
            <template v-if="invoiceCreated.supplier_name"> from <strong>{{ invoiceCreated.supplier_name }}</strong></template>
            has been recorded successfully.
          </template>
        </p>
        <div class="mt-4 flex justify-center gap-3">
          <Button @click="resetUpload">{{ t('upload.uploadAnother') }}</Button>
          <Button variant="secondary" @click="$router.push('/invoices')">{{ t('upload.viewInvoices') }}</Button>
        </div>
      </div>
    </Card>
  </div>
</template>
