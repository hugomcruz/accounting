import api from './api';
import { Company, Invoice, UploadResponse, SAFTImport, InvoiceProcessingQueue, ExpenseReport } from '@/types';

// Companies
export const companiesApi = {
  getAll: (params?: { is_customer?: boolean; is_supplier?: boolean }) =>
    api.get<Company[]>('/companies', { params }),
  
  getById: (id: number) =>
    api.get<Company>(`/companies/${id}`),
  
  getByNif: (nif: string) =>
    api.get<Company>(`/companies/nif/${nif}`),
  
  create: (data: Partial<Company>) =>
    api.post<Company>('/companies', data),
  
  update: (id: number, data: Partial<Company>) =>
    api.patch<Company>(`/companies/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/companies/${id}`),
};

// Invoices
export const invoicesApi = {
  getAll: (params?: { invoice_type?: string; status?: string; start_date?: string; end_date?: string; limit?: number; skip?: number; order_by?: string; reconciled_only?: boolean }) =>
    api.get<Invoice[]>('/invoices', { params }),
  
  getCount: (params?: { invoice_type?: string; status?: string }) =>
    api.get<{ count: number }>('/invoices/count', { params }),
  
  getById: (id: number) =>
    api.get<Invoice>(`/invoices/${id}`),
  
  getFileUrl: (id: number) =>
    api.get<{ url: string }>(`/invoices/${id}/file-url`),

  attachFile: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ file_path: string; url: string }>(`/invoices/${id}/attach-file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  create: (data: Partial<Invoice>) =>
    api.post<Invoice>('/invoices', data),
  
  update: (id: number, data: Partial<Invoice>) =>
    api.patch<Invoice>(`/invoices/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/invoices/${id}`),
};

// Invoice Direct Payments
export const invoicePaymentsApi = {
  getAll: (invoiceId: number) =>
    api.get(`/invoices/${invoiceId}/payments`),
  add: (invoiceId: number, data: Record<string, unknown>) =>
    api.post(`/invoices/${invoiceId}/payments`, data),
  delete: (invoiceId: number, paymentId: number) =>
    api.delete(`/invoices/${invoiceId}/payments/${paymentId}`),
};

// Invoice Comments
export const invoiceCommentsApi = {
  getAll: (invoiceId: number) =>
    api.get(`/invoices/${invoiceId}/comments`),
  add: (invoiceId: number, body: string) =>
    api.post(`/invoices/${invoiceId}/comments`, { body }),
  update: (invoiceId: number, commentId: number, body: string) =>
    api.patch(`/invoices/${invoiceId}/comments/${commentId}`, { body }),
  delete: (invoiceId: number, commentId: number) =>
    api.delete(`/invoices/${invoiceId}/comments/${commentId}`),
};

// Upload
export const uploadApi = {
  uploadInvoice: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<UploadResponse>('/upload/invoice', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  
  processInvoice: (filePath: string, createInvoice: boolean = true, notes?: string, qrData?: object) =>
    api.post('/upload/invoice/process', {
      file_path: filePath,
      create_invoice: createInvoice,
      notes: notes ?? null,
      qr_data: qrData ?? null,
    }),
};

// Invoice Queue
export const invoiceQueueApi = {
  uploadBulk: (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    return api.post('/queue/upload-bulk', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  
  getAll: (params?: { status?: string }) =>
    api.get<InvoiceProcessingQueue[]>('/queue', { params }),
  
  getById: (id: number) =>
    api.get<InvoiceProcessingQueue>(`/queue/${id}`),
  
  processItem: (id: number) =>
    api.post(`/queue/${id}/process`),
  
  updateItem: (id: number, qr_data: any) =>
    api.put(`/queue/${id}`, qr_data),
  
  deleteItem: (id: number) =>
    api.delete(`/queue/${id}`),
  
  getFileUrl: (id: number) =>
    api.get<{ url: string }>(`/queue/${id}/file-url`),
};

// SAFT
export const saftApi = {
  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<SAFTImport>('/saft/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  
  getImports: () =>
    api.get<SAFTImport[]>('/saft/imports'),
  
  getImportById: (id: number) =>
    api.get<SAFTImport>(`/saft/imports/${id}`),
};

// Bank
export const bankApi = {
  getStatements: () => api.get('/bank/statements'),
  getStatement: (id: number) => api.get(`/bank/statements/${id}`),
  deleteStatement: (id: number) => api.delete(`/bank/statements/${id}`),
  importStatement: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/bank/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  reconcileStatement: (id: number) => api.post(`/bank/statements/${id}/reconcile`),
  getTransactions: (params?: Record<string, string | number | boolean>) =>
    api.get('/bank/transactions', { params }),
  getTransaction: (id: number) => api.get(`/bank/transactions/${id}`),
  reconcileTransaction: (txId: number, invoiceId: number) =>
    api.patch(`/bank/transactions/${txId}/reconcile`, null, { params: { invoice_id: invoiceId } }),
  unreconcileTransaction: (txId: number) =>
    api.delete(`/bank/transactions/${txId}/reconcile`),
  linkTransfer: (txId: number, counterpartId: number) =>
    api.post(`/bank/transactions/${txId}/link-transfer`, null, { params: { counterpart_id: counterpartId } }),
  unlinkTransfer: (txId: number) =>
    api.delete(`/bank/transactions/${txId}/link-transfer`),
  getAccounts: () => api.get('/bank/accounts'),
  getAccount: (id: number) => api.get(`/bank/accounts/${id}`),
  updateAccount: (id: number, data: Record<string, unknown>) => api.patch(`/bank/accounts/${id}`, data),
  getTransactionNotes: (txId: number) => api.get(`/bank/transactions/${txId}/notes`),
  addTransactionNote: (txId: number, body: string) => api.post(`/bank/transactions/${txId}/notes`, { body }),
  updateTransactionNote: (txId: number, noteId: number, body: string) =>
    api.patch(`/bank/transactions/${txId}/notes/${noteId}`, { body }),
  deleteTransactionNote: (txId: number, noteId: number) =>
    api.delete(`/bank/transactions/${txId}/notes/${noteId}`),
};

export const bankLogosApi = {
  getAll: () => api.get('/bank/logos'),
  create: (data: { name: string; url: string }) => api.post('/bank/logos', data),
  delete: (id: number) => api.delete(`/bank/logos/${id}`),
};

// HR
export const hrApi = {
  getEmployees: (params?: Record<string, string | number>) => api.get('/hr/employees', { params }),
  createEmployee: (data: Record<string, unknown>) => api.post('/hr/employees', data),
  updateEmployee: (id: number, data: Record<string, unknown>) => api.patch(`/hr/employees/${id}`, data),
  removeEmployee: (id: number) => api.delete(`/hr/employees/${id}`),
  getBenefitTypes: () => api.get('/hr/benefit-types'),
  addCompensation: (employeeId: number, data: Record<string, unknown>) =>
    api.post(`/hr/employees/${employeeId}/compensations`, data),
  removeCompensation: (employeeId: number, compensationId: number) => api.delete(`/hr/employees/${employeeId}/compensations/${compensationId}`),
  getPayrollPeriods: () => api.get('/hr/payroll/periods?limit=200'),
  createPayrollPeriod: (data: Record<string, unknown>) => api.post('/hr/payroll/periods', data),
  processPayrollPeriod: (id: number) => api.post(`/hr/payroll/periods/${id}/process`),
  uploadPayrollFile: (id: number, formData: FormData) =>
    api.post(`/hr/payroll/periods/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
};

// Settings
export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data: Record<string, unknown>) => api.post('/settings', data),
};

// Auth / Users
export const authApi = {
  getUsers: () => api.get('/auth/users'),
  createUser: (data: Record<string, unknown>) => api.post('/auth/users', data),
  updateUser: (id: number, data: Record<string, unknown>) => api.put(`/auth/users/${id}`, data),
  deleteUser: (id: number) => api.delete(`/auth/users/${id}`),
};

// Exports
export const exportApi = {
  triggerInvoiceExport: (year: number, month: number) =>
    api.post('/exports/invoices', null, { params: { year, month } }),

  listInvoiceExports: () =>
    api.get('/exports/invoices'),

  getInvoiceExport: (id: number) =>
    api.get(`/exports/invoices/${id}`),

  deleteInvoiceExport: (id: number) =>
    api.delete(`/exports/invoices/${id}`),

  downloadExport: (id: number) =>
    api.get(`/exports/invoices/${id}/download`, { responseType: 'blob' }),
};

// Expenses
export const expensesApi = {
  listReports: (params?: { employee_id?: number; status?: string }) =>
    api.get<ExpenseReport[]>('/expenses/reports', { params }),

  getReport: (id: number) =>
    api.get<ExpenseReport>(`/expenses/reports/${id}`),

  createReport: (employeeId: number | undefined, data: { title: string; description?: string; notes?: string }) =>
    api.post<ExpenseReport>('/expenses/reports', data, {
      params: employeeId ? { employee_id: employeeId } : {},
    }),

  updateReport: (id: number, data: { title?: string; description?: string; notes?: string }) =>
    api.patch<ExpenseReport>(`/expenses/reports/${id}`, data),

  deleteReport: (id: number) =>
    api.delete(`/expenses/reports/${id}`),

  submitReport: (id: number) =>
    api.post<ExpenseReport>(`/expenses/reports/${id}/submit`),

  approveReport: (id: number) =>
    api.post<ExpenseReport>(`/expenses/reports/${id}/approve`),

  rejectReport: (id: number, notes?: string) =>
    api.post<ExpenseReport>(`/expenses/reports/${id}/reject`, null, { params: { notes } }),

  reviseReport: (id: number) =>
    api.post<ExpenseReport>(`/expenses/reports/${id}/revise`),
  payReport: (id: number, bankTransactionId: number) =>
    api.post<ExpenseReport>(`/expenses/reports/${id}/pay`, { bank_transaction_id: bankTransactionId }),

  parseInvoice: (file: File, reportId?: number) => {
    const fd = new FormData()
    fd.append('file', file)
    if (reportId) fd.append('report_id', String(reportId))
    return api.post<{ file_path: string; original_filename: string; qr_data: Record<string, unknown> | null; extraction_method: string | null }>(
      '/expenses/parse-invoice', fd, { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },

  addItem: (reportId: number, formData: FormData) =>
    api.post(`/expenses/reports/${reportId}/items`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  deleteItem: (itemId: number) =>
    api.delete(`/expenses/items/${itemId}`),

  updateItem: (itemId: number, formData: FormData) =>
    api.patch(`/expenses/items/${itemId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  fetchItemBlob: (itemId: number) =>
    api.get(`/expenses/items/${itemId}/file`, { responseType: 'blob' }),

  itemFileUrl: (itemId: number) =>
    `/api/v1/expenses/items/${itemId}/file`,
};

export const processesApi = {
  getAvailable: (year: number, month: number) =>
    api.get('/processes/month-end/available', { params: { year, month } }),

  createReport: (data: { year: number; month: number; saft_import_id: number; bank_statement_id: number }) =>
    api.post('/processes/month-end/reports', data),

  listReports: () =>
    api.get('/processes/month-end/reports'),

  getReport: (id: number) =>
    api.get(`/processes/month-end/reports/${id}`),

  deleteReport: (id: number) =>
    api.delete(`/processes/month-end/reports/${id}`),
};
