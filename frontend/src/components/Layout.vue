<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { setLocale } from '@/i18n'
import bwLogoImageOnly from '@/assets/bw-logo-image-only.png'
import {
  LayoutDashboard, FileText, Upload, ClipboardList, Database,
  Building2, Users, CreditCard, RefreshCw, UserCog,
  Settings, LogOut, Menu, ChevronDown, Layers, ListChecks, Download, Receipt, Globe, CalendarCheck,
  TrendingUp, ShoppingCart, Landmark, GitBranch,
} from 'lucide-vue-next'

const { t, locale } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(false)
const openGroups = ref<Record<string, boolean>>({})

function toggleGroup(name: string) {
  openGroups.value[name] = !openGroups.value[name]
}

const isAdmin = computed(() => auth.isAdmin)
const isAccountant = computed(() => auth.isAccountant)
const isUser = computed(() => auth.isUser)

// Full navigation definition with role flags
// blockedForAccountant: hidden for 'accounting' role
// userOnly: only shown to 'user' role (and admin/accounting who also have access)
const allNavigation = computed(() => [
  { name: t('nav.dashboard'), href: '/', icon: LayoutDashboard, hidden: isUser.value },
  {
    name: t('nav.invoicesGroup'),
    icon: FileText,
    hidden: isUser.value,
    children: [
      { name: t('nav.salesInvoices'), href: '/invoices/sales', icon: TrendingUp },
      { name: t('nav.purchasesInvoices'), href: '/invoices/purchases', icon: ShoppingCart },
      { name: t('nav.upload'), href: '/upload', icon: Upload, blockedForAccountant: true },
    ],
  },
  {
    name: t('nav.importGroup'),
    icon: Database,
    hidden: isUser.value || isAccountant.value,
    children: [
      { name: t('nav.saftImport'), href: '/saft', icon: Database },
      { name: t('nav.uploadStatements'), href: '/bank/statements', icon: Upload },
      { name: t('nav.bulkInvoices'), href: '/invoices/review', icon: ClipboardList },
    ],
  },
  {
    name: t('nav.bankGroup'),
    icon: CreditCard,
    hidden: isUser.value,
    children: [
      { name: t('nav.transactions'), href: '/bank', icon: CreditCard },
      { name: t('nav.bankAccounts'), href: '/bank/accounts', icon: Landmark },
    ],
  },
  {
    name: t('nav.reconciliationGroup'),
    icon: RefreshCw,
    hidden: isUser.value,
    children: [
      { name: t('nav.autoReconciliation'), href: '/reconciliation', icon: RefreshCw },
      { name: t('nav.allReconciliations'), href: '/reconciliation/overview', icon: ListChecks },
      { name: t('nav.reconciliationResults'), href: '/reconciliation/results', icon: GitBranch },
    ],
  },
  { name: t('nav.companies'), href: '/companies', icon: Building2, hidden: isUser.value },
  { name: t('nav.employees'), href: '/hr/employees', icon: Users, hidden: isUser.value },
  { name: t('nav.payroll'), href: '/hr/payroll', icon: CreditCard, hidden: isUser.value },
  { name: t('nav.expenseReports'), href: '/expenses', icon: Receipt },
  {
    name: t('nav.exportsGroup'),
    icon: Download,
    hidden: isUser.value,
    children: [
      { name: t('nav.invoiceExports'), href: '/exports/invoices', icon: FileText },
    ],
  },
  {
    name: t('nav.processesGroup'),
    icon: CalendarCheck,
    hidden: isUser.value,
    children: [
      { name: t('nav.endOfMonth'), href: '/processes/end-of-month', icon: CalendarCheck },
    ],
  },
])

// Filtered navigation: apply role-based visibility
const navigation = computed(() => {
  return allNavigation.value
    .filter(item => !item.hidden)
    .map(item => {
      if (!item.children) return item
      const filteredChildren = item.children.filter(
        child => !(child.blockedForAccountant && isAccountant.value)
      )
      return { ...item, children: filteredChildren }
    })
    .filter(item => !item.children || item.children.length > 0)
})

const adminNav = computed(() => [
  { name: t('nav.userManagement'), href: '/admin/users', icon: UserCog },
  { name: t('nav.settings'), href: '/settings', icon: Settings },
])

// Auto-expand a group if the current route is under it
function isGroupSection(children: { href: string }[]) {
  return children.some(c => route.path === c.href || route.path.startsWith(c.href + '/'))
}

function isGroupOpen(name: string, children: { href: string }[]) {
  return openGroups.value[name] || isGroupSection(children)
}

function isActive(href: string) {
  if (href === '/') return route.path === '/'
  return route.path === href || route.path.startsWith(href + '/')
}

function toggleLocale() {
  setLocale(locale.value === 'en' ? 'pt' : 'en')
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50">
    <!-- Sidebar -->
    <aside
      :class="[
        'fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 flex flex-col',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      ]"
    >
      <!-- Logo -->
      <div class="flex items-center gap-2 px-6 py-5 border-b border-gray-100">
        <img :src="bwLogoImageOnly" alt="BrightWaves" class="h-8 w-auto" />
        <div>
          <p class="font-bold text-gray-900 text-sm">Bright Waves Finance</p>
          <p class="text-xs text-gray-500">{{ t('nav.accounting') }}</p>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <template v-for="item in navigation" :key="item.name">
          <!-- Regular nav item -->
          <RouterLink
            v-if="!item.children"
            :to="item.href"
            :class="[
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive(item.href)
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-700 hover:bg-gray-100'
            ]"
            @click="sidebarOpen = false"
          >
            <component :is="item.icon" class="h-5 w-5 flex-shrink-0" />
            {{ item.name }}
          </RouterLink>

          <!-- Group with submenu -->
          <div v-else>
            <button
              :class="[
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isGroupSection(item.children)
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100'
              ]"
              @click="toggleGroup(item.name)"
            >
              <component :is="item.icon" class="h-5 w-5 flex-shrink-0" />
              <span class="flex-1 text-left">{{ item.name }}</span>
              <ChevronDown
                :class="['h-4 w-4 transition-transform', isGroupOpen(item.name, item.children) ? 'rotate-180' : '']"
              />
            </button>
            <div v-if="isGroupOpen(item.name, item.children)" class="mt-1 ml-4 space-y-1 border-l-2 border-gray-100 pl-3">
              <RouterLink
                v-for="child in item.children"
                :key="child.href"
                :to="child.href"
                :class="[
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                  isActive(child.href)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100'
                ]"
                @click="sidebarOpen = false"
              >
                <component :is="child.icon" class="h-4 w-4 flex-shrink-0" />
                {{ child.name }}
              </RouterLink>
            </div>
          </div>
        </template>

        <div v-if="isAdmin" class="pt-4">
          <p class="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{{ t('nav.adminSection') }}</p>
          <RouterLink
            v-for="item in adminNav"
            :key="item.href"
            :to="item.href"
            :class="[
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive(item.href)
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-700 hover:bg-gray-100'
            ]"
            @click="sidebarOpen = false"
          >
            <component :is="item.icon" class="h-5 w-5 flex-shrink-0" />
            {{ item.name }}
          </RouterLink>
        </div>
      </nav>

      <!-- User info -->
      <div class="border-t border-gray-100 p-4">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
            <span class="text-primary-700 font-semibold text-xs">
              {{ (auth.user?.full_name?.charAt(0) || auth.user?.username?.charAt(0) || 'U').toUpperCase() }}
            </span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ auth.user?.full_name || auth.user?.username }}</p>
            <p class="text-xs text-gray-500 truncate capitalize">{{ auth.user?.role?.toLowerCase() }}</p>
          </div>
        </div>
        <!-- Language switcher -->
        <button
          @click="toggleLocale"
          class="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors mb-1"
          :title="locale === 'en' ? 'Mudar para Português' : 'Switch to English'"
        >
          <Globe class="h-4 w-4" />
          <span>{{ locale === 'en' ? 'Português' : 'English' }}</span>
        </button>
        <button
          @click="logout"
          class="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <LogOut class="h-4 w-4" />
          {{ t('nav.signOut') }}
        </button>
      </div>
    </aside>

    <!-- Overlay for mobile -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
      @click="sidebarOpen = false"
    />

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Top bar (mobile) -->
      <header class="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
        <button @click="sidebarOpen = !sidebarOpen" class="p-2 text-gray-500 hover:text-gray-900">
          <Menu class="h-6 w-6" />
        </button>
        <span class="font-bold text-gray-900">Bright Waves Finance</span>
        <button @click="toggleLocale" class="w-10 flex items-center justify-center text-gray-500 hover:text-gray-900" :title="locale === 'en' ? 'PT' : 'EN'">
          <Globe class="h-5 w-5" />
        </button>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
