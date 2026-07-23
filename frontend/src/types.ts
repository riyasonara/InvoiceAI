// Shared domain types — mirror the FastAPI response shapes.

export interface Organization {
  id: number;
  name: string;
  invite_code: string;
}

// What /me and /login return (user + their organization).
export interface CurrentUser {
  id: number;
  email: string;
  organization: Organization;
}

export type InvoiceStatus = "paid" | "pending" | "unpaid";

export interface Invoice {
  id: number;
  vendor: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  gst: number | null;
  total: number | null;
  status: InvoiceStatus;
  due_date: string | null;
  created_at: string | null;
}

export interface MonthlyPoint {
  month: string;
  count: number;
  amount: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface SupplierSpend {
  vendor: string;
  count: number;
  amount: number;
}

export interface EmailStats {
  synced_today: number;
  imported: number;
  errors: number;
  pending: number;
}

export interface DashboardSummary {
  total_invoices: number;
  total_suppliers: number;
  total_amount: number;
  paid_amount: number;
  pending_amount: number;
  unpaid_amount: number;
  unpaid_count: number;
  monthly_trend: MonthlyPoint[];
  status_distribution: StatusCount[];
  top_suppliers: SupplierSpend[];
  email_stats?: EmailStats;
}

export type AttachmentStatus = "pending" | "processing" | "completed" | "failed";

export interface EmailAttachment {
  id: number;
  filename: string | null;
  mime_type: string | null;
  status: AttachmentStatus;
  invoice_id: number | null;
}

export interface EmailMessage {
  id: number;
  sender: string | null;
  subject: string | null;
  received_at: string | null;
  created_at: string | null;
  attachments: EmailAttachment[];
}

export interface SyncResult {
  scanned: number;
  new_messages: number;
  new_attachments: number;
}

export interface ProcessResult {
  processed: number;
  completed: number;
  failed: number;
}
