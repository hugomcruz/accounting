<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Upload, FileText, Trash2, Building2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { bankApi } from '@/services/queries'

const { t } = useI18n()
const router = useRouter()
const queryClient = useQueryClient()

const dragOver = ref(false)
const selectedFile = ref<File | null>(null)

const { data: statements, isLoading } = useQuery({
  queryKey: ['bank-statements'],
  queryFn: async () => {
    const res = await bankApi.getStatements()
    return res.data
  },
})

const importMutation = useMutation({
  mutationFn: async (file: File) => {
    const res = await bankApi.importStatement(file)
    return res.data
  },
  onSuccess: () => {
    selectedFile.value = null
    queryClient.invalidateQueries({ queryKey: ['bank-statements'] })
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => bankApi.deleteStatement(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bank-statements'] }),
})

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    const file = files[0]
    if (file.name.endsWith('.csv') || file.name.endsWith('.xlsx')) selectedFile.value = file
  }
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) selectedFile.value = input.files[0]
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-gray-900">{{ t('bank.statementsTitle') }}</h1>
      <p class="mt-1 text-gray-500">{{ t('bank.statementsSubtitle') }}</p>
    </div>

    <Card>
      <CardHeader><CardTitle>{{ t('bank.importCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div
          class="border-2 border-dashed rounded-xl p-8 text-center transition-colors"
          :class="dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="handleDrop"
        >
          <Building2 class="h-10 w-10 mx-auto text-gray-400 mb-2" />
          <p class="text-gray-600 mb-1">{{ t('bank.dragDrop') }}</p>
          <label class="cursor-pointer text-blue-600 hover:underline font-medium">
            {{ t('bank.browseFile') }}
            <input type="file" accept=".csv,.xlsx" class="hidden" @change="handleFileChange" />
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
            @click="importMutation.mutate(selectedFile!)"
          >
            <Upload class="h-4 w-4" />
            {{ importMutation.isPending.value ? t('common.importing') : t('common.import') }}
          </button>
        </div>

        <div v-if="importMutation.isError.value" class="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-red-700 text-sm">{{ t('bank.importFailed') }}</p>
        </div>
        <div v-if="importMutation.isSuccess.value" class="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
          <p class="text-green-700 text-sm">{{ t('bank.importSuccess') }}</p>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle>{{ t('bank.statementsCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!statements?.length" class="text-center py-6 text-gray-400">{{ t('bank.noStatements') }}</div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="stmt in statements"
            :key="stmt.id"
            class="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
            @click="router.push(`/bank/statements/${stmt.id}`)"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <p class="font-semibold text-gray-900 truncate">{{ stmt.company_name || t('bank.unknownAccount') }}</p>
                <p class="text-sm text-gray-500 mt-0.5">{{ stmt.account_number }} · {{ stmt.account_currency }}</p>
                <p v-if="stmt.company_nif" class="text-xs text-gray-400 mt-0.5">NIF: {{ stmt.company_nif }}</p>
                <div class="flex items-center gap-1 mt-2 text-sm text-gray-600">
                  <span>{{ new Date(stmt.period_start).toLocaleDateString() }}</span>
                  <span>–</span>
                  <span>{{ new Date(stmt.period_end).toLocaleDateString() }}</span>
                </div>
                <div class="flex gap-4 mt-1 text-sm">
                  <span class="text-gray-500">{{ t('bank.opening') }} <span class="font-medium text-gray-900">€{{ Number(stmt.opening_balance || 0).toFixed(2) }}</span></span>
                  <span class="text-gray-500">{{ t('bank.closing') }} <span class="font-medium text-gray-900">€{{ Number(stmt.closing_balance || 0).toFixed(2) }}</span></span>
                </div>
              </div>
              <button
                class="ml-2 p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded"
                @click.stop="deleteMutation.mutate(stmt.id)"
              >
                <Trash2 class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
