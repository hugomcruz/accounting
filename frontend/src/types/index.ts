export interface Company {
  id: number;
  nif: string;
  name: string;
  address?: string;
  postal_code?: string;
  city?: string;
  country: string;
  email?: string;
  phone?: string;
  is_customer: boolean;
  is_supplier: boolean;
  created_at: string;
  updated_at: string;
}

export interface InvoiceLineItem {
  id?: number;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  line_total: number;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  invoice_type: 'sale' | 'purchase';
  status: 'draft' | 'issued' | 'paid' | 'cancelled';
  invoice_date: string;
  due_date?: string;
  customer_id?: number;
  supplier_id?: number;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  tax_rate: number;
  file_path?: string;
  qr_code_data?: string;
  atcud?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  line_items?: InvoiceLineItem[];
  // Foreign currency fields
  is_foreign_currency?: boolean;
  foreign_currency_code?: string;
  original_total_amount?: number;
  original_tax_amount?: number;
  exchange_rate?: number;
  // VAT breakdown
  vat_6_base?: number;
  vat_6_amount?: number;
  vat_23_base?: number;
  vat_23_amount?: number;
  supplier_name?: string;
  customer_name?: string;
  is_reconciled?: boolean;
  bank_transaction_id?: number | null;
  linked_transaction_ids?: number[];
  reconciled_amount?: number;
  is_partial?: boolean;
  payments?: InvoiceDirectPayment[];
  total_paid?: number;
  remaining_amount?: number;
}

export interface InvoiceDirectPayment {
  id: number;
  invoice_id: number;
  payment_date: string;
  amount: number;
  payment_type: 'cash' | 'employee' | 'company_account' | 'other';
  reference?: string;
  employee_id?: number;
  employee_name?: string;
  bank_transaction_id?: number | null;
  notes?: string;
  created_at: string;
}

export interface ExpenseItem {
  id: number;
  report_id: number;
  description: string;
  category?: string;
  amount: number;
  currency: string;
  eur_amount?: number | null;
  exchange_rate?: number | null;
  expense_date: string;
  file_path: string;
  original_filename?: string;
  notes?: string;
  created_at: string;
  invoice_id?: number | null;
}

export interface ExpenseReport {
  id: number;
  expense_id?: string;
  employee_id: number;
  employee_name?: string;
  title: string;
  description?: string;
  status: 'draft' | 'submitted' | 'approved' | 'rejected' | 'paid';
  submitted_at?: string;
  approved_at?: string;
  paid_at?: string;
  bank_transaction_id?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  items: ExpenseItem[];
  total_amount: number;
}

export interface InvoiceProcessingQueue {
  id: number;
  filename: string;
  local_file_path?: string;
  s3_file_path?: string;
  status: string;
  error_message?: string;
  has_qr_data: boolean;
  qr_data?: string;
  invoice_id?: number;
  uploaded_at: string;
  processed_at?: string;
  retry_count: number;
  last_retry_at?: string;
}

export interface QRCodeData {
  nif_emitente: string;
  nif_adquirente: string;
  pais_adquirente: string;
  tipo_documento: string;
  estado_documento: string;
  data_documento: string;
  identificacao_documento: string;
  atcud: string;
  espaco_fiscal: string;
  base_incidencia_iva?: number[];
  total_iva?: number[];
  total_impostos: number;
  total_documento: number;
  hash: string;
  certificado: string;
  outras_infos?: string;
}

export interface UploadResponse {
  filename: string;
  file_path: string;
  qr_data?: QRCodeData;
  message: string;
}

export interface SAFTImport {
  id: number;
  filename: string;
  tax_registration_number?: string;
  company_name?: string;
  fiscal_year?: number;
  start_date?: string;
  end_date?: string;
  total_invoices: number;
  imported_invoices: number;
  failed_invoices: number;
  status: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}
