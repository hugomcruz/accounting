<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Pencil, Landmark, X, Plus, Trash2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { bankApi, bankLogosApi } from '@/services/queries'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const queryClient = useQueryClient()
const auth = useAuthStore()

// ─── Data ──────────────────────────────────────────────────────────────────

const { data: accounts, isLoading } = useQuery({
  queryKey: ['bank-accounts'],
  queryFn: async () => (await bankApi.getAccounts()).data,
})

const { data: logos } = useQuery({
  queryKey: ['bank-logos'],
  queryFn: async () => (await bankLogosApi.getAll()).data,
})

// ─── Edit modal ─────────────────────────────────────────────────────────────

const editingAccount = ref<any>(null)
const editForm = ref({ account_name: '', bank_name: '', iban: '', currency: '', notes: '', logo_path: '' })

function openEdit(acc: any) {
  editingAccount.value = acc
  editForm.value = {
    account_name: acc.account_name || '',
    bank_name: acc.bank_name || '',
    iban: acc.iban || '',
    currency: acc.currency || '',
    notes: acc.notes || '',
    logo_path: acc.logo_path || '',
  }
}

function closeEdit() {
  editingAccount.value = null
}

const updateMutation = useMutation({
  mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
    bankApi.updateAccount(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
    closeEdit()
  },
})

function saveEdit() {
  if (!editingAccount.value) return
  const payload: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(editForm.value)) {
    if (v !== '') payload[k] = v
  }
  // Explicitly allow clearing logo_path
  if (editForm.value.logo_path === '') payload.logo_path = null
  updateMutation.mutate({ id: editingAccount.value.id, data: payload })
}

function selectLogo(url: string) {
  editForm.value.logo_path = editForm.value.logo_path === url ? '' : url
}

// ─── Admin: logo library management ─────────────────────────────────────────

const showLogoManager = ref(false)
const newLogoName = ref('')
const newLogoUrl = ref('')

const createLogoMutation = useMutation({
  mutationFn: (data: { name: string; url: string }) => bankLogosApi.create(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-logos'] })
    newLogoName.value = ''
    newLogoUrl.value = ''
  },
})

const deleteLogoMutation = useMutation({
  mutationFn: (id: number) => bankLogosApi.delete(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bank-logos'] })
  },
})

function addLogo() {
  const name = newLogoName.value.trim()
  const url = newLogoUrl.value.trim()
  if (!name || !url) return
  createLogoMutation.mutate({ name, url })
}

function confirmDeleteLogo(logo: any) {
  if (confirm(t('bank.logoDeleteConfirm', { name: logo.name }))) {
    deleteLogoMutation.mutate(logo.id)
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">{{ t('bank.bankAccountsTitle') }}</h1>
        <p class="mt-1 text-gray-500">{{ t('bank.bankAccountsSubtitle') }}</p>
      </div>
      <!-- Admin: manage logos library -->
      <button
        v-if="auth.isAdmin"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-gray-300 hover:bg-gray-50 text-gray-700"
        @click="showLogoManager = !showLogoManager"
      >
        <Landmark class="h-4 w-4" />
        {{ t('bank.manageLogos') }}
      </button>
    </div>

    <!-- Admin: Logo library panel -->
    <Card v-if="auth.isAdmin && showLogoManager">
      <CardHeader>
        <CardTitle>{{ t('bank.logoLibraryTitle') }}</CardTitle>
      </CardHeader>
      <CardContent class="space-y-4">
        <!-- Add form -->
        <div class="flex gap-2">
          <input
            v-model="newLogoName"
            type="text"
            :placeholder="t('bank.logoNamePlaceholder')"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <input
            v-model="newLogoUrl"
            type="url"
            :placeholder="t('bank.logoCdnUrlPlaceholder')"
            class="flex-[2] px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            class="flex items-center gap-1 px-3 py-2 text-sm rounded-md bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
            :disabled="!newLogoName.trim() || !newLogoUrl.trim() || createLogoMutation.isPending.value"
            @click="addLogo"
          >
            <Plus class="h-4 w-4" />
            {{ t('common.add') }}
          </button>
        </div>
        <!-- Existing logos -->
        <div v-if="!logos?.length" class="text-sm text-gray-400">{{ t('bank.noLogos') }}</div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          <div
            v-for="logo in logos"
            :key="logo.id"
            class="flex items-center gap-2 p-2 rounded-lg border border-gray-200 group"
          >
            <img :src="logo.url" :alt="logo.name" class="w-8 h-8 object-contain flex-shrink-0" />
            <span class="text-xs text-gray-700 truncate flex-1">{{ logo.name }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 flex-shrink-0"
              @click="confirmDeleteLogo(logo)"
            >
              <Trash2 class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>

    <div v-if="isLoading" class="text-center py-10 text-gray-500">{{ t('common.loading') }}</div>

    <div v-else-if="!accounts?.length" class="text-center py-10 text-gray-400">
      {{ t('bank.noAccounts') }}
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <Card v-for="acc in accounts" :key="acc.id">
        <CardContent class="pt-5 pb-4">
          <div class="flex items-start gap-4">
            <!-- Logo -->
            <div class="flex-shrink-0 w-14 h-14 rounded-lg bg-gray-100 flex items-center justify-center overflow-hidden">
              <img
                v-if="acc.logo_path"
                :src="acc.logo_path"
                :alt="acc.bank_name || acc.account_name"
                class="w-full h-full object-contain p-1"
              />
              <Landmark v-else class="h-7 w-7 text-gray-400" />
            </div>

            <!-- Details -->
            <div class="flex-1 min-w-0">
              <p class="font-semibold text-gray-900 truncate">
                {{ acc.account_name || acc.account_number }}
              </p>
              <p v-if="acc.bank_name" class="text-sm text-gray-500">{{ acc.bank_name }}</p>
              <p class="text-xs text-gray-400 font-mono mt-0.5">{{ acc.account_number }}</p>
              <p v-if="acc.iban" class="text-xs text-gray-400 font-mono">{{ acc.iban }}</p>
              <div class="flex items-center gap-2 mt-2">
                <span v-if="acc.currency" class="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-medium">
                  {{ acc.currency }}
                </span>
              </div>
              <p v-if="acc.notes" class="text-xs text-gray-400 mt-1 truncate">{{ acc.notes }}</p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 mt-4">
            <button
              class="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-gray-200 hover:bg-gray-50 text-gray-700"
              @click="openEdit(acc)"
            >
              <Pencil class="h-3.5 w-3.5" />
              {{ t('bank.editAccount') }}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Edit Modal -->
    <div
      v-if="editingAccount"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="closeEdit"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 mx-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-5">
          <h2 class="text-lg font-semibold text-gray-900">{{ t('bank.editAccount') }}</h2>
          <button class="text-gray-400 hover:text-gray-600" @click="closeEdit">
            <X class="h-5 w-5" />
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.accountName') }}</label>
            <input
              v-model="editForm.account_name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.bankName') }}</label>
            <input
              v-model="editForm.bank_name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.ibanLabel') }}</label>
            <input
              v-model="editForm.iban"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.currencyLabel') }}</label>
            <input
              v-model="editForm.currency"
              type="text"
              maxlength="3"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('bank.notesLabel') }}</label>
            <textarea
              v-model="editForm.notes"
              rows="2"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <!-- Logo picker -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('bank.logoLabel') }}</label>
            <div v-if="!logos?.length" class="text-sm text-gray-400">{{ t('bank.noLogosAvailable') }}</div>
            <div v-else class="grid grid-cols-3 gap-2">
              <!-- No logo option -->
              <button
                type="button"
                class="flex flex-col items-center justify-center gap-1 p-2 rounded-lg border-2 text-xs text-gray-500 transition-colors"
                :class="editForm.logo_path === '' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'"
                @click="editForm.logo_path = ''"
              >
                <Landmark class="h-6 w-6 text-gray-400" />
                {{ t('bank.noLogo') }}
              </button>
              <button
                v-for="logo in logos"
                :key="logo.id"
                type="button"
                class="flex flex-col items-center justify-center gap-1 p-2 rounded-lg border-2 text-xs text-gray-600 transition-colors"
                :class="editForm.logo_path === logo.url ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'"
                @click="selectLogo(logo.url)"
              >
                <img :src="logo.url" :alt="logo.name" class="w-8 h-8 object-contain" />
                <span class="truncate w-full text-center">{{ logo.name }}</span>
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            class="px-4 py-2 text-sm rounded-md border border-gray-200 hover:bg-gray-50 text-gray-700"
            @click="closeEdit"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            class="px-4 py-2 text-sm rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50"
            :disabled="updateMutation.isPending.value"
            @click="saveEdit"
          >
            {{ updateMutation.isPending.value ? t('common.loading') : t('bank.saveAccount') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
