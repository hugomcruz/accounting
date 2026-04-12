<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Upload, FileText, CheckCircle, XCircle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { saftApi } from '@/services/queries'

const { t } = useI18n()
const queryClient = useQueryClient()

const dragOver = ref(false)
const selectedFile = ref<File | null>(null)
const importResult = ref<any>(null)

const { data: imports, isLoading } = useQuery({
  queryKey: ['saft-imports'],
  queryFn: async () => {
    const res = await saftApi.getImports()
    return res.data
  },
})

const importMutation = useMutation({
  mutationFn: async (file: File) => {
    const res = await saftApi.import(file)
    return res.data
  },
  onSuccess: (data) => {
    importResult.value = data
    selectedFile.value = null
    queryClient.invalidateQueries({ queryKey: ['saft-imports'] })
  },
})

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    const file = files[0]
    if (file.name.endsWith('.xml')) {
      selectedFile.value = file
    }
  }
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    selectedFile.value = input.files[0]
  }
}

function handleImport() {
  if (selectedFile.value) {
    importMutation.mutate(selectedFile.value)
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('saft.title') }}</h1>
      <p class="mt-1 text-gray-500">{{ t('saft.subtitle') }}</p>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('saft.uploadCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div
          class="border-2 border-dashed rounded-xl p-10 text-center transition-colors"
          :class="dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="handleDrop"
        >
          <FileText class="h-12 w-12 mx-auto text-gray-400 mb-3" />
          <p class="text-gray-600 mb-1">{{ t('saft.dragDrop') }}</p>
          <label class="cursor-pointer text-blue-600 hover:underline font-medium">
            {{ t('saft.browseFile') }}
            <input type="file" accept=".xml" class="hidden" @change="handleFileChange" />
          </label>
        </div>

        <div v-if="selectedFile" class="mt-4 flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
          <FileText class="h-5 w-5 text-blue-600 shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="font-medium text-gray-900 truncate">{{ selectedFile.name }}</p>
            <p class="text-sm text-gray-500">{{ (selectedFile.size / 1024).toFixed(1) }} KB</p>
          </div>
          <button
            :disabled="importMutation.isPending.value"
            class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="handleImport"
          >
            <Upload class="h-4 w-4" />
            {{ importMutation.isPending.value ? t('common.importing') : t('common.import') }}
          </button>
        </div>

        <div v-if="importMutation.isError.value" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-red-700">{{ t('saft.importFailed') }}</p>
        </div>

        <div v-if="importResult" class="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div class="flex items-center gap-2 mb-3">
            <CheckCircle class="h-5 w-5 text-green-600" />
            <h3 class="font-semibold text-green-800">{{ t('saft.importSuccess') }}</h3>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p class="text-gray-500">{{ t('saft.company') }}</p>
              <p class="font-medium">{{ importResult.company_name || '-' }}</p>
            </div>
            <div>
              <p class="text-gray-500">{{ t('saft.nif') }}</p>
              <p class="font-medium">{{ importResult.nif || '-' }}</p>
            </div>
            <div>
              <p class="text-gray-500">{{ t('saft.fiscalYear') }}</p>
              <p class="font-medium">{{ importResult.fiscal_year || '-' }}</p>
            </div>
            <div>
              <p class="text-gray-500">{{ t('saft.invoicesImported') }}</p>
              <p class="font-medium text-green-700">{{ importResult.invoices_imported ?? importResult.imported ?? 0 }}</p>
            </div>
          </div>
          <div v-if="importResult.errors?.length" class="mt-3">
            <div class="flex items-center gap-1 text-red-600 mb-1">
              <XCircle class="h-4 w-4" />
              <span class="text-sm font-medium">{{ t('saft.errors', { n: importResult.errors.length }) }}</span>
            </div>
            <ul class="text-sm text-red-600 list-disc list-inside">
              <li v-for="(err, i) in importResult.errors.slice(0, 5)" :key="i">{{ err }}</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle>{{ t('saft.historyCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!imports?.length" class="text-center py-6 text-gray-400">{{ t('saft.noImports') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('saft.tableFile') }}</th>
                <th class="pb-2 font-medium">{{ t('saft.tableCompany') }}</th>
                <th class="pb-2 font-medium">{{ t('saft.tablePeriod') }}</th>
                <th class="pb-2 font-medium">{{ t('saft.tableInvoices') }}</th>
                <th class="pb-2 font-medium">{{ t('saft.tableStatus') }}</th>
                <th class="pb-2 font-medium">{{ t('saft.tableDate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="imp in imports" :key="imp.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-3 font-mono text-xs">{{ imp.filename }}</td>
                <td class="py-3">{{ imp.company_name || imp.nif || '-' }}</td>
                <td class="py-3">{{ imp.fiscal_year || '-' }}</td>
                <td class="py-3">{{ imp.invoices_imported ?? '-' }}</td>
                <td class="py-3">
                  <span :class="imp.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                    class="px-2 py-0.5 rounded-full text-xs font-medium">
                    {{ imp.status }}
                  </span>
                </td>
                <td class="py-3 text-gray-500">{{ new Date(imp.created_at).toLocaleDateString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
