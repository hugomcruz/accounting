<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Plus, Edit2, Trash2, X } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { useAuthStore } from '@/stores/auth'
import { authApi, hrApi } from '@/services/queries'

const { t } = useI18n()
const auth = useAuthStore()
const queryClient = useQueryClient()
const isAdmin = computed(() => auth.isAdmin)

const showModal = ref(false)
const editingUser = ref<any>(null)
// Optional employee link (any role)
const linkedEmployeeId = ref<number | null>(null)
// The previous employee linked to this user (to unlink when changed)
const previousEmployeeId = ref<number | null>(null)

const emptyForm = () => ({
  username: '', email: '', password: '',
  first_name: '', family_name: '', phone: '',
  role: 'accounting', is_active: true,
})
const form = ref(emptyForm())


const { data: users, isLoading } = useQuery({
  queryKey: ['users'],
  queryFn: async () => {
    const res = await authApi.getUsers()
    return res.data
  },
  enabled: isAdmin,
})

const { data: employees } = useQuery({
  queryKey: ['employees-for-link'],
  queryFn: async () => {
    const res = await hrApi.getEmployees({ is_active: 1 })
    return res.data as any[]
  },
  enabled: isAdmin,
})

// After saving a user, also update employee link if needed
async function syncEmployeeLink(userId: number) {
  const newEmpId = linkedEmployeeId.value
  const prevEmpId = previousEmployeeId.value

  // Unlink previous employee if changed
  if (prevEmpId && prevEmpId !== newEmpId) {
    await hrApi.updateEmployee(prevEmpId, { user_id: null })
  }
  // Link new employee
  if (newEmpId) {
    await hrApi.updateEmployee(newEmpId, { user_id: userId })
  }
  queryClient.invalidateQueries({ queryKey: ['employees-for-link'] })
}

const createMutation = useMutation({
  mutationFn: (data: any) => authApi.createUser(data),
  onSuccess: async (res: any) => {
    const userId = res.data?.id
    if (userId) await syncEmployeeLink(userId)
    queryClient.invalidateQueries({ queryKey: ['users'] })
    showModal.value = false
    form.value = emptyForm()
    linkedEmployeeId.value = null
    previousEmployeeId.value = null
  },
})

const updateMutation = useMutation({
  mutationFn: ({ id, data }: { id: number; data: any }) => authApi.updateUser(id, data),
  onSuccess: async (_: any, vars: any) => {
    await syncEmployeeLink(vars.id)
    queryClient.invalidateQueries({ queryKey: ['users'] })
    showModal.value = false
    editingUser.value = null
    form.value = emptyForm()
    linkedEmployeeId.value = null
    previousEmployeeId.value = null
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => authApi.deleteUser(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
})

function openCreate() {
  editingUser.value = null
  form.value = emptyForm()
  linkedEmployeeId.value = null
  previousEmployeeId.value = null
  showModal.value = true
}

function openEdit(user: any) {
  editingUser.value = user
  form.value = {
    username: user.username || '',
    email: user.email || '',
    password: '',
    first_name: user.first_name || '',
    family_name: user.family_name || user.last_name || '',
    phone: user.phone || '',
    role: user.role || 'accounting',
    is_active: user.is_active ?? true,
  }
  // Find the employee currently linked to this user
  const linked = employees.value?.find((e: any) => e.user_id === user.id) ?? null
  linkedEmployeeId.value = linked?.id ?? null
  previousEmployeeId.value = linked?.id ?? null
  showModal.value = true
}

function handleSubmit() {
  const payload: any = { ...form.value }
  // Auto-compute full_name from first + family name
  payload.full_name = [payload.first_name, payload.family_name].filter(Boolean).join(' ')
  // Null out empty optional strings so EmailStr validation doesn't fail
  if (!payload.email) payload.email = null
  if (!payload.phone) payload.phone = null
  if (editingUser.value && !payload.password) {
    delete payload.password
  }
  if (editingUser.value) {
    updateMutation.mutate({ id: editingUser.value.id, data: payload })
  } else {
    createMutation.mutate(payload)
  }
}

const isSaving = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

function roleBadge(role: string) {
  const r = role?.toLowerCase()
  if (r === 'admin') return 'bg-red-100 text-red-700'
  if (r === 'finance') return 'bg-blue-100 text-blue-700'
  if (r === 'accounting') return 'bg-purple-100 text-purple-700'
  if (r === 'user') return 'bg-green-100 text-green-700'
  return 'bg-gray-100 text-gray-600'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">{{ t('users.title') }}</h1>
        <p class="mt-1 text-gray-500">{{ t('users.subtitle') }}</p>
      </div>
      <button
        v-if="isAdmin"
        class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        @click="openCreate"
      >
        <Plus class="h-4 w-4" />
        {{ t('users.addUser') }}
      </button>
    </div>

    <div v-if="!isAdmin" class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
      {{ t('users.noAdminWarning') }}
    </div>

    <Card v-else>
      <CardHeader><CardTitle>{{ t('users.listCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!users?.length" class="text-center py-6 text-gray-400">{{ t('users.noUsers') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('users.tableUsername') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableName') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableEmail') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableRole') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableEmployee') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableStatus') }}</th>
                <th class="pb-2 font-medium">{{ t('users.tableLastLogin') }}</th>
                <th class="pb-2 font-medium">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-3 font-medium">{{ user.username }}</td>
                <td class="py-3">{{ [user.first_name, user.family_name || user.last_name].filter(Boolean).join(' ') || '-' }}</td>
                <td class="py-3 text-gray-500">{{ user.email || '-' }}</td>
                <td class="py-3">
                  <span :class="roleBadge(user.role)" class="px-2 py-0.5 rounded-full text-xs font-medium">
                    {{ user.role }}
                  </span>
                </td>
                <td class="py-3 text-gray-500 text-xs">
                  {{ employees?.find((e: any) => e.user_id === user.id) ? `${employees.find((e: any) => e.user_id === user.id).first_name} ${employees.find((e: any) => e.user_id === user.id).last_name}` : '-' }}
                </td>
                <td class="py-3">
                  <span :class="user.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                    class="px-2 py-0.5 rounded-full text-xs font-medium">
                    {{ user.is_active ? t('common.active') : t('common.inactive') }}
                  </span>
                </td>
                <td class="py-3 text-gray-500 text-xs">
                  {{ user.last_login ? new Date(user.last_login).toLocaleString() : t('common.never') }}
                </td>
                <td class="py-3">
                  <div class="flex gap-1">
                    <button class="p-1.5 text-blue-500 hover:bg-blue-50 rounded" @click="openEdit(user)">
                      <Edit2 class="h-3.5 w-3.5" />
                    </button>
                    <button
                      v-if="user.id !== auth.user?.id"
                      class="p-1.5 text-red-400 hover:bg-red-50 rounded"
                      @click="deleteMutation.mutate(user.id)"
                    >
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

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between p-6 border-b">
          <h2 class="text-lg font-semibold">{{ editingUser ? t('users.editUser') : t('users.newUser') }}</h2>
          <button @click="showModal = false"><X class="h-5 w-5 text-gray-400" /></button>
        </div>
        <div class="p-6 space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('users.usernameRequired') }}</label>
              <input v-model="form.username" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('common.email') }}</label>
              <input v-model="form.email" type="email"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                {{ editingUser ? t('users.passwordEdit') : t('users.passwordNew') }}
              </label>
              <input v-model="form.password" type="password"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('users.roleLabel') }}</label>
              <select v-model="form.role"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                <option value="admin">{{ t('users.roleAdmin') }}</option>
                <option value="accounting">{{ t('users.roleAccounting') }}</option>
                <option value="finance">{{ t('users.roleFinance') }}</option>
                <option value="user">{{ t('users.roleUser') }}</option>
              </select>
            </div>
            <!-- Employee link: optional for any role -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('users.linkedEmployee') }}</label>
              <select v-model="linkedEmployeeId"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                <option :value="null">— {{ t('users.noEmployeeLink') }} —</option>
                <option
                  v-for="emp in employees"
                  :key="emp.id"
                  :value="emp.id"
                  :disabled="emp.user_id && emp.user_id !== editingUser?.id"
                >
                  {{ emp.first_name }} {{ emp.last_name }} ({{ emp.employee_id }})
                  <template v-if="emp.user_id && emp.user_id !== editingUser?.id"> ⚠ linked</template>
                </option>
              </select>
              <p class="mt-1 text-xs text-gray-500">{{ t('users.linkedEmployeeHint') }}</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('users.firstName') }}</label>
              <input v-model="form.first_name" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('users.lastName') }}</label>
              <input v-model="form.family_name" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('common.phone') }}</label>
              <input v-model="form.phone" type="tel"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div class="flex items-center gap-2 mt-4">
              <input v-model="form.is_active" type="checkbox" id="user_is_active" class="w-4 h-4 text-blue-600 border-gray-300 rounded" />
              <label for="user_is_active" class="text-sm font-medium text-gray-700">{{ t('users.activeLabel') }}</label>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-3 px-6 py-4 border-t">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg" @click="showModal = false">{{ t('common.cancel') }}</button>
          <button
            :disabled="isSaving || !form.username"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="handleSubmit"
          >
            {{ isSaving ? t('common.saving') : (editingUser ? t('common.saveChanges') : t('users.createUser')) }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
