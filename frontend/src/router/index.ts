import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Augment Vue Router's RouteMeta to include our custom flags
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    allowUser?: boolean         // 'user' role is allowed
    blockedForAccountant?: boolean  // 'accounting' role is blocked
    adminOnly?: boolean         // only 'admin' role
  }
}

import Layout from '@/components/Layout.vue'
import Login from '@/pages/Login.vue'
import Dashboard from '@/pages/Dashboard.vue'
import InvoiceList from '@/pages/InvoiceList.vue'
import InvoiceDetail from '@/pages/InvoiceDetail.vue'
import InvoiceSales from '@/pages/InvoiceSales.vue'
import InvoicePurchases from '@/pages/InvoicePurchases.vue'
import UploadInvoice from '@/pages/UploadInvoice.vue'
import ReviewInvoices from '@/pages/ReviewInvoices.vue'
import SAFTImport from '@/pages/SAFTImport.vue'
import CompanyList from '@/pages/CompanyList.vue'
import CompanyDetail from '@/pages/CompanyDetail.vue'
import BankTransactions from '@/pages/BankTransactions.vue'
import BankStatements from '@/pages/BankStatements.vue'
import BankStatementDetail from '@/pages/BankStatementDetail.vue'
import BankAccounts from '@/pages/BankAccounts.vue'
import Reconciliation from '@/pages/Reconciliation.vue'
import ReconciliationOverview from '@/pages/ReconciliationOverview.vue'
import ReconciliationResults from '@/pages/ReconciliationResults.vue'
import Employees from '@/pages/Employees.vue'
import Payroll from '@/pages/Payroll.vue'
import Users from '@/pages/Users.vue'
import Settings from '@/pages/Settings.vue'
import ExportInvoices from '@/pages/ExportInvoices.vue'
import ExpenseReports from '@/pages/ExpenseReports.vue'
import ExpenseReportDetail from '@/pages/ExpenseReportDetail.vue'
import EndOfMonth from '@/pages/EndOfMonth.vue'

// Route meta flags:
//   allowUser: true          → the 'user' role is allowed on this route
//   blockedForAccountant: true → the 'accounting' role is blocked on this route
//   adminOnly: true          → only 'admin' role allowed

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    {
      path: '/',
      component: Layout,
      meta: { requiresAuth: true },
      children: [
        { path: '', component: Dashboard },
        { path: 'invoices', component: InvoiceList },
        { path: 'invoices/sales', component: InvoiceSales },
        { path: 'invoices/purchases', component: InvoicePurchases },
        { path: 'invoices/review', component: ReviewInvoices, meta: { blockedForAccountant: true } },
        { path: 'invoices/:id', component: InvoiceDetail },
        { path: 'upload', component: UploadInvoice, meta: { blockedForAccountant: true } },
        { path: 'saft', component: SAFTImport, meta: { blockedForAccountant: true } },
        { path: 'companies', component: CompanyList },
        { path: 'companies/:id', component: CompanyDetail },
        { path: 'bank', component: BankTransactions },
        { path: 'bank/statements', component: BankStatements, meta: { blockedForAccountant: true } },
        { path: 'bank/statements/:id', component: BankStatementDetail, meta: { blockedForAccountant: true } },
        { path: 'bank/accounts', component: BankAccounts, meta: { blockedForAccountant: true } },
        { path: 'reconciliation', component: Reconciliation },
        { path: 'reconciliation/overview', component: ReconciliationOverview },
        { path: 'reconciliation/results', component: ReconciliationResults },
        { path: 'hr/employees', component: Employees },
        { path: 'hr/payroll', component: Payroll },
        { path: 'admin/users', component: Users, meta: { adminOnly: true } },
        { path: 'settings', component: Settings, meta: { adminOnly: true } },
        { path: 'exports/invoices', component: ExportInvoices },
        { path: 'expenses', component: ExpenseReports, meta: { allowUser: true } },
        { path: 'expenses/:id', component: ExpenseReportDetail, meta: { allowUser: true } },
        { path: 'processes/end-of-month', component: EndOfMonth },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return { path: '/login' }
  }
  if (to.path === '/login' && auth.token) {
    return auth.isUser ? { path: '/expenses' } : { path: '/' }
  }

  if (!auth.token) return  // unauthenticated, let other guards handle it

  const role = auth.role

  // 'user' role: only routes with allowUser=true are accessible
  if (role === 'user' && !to.meta.allowUser) {
    return { path: '/expenses' }
  }

  // 'accounting' role: blocked from import/upload routes
  if (role === 'accounting' && to.meta.blockedForAccountant) {
    return { path: '/' }
  }

  // adminOnly routes
  if (to.meta.adminOnly && role !== 'admin') {
    return { path: '/' }
  }
})

export default router
