# Backend API Endpoints

All endpoints are served by the backend on port `8000`. The base path for all API routes is `/api/v1`.

## Role Hierarchy

| Role | Access |
|------|--------|
| `admin` | Full access everywhere |
| `admin_or_finance` | Import/upload routes + some bank mutations |
| `staff` (admin/accounting/finance) | Most read/write routes; blocks the `user` role |
| `user` | Expense self-service only |

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | None | Welcome message |
| `GET` | `/health` | None | Health check |

---

## Authentication — `/api/v1/auth`

`POST /login` is public. All other routes require a valid Bearer token. User-management routes require the `admin` role.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | None | Authenticate with username/password → JWT |
| `GET` | `/api/v1/auth/me` | Authenticated | Get current user info |
| `PUT` | `/api/v1/auth/me/password` | Authenticated | Change own password |
| `GET` | `/api/v1/auth/users` | admin | List all users |
| `POST` | `/api/v1/auth/users` | admin | Create a new user |
| `GET` | `/api/v1/auth/users/{user_id}` | admin | Get user by ID |
| `PUT` | `/api/v1/auth/users/{user_id}` | admin | Update user |
| `DELETE` | `/api/v1/auth/users/{user_id}` | admin | Delete user |

---

## Companies — `/api/v1/companies`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/companies/` | staff | List companies (filter by `is_customer`, `is_supplier`) |
| `GET` | `/api/v1/companies/{company_id}` | staff | Get company by ID |
| `GET` | `/api/v1/companies/nif/{nif}` | staff | Look up company by NIF |
| `POST` | `/api/v1/companies/` | staff | Create company |
| `PATCH` | `/api/v1/companies/{company_id}` | staff | Update company |
| `DELETE` | `/api/v1/companies/{company_id}` | staff | Delete company |
| `POST` | `/api/v1/companies/enrich` | staff | Batch-enrich companies via NIF.PT API |
| `GET` | `/api/v1/companies/enrich/status` | staff | Count companies needing enrichment |

---

## Invoices — `/api/v1/invoices`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/invoices/count` | staff | Count invoices (filter by type/status) |
| `GET` | `/api/v1/invoices/` | staff | List invoices (filter by type, status, date range) |
| `POST` | `/api/v1/invoices/` | staff | Create invoice with line items |
| `GET` | `/api/v1/invoices/{invoice_id}` | staff | Get invoice (incl. reconciliation info) |
| `PATCH` | `/api/v1/invoices/{invoice_id}` | staff | Update invoice |
| `DELETE` | `/api/v1/invoices/{invoice_id}` | staff | Delete invoice |
| `GET` | `/api/v1/invoices/{invoice_id}/file-url` | staff | Get presigned URL for invoice file |
| `POST` | `/api/v1/invoices/{invoice_id}/attach-file` | staff | Attach PDF/image file to invoice |
| `GET` | `/api/v1/invoices/{invoice_id}/payments` | staff | List direct payments for invoice |
| `POST` | `/api/v1/invoices/{invoice_id}/payments` | staff | Add direct payment (cash/employee/bank) |
| `DELETE` | `/api/v1/invoices/{invoice_id}/payments/{payment_id}` | staff | Remove direct payment |
| `GET` | `/api/v1/invoices/{invoice_id}/comments` | staff | List comments |
| `POST` | `/api/v1/invoices/{invoice_id}/comments` | Authenticated | Add comment |
| `PATCH` | `/api/v1/invoices/{invoice_id}/comments/{comment_id}` | Authenticated (own) | Edit own comment |
| `DELETE` | `/api/v1/invoices/{invoice_id}/comments/{comment_id}` | Authenticated (own) | Delete own comment within 1 h |

---

## Payments — `/api/v1/payments`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/payments` | staff | List all payments |
| `GET` | `/api/v1/payments/{payment_id}` | staff | Get payment by ID |
| `GET` | `/api/v1/payments/customer/{customer_id}` | staff | List payments for a customer |

---

## Bank — `/api/v1/bank`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/bank/accounts` | staff | List bank accounts |
| `GET` | `/api/v1/bank/accounts/{account_id}` | staff | Get bank account |
| `PATCH` | `/api/v1/bank/accounts/{account_id}` | admin_or_finance | Update bank account |
| `GET` | `/api/v1/bank/logos` | staff | List bank logos |
| `POST` | `/api/v1/bank/logos` | admin | Create bank logo |
| `DELETE` | `/api/v1/bank/logos/{logo_id}` | admin | Delete bank logo |
| `POST` | `/api/v1/bank/import` | admin_or_finance | Import bank statement (CSV/XLSX) |
| `GET` | `/api/v1/bank/statements` | admin_or_finance | List bank statements |
| `GET` | `/api/v1/bank/statements/{statement_id}` | admin_or_finance | Get statement with transactions |
| `DELETE` | `/api/v1/bank/statements/{statement_id}` | admin | Delete statement |
| `POST` | `/api/v1/bank/statements/{statement_id}/reconcile` | staff | Auto-reconcile all transactions in statement |
| `GET` | `/api/v1/bank/transactions` | staff | List transactions (filter by account, date, category) |
| `GET` | `/api/v1/bank/transactions/{transaction_id}` | staff | Get transaction |
| `PATCH` | `/api/v1/bank/transactions/{transaction_id}/reconcile` | staff | Mark transaction reconciled with invoice/payment |
| `DELETE` | `/api/v1/bank/transactions/{transaction_id}/reconcile` | staff | Unreconcile transaction |
| `GET` | `/api/v1/bank/transactions/{transaction_id}/suggestions` | staff | Get suggested invoices for reconciliation |
| `POST` | `/api/v1/bank/transactions/{transaction_id}/reconcile-manual` | staff | Manually reconcile with a specific invoice |
| `POST` | `/api/v1/bank/transactions/{transaction_id}/link-transfer` | admin_or_finance | Link two transactions as inter-account transfer |
| `DELETE` | `/api/v1/bank/transactions/{transaction_id}/link-transfer` | admin_or_finance | Unlink inter-account transfer |
| `GET` | `/api/v1/bank/transactions/{transaction_id}/notes` | staff | List transaction notes |
| `POST` | `/api/v1/bank/transactions/{transaction_id}/notes` | Authenticated | Add note to transaction |
| `PATCH` | `/api/v1/bank/transactions/{transaction_id}/notes/{note_id}` | Authenticated (own) | Edit own note |
| `DELETE` | `/api/v1/bank/transactions/{transaction_id}/notes/{note_id}` | Authenticated (own) | Delete own note within 1 h |

---

## HR — `/api/v1/hr`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/hr/benefit-types` | staff | List benefit types |
| `POST` | `/api/v1/hr/benefit-types` | staff | Create benefit type |
| `PATCH` | `/api/v1/hr/benefit-types/{type_id}` | staff | Update benefit type |
| `GET` | `/api/v1/hr/employees` | staff | List employees |
| `GET` | `/api/v1/hr/employees/{employee_id}` | staff | Get employee |
| `POST` | `/api/v1/hr/employees` | staff | Create employee |
| `PATCH` | `/api/v1/hr/employees/{employee_id}` | staff | Update employee profile |
| `DELETE` | `/api/v1/hr/employees/{employee_id}` | staff | Soft-delete employee (sets inactive) |
| `GET` | `/api/v1/hr/employees/{employee_id}/compensations` | staff | List compensations for employee |
| `POST` | `/api/v1/hr/employees/{employee_id}/compensations` | staff | Add compensation/benefit |
| `PATCH` | `/api/v1/hr/compensations/{compensation_id}` | staff | Update compensation |
| `DELETE` | `/api/v1/hr/compensations/{compensation_id}` | staff | Delete compensation |
| `GET` | `/api/v1/hr/payroll/periods` | staff | List payroll periods |
| `GET` | `/api/v1/hr/payroll/periods/{period_id}` | staff | Get payroll period |
| `POST` | `/api/v1/hr/payroll/periods` | staff | Create payroll period |
| `PATCH` | `/api/v1/hr/payroll/periods/{period_id}` | staff | Update payroll period |
| `POST` | `/api/v1/hr/payroll/periods/{period_id}/process` | staff | Auto-process payroll |
| `POST` | `/api/v1/hr/payroll/periods/{period_id}/upload` | staff | Upload CSV to update net amounts |
| `GET` | `/api/v1/hr/payroll/entries` | staff | List payroll entries (filter by period/employee) |
| `PATCH` | `/api/v1/hr/payroll/entries/{entry_id}` | staff | Update payroll entry |

---

## Settings — `/api/v1/settings`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/settings` | staff | Get app settings |
| `POST` | `/api/v1/settings` | staff | Update app settings |

---

## Exports — `/api/v1/exports`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/exports/invoices` | staff | Trigger background ZIP export for a year/month |
| `GET` | `/api/v1/exports/invoices` | staff | List all export jobs |
| `GET` | `/api/v1/exports/invoices/{export_id}` | staff | Poll export status |
| `DELETE` | `/api/v1/exports/invoices/{export_id}` | staff | Delete export record and ZIP file |
| `GET` | `/api/v1/exports/invoices/{export_id}/download` | staff | Download the ZIP |

---

## Month-End Processes — `/api/v1/processes`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/processes/month-end/available` | staff | List available SAF-T files and bank statements for a month |
| `POST` | `/api/v1/processes/month-end/reports` | staff | Generate month-end report |
| `GET` | `/api/v1/processes/month-end/reports` | staff | List all month-end reports |
| `GET` | `/api/v1/processes/month-end/reports/{report_id}` | staff | Get month-end report |
| `DELETE` | `/api/v1/processes/month-end/reports/{report_id}` | staff | Delete report and invoice ZIP |

---

## Upload — `/api/v1/upload`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/upload/invoice` | admin_or_finance | Upload invoice file (PDF/image); extracts QR code data |
| `POST` | `/api/v1/upload/invoice/process` | admin_or_finance | Process uploaded file → create invoice and company records |

---

## Invoice Queue — `/api/v1/queue`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/queue/upload-bulk` | admin_or_finance | Bulk upload invoice files to processing queue |
| `GET` | `/api/v1/queue/` | admin_or_finance | List queue items (filter by status) |
| `GET` | `/api/v1/queue/{queue_id}` | admin_or_finance | Get queue item |
| `PUT` | `/api/v1/queue/{queue_id}` | admin_or_finance | Update queue item QR data (manual entry) |
| `POST` | `/api/v1/queue/{queue_id}/process` | admin_or_finance | Process queue item → creates invoice and company records |
| `GET` | `/api/v1/queue/{queue_id}/file-url` | admin_or_finance | Get URL for queue item file |
| `DELETE` | `/api/v1/queue/{queue_id}` | admin_or_finance | Delete queue item |

---

## SAF-T — `/api/v1/saft`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/saft/import` | admin_or_finance | Import SAF-T PT XML (imports companies, sales invoices, payments) |
| `GET` | `/api/v1/saft/imports` | admin_or_finance | List SAF-T import records |
| `GET` | `/api/v1/saft/imports/{import_id}` | admin_or_finance | Get SAF-T import record |

---

## Expenses — `/api/v1/expenses`

`user` role sees only their own data and is blocked from approve/reject/pay actions.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/expenses/reports` | Authenticated | List expense reports |
| `POST` | `/api/v1/expenses/reports` | Authenticated | Create expense report |
| `GET` | `/api/v1/expenses/reports/{report_id}` | Authenticated | Get expense report |
| `PATCH` | `/api/v1/expenses/reports/{report_id}` | Authenticated | Edit report (draft only) |
| `DELETE` | `/api/v1/expenses/reports/{report_id}` | Authenticated | Delete report (draft only) |
| `POST` | `/api/v1/expenses/reports/{report_id}/submit` | Authenticated | Submit report for approval |
| `POST` | `/api/v1/expenses/reports/{report_id}/approve` | staff | Approve report |
| `POST` | `/api/v1/expenses/reports/{report_id}/reject` | staff | Reject report |
| `POST` | `/api/v1/expenses/reports/{report_id}/revise` | Authenticated | Move rejected report back to draft |
| `POST` | `/api/v1/expenses/reports/{report_id}/pay` | staff | Mark approved report as paid + link bank transaction |
| `POST` | `/api/v1/expenses/parse-invoice` | Authenticated | Upload receipt, extract QR data |
| `POST` | `/api/v1/expenses/reports/{report_id}/items` | Authenticated | Add expense item (with file/QR) |
| `PATCH` | `/api/v1/expenses/items/{item_id}` | Authenticated | Update expense item |
| `DELETE` | `/api/v1/expenses/items/{item_id}` | Authenticated | Delete expense item (draft only) |
| `GET` | `/api/v1/expenses/items/{item_id}/file` | Authenticated | Download receipt file |
