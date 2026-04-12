<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { Plus, Edit2, Trash2, X, DollarSign } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CardContent from '@/components/ui/CardContent.vue'
import { hrApi } from '@/services/queries'

const { t } = useI18n()
const queryClient = useQueryClient()

const filterActive = ref<string>('true')
const showModal = ref(false)
const editingEmployee = ref<any>(null)
const showCompensationModal = ref<any>(null)
const newCompensation = ref({ benefit_type_id: '', amount: '' })

const emptyForm = () => ({
  employee_id: '', nif: '', niss: '', first_name: '', last_name: '',
  email: '', phone: '', position: '', department: '',
  hire_date: '', is_active: true, notes: '',
})

const form = ref(emptyForm())

const queryParams = computed(() => ({
  is_active: filterActive.value !== '' ? filterActive.value === 'true' : undefined,
}))

const { data: employees, isLoading } = useQuery({
  queryKey: ['employees', queryParams],
  queryFn: async () => {
    const res = await hrApi.getEmployees(queryParams.value)
    return res.data
  },
})

const { data: benefitTypes } = useQuery({
  queryKey: ['benefit-types'],
  queryFn: async () => {
    const res = await hrApi.getBenefitTypes()
    return res.data
  },
})

const createMutation = useMutation({
  mutationFn: (data: any) => hrApi.createEmployee(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['employees'] })
    showModal.value = false
    form.value = emptyForm()
  },
})

const updateMutation = useMutation({
  mutationFn: ({ id, data }: { id: number; data: any }) => hrApi.updateEmployee(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['employees'] })
    showModal.value = false
    editingEmployee.value = null
    form.value = emptyForm()
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => hrApi.removeEmployee(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
})

const addCompMutation = useMutation({
  mutationFn: ({ employeeId, data }: { employeeId: number; data: any }) =>
    hrApi.addCompensation(employeeId, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['employees'] })
    newCompensation.value = { benefit_type_id: '', amount: '' }
  },
})

const removeCompMutation = useMutation({
  mutationFn: ({ employeeId, compensationId }: { employeeId: number; compensationId: number }) =>
    hrApi.removeCompensation(employeeId, compensationId),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
})

function openCreate() {
  editingEmployee.value = null
  form.value = emptyForm()
  showModal.value = true
}

function openEdit(emp: any) {
  editingEmployee.value = emp
  form.value = {
    employee_id: emp.employee_id || '',
    nif: emp.nif || '',
    niss: emp.social_security_number || '',
    first_name: emp.first_name || '',
    last_name: emp.last_name || '',
    email: emp.email || '',
    phone: emp.phone || '',
    position: emp.position || '',
    department: emp.department || '',
    hire_date: emp.hire_date ? emp.hire_date.split('T')[0] : '',
    is_active: emp.is_active ?? true,
    notes: emp.notes || '',
  }
  showModal.value = true
}

function buildPayload() {
  const f = form.value
  return {
    employee_id: f.employee_id,
    first_name: f.first_name,
    last_name: f.last_name,
    nif: f.nif || null,
    social_security_number: (f as any).niss || null,
    email: f.email || null,
    phone: f.phone || null,
    position: f.position || null,
    department: f.department || null,
    hire_date: f.hire_date || new Date().toISOString().split('T')[0],
    notes: f.notes || null,
  }
}

function handleSubmit() {
  if (editingEmployee.value) {
    updateMutation.mutate({ id: editingEmployee.value.id, data: buildPayload() })
  } else {
    createMutation.mutate(buildPayload())
  }
}

const isSaving = computed(() => createMutation.isPending.value || updateMutation.isPending.value)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">{{ t('employees.title') }}</h1>
        <p class="mt-1 text-gray-500">{{ t('employees.subtitle') }}</p>
      </div>
      <button
        class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        @click="openCreate"
      >
        <Plus class="h-4 w-4" />
        {{ t('employees.addEmployee') }}
      </button>
    </div>

    <Card>
      <CardContent class="pt-4">
        <div class="flex gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('employees.statusLabel') }}</label>
            <select v-model="filterActive" class="px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
              <option value="">{{ t('common.all') }}</option>
              <option value="true">{{ t('employees.filterActive') }}</option>
              <option value="false">{{ t('employees.filterInactive') }}</option>
            </select>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle>{{ t('employees.listCard') }}</CardTitle></CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-6 text-gray-500">{{ t('common.loading') }}</div>
        <div v-else-if="!employees?.length" class="text-center py-6 text-gray-400">{{ t('employees.noEmployees') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-gray-500">
                <th class="pb-2 font-medium">{{ t('employees.tableId') }}</th>
                <th class="pb-2 font-medium">{{ t('employees.tableName') }}</th>
                <th class="pb-2 font-medium">{{ t('employees.tablePosition') }}</th>
                <th class="pb-2 font-medium">{{ t('employees.tableDepartment') }}</th>
                <th class="pb-2 font-medium">{{ t('employees.tableEmail') }}</th>
                <th class="pb-2 font-medium">{{ t('employees.tableStatus') }}</th>
                <th class="pb-2 font-medium">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="emp in employees" :key="emp.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="py-3 font-mono text-xs">{{ emp.employee_id }}</td>
                <td class="py-3 font-medium">{{ emp.first_name }} {{ emp.last_name }}</td>
                <td class="py-3">{{ emp.position || '-' }}</td>
                <td class="py-3">{{ emp.department || '-' }}</td>
                <td class="py-3 text-gray-500">{{ emp.email || '-' }}</td>
                <td class="py-3">
                  <span :class="emp.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'"
                    class="px-2 py-0.5 rounded-full text-xs font-medium">
                    {{ emp.is_active ? t('common.active') : t('common.inactive') }}
                  </span>
                </td>
                <td class="py-3">
                  <div class="flex gap-1">
                    <button class="p-1.5 text-blue-500 hover:bg-blue-50 rounded" @click="openEdit(emp)">
                      <Edit2 class="h-3.5 w-3.5" />
                    </button>
                    <button class="p-1.5 text-green-500 hover:bg-green-50 rounded" @click="showCompensationModal = emp">
                      <DollarSign class="h-3.5 w-3.5" />
                    </button>
                    <button class="p-1.5 text-red-400 hover:bg-red-50 rounded" @click="deleteMutation.mutate(emp.id)">
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
      <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between p-6 border-b">
          <h2 class="text-lg font-semibold">{{ editingEmployee ? t('employees.editEmployee') : t('employees.newEmployee') }}</h2>
          <button @click="showModal = false"><X class="h-5 w-5 text-gray-400" /></button>
        </div>
        <div class="p-6 space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.employeeId') }}</label>
              <input v-model="form.employee_id" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.nif') }}</label>
              <input v-model="form.nif" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.niss') }}</label>
              <input v-model="form.niss" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.firstName') }}</label>
              <input v-model="form.first_name" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.lastName') }}</label>
              <input v-model="form.last_name" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.email') }}</label>
              <input v-model="form.email" type="email"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.phone') }}</label>
              <input v-model="form.phone" type="tel"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.position') }}</label>
              <input v-model="form.position" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.department') }}</label>
              <input v-model="form.department" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.hireDate') }}</label>
              <input v-model="form.hire_date" type="date"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div class="flex items-center gap-2 mt-4">
              <input v-model="form.is_active" type="checkbox" id="is_active" class="w-4 h-4 text-blue-600 border-gray-300 rounded" />
              <label for="is_active" class="text-sm font-medium text-gray-700">{{ t('employees.activeLabel') }}</label>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('employees.notes') }}</label>
            <textarea v-model="form.notes" rows="3"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 px-6 py-4 border-t">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg" @click="showModal = false">{{ t('common.cancel') }}</button>
          <button
            :disabled="isSaving"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            @click="handleSubmit"
          >
            {{ isSaving ? t('common.saving') : (editingEmployee ? t('common.saveChanges') : t('employees.createEmployee')) }}
          </button>
        </div>
      </div>
    </div>

    <!-- Compensation Modal -->
    <div v-if="showCompensationModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div class="flex items-center justify-between p-6 border-b">
          <h2 class="text-lg font-semibold">
            {{ t('employees.compensationTitle', { name: `${showCompensationModal.first_name} ${showCompensationModal.last_name}` }) }}
          </h2>
          <button @click="showCompensationModal = null"><X class="h-5 w-5 text-gray-400" /></button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-2">
            <div v-if="!showCompensationModal.compensations?.length" class="text-gray-400 text-sm">{{ t('employees.noCompensation') }}</div>
            <div v-for="comp in showCompensationModal.compensations" :key="comp.id"
              class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
              <div>
                <p class="font-medium text-sm">{{ comp.benefit_type?.name || comp.benefit_type_id }}</p>
                <p class="text-gray-500 text-xs">€{{ Number(comp.amount).toFixed(2) }}</p>
              </div>
              <button class="p-1 text-red-400 hover:bg-red-50 rounded"
                @click="removeCompMutation.mutate({ employeeId: showCompensationModal.id, compensationId: comp.id })">
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div class="border-t pt-4">
            <p class="text-sm font-medium text-gray-700 mb-3">{{ t('employees.addCompensation') }}</p>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-gray-600 mb-1">{{ t('employees.compType') }}</label>
                <select v-model="newCompensation.benefit_type_id"
                  class="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500">
                  <option value="">{{ t('employees.selectType') }}</option>
                  <option v-for="bt in benefitTypes" :key="bt.id" :value="String(bt.id)">{{ bt.name }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-gray-600 mb-1">{{ t('employees.compAmount') }}</label>
                <input v-model="newCompensation.amount" type="number" step="0.01" min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <button
              :disabled="!newCompensation.benefit_type_id || !newCompensation.amount"
              class="mt-3 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
              @click="addCompMutation.mutate({ employeeId: showCompensationModal.id, data: newCompensation })"
            >
              {{ t('common.add') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
