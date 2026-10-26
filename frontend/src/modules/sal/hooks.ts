import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";

/** Shapes match backend/app/modules/sal/schemas.py. Decimals arrive as strings. */
export type SalesStatus = "draft" | "confirmed" | "partially_delivered" | "delivered" | "cancelled";

export interface SalesOrderLine {
  id: string;
  material_item_id: string;
  quantity: string;
  unit_price: string;
  delivered_quantity: string;
  invoiced_quantity: string;
}

export interface DeliveryNote {
  id: string;
  number: string;
  delivered_at: string;
  lines: { order_line_id: string; material_item_id: string; quantity: string; valued_cost: string }[];
}

export interface SalesInvoice {
  id: string;
  number: string;
  order_id: string;
  invoice_date: string;
  due_date: string | null;
  net_amount: string;
  vat_amount: string;
  amount: string;
}

export interface SalesOrder {
  id: string;
  number: string;
  client_id: string;
  warehouse_id: string;
  status: SalesStatus;
  order_date: string;
  delivery_date: string | null;
  vat_percent: string;
  subtotal: string;
  vat_amount: string;
  total: string;
  lines: SalesOrderLine[];
  deliveries: DeliveryNote[];
  invoices: SalesInvoice[];
  delivered_value: string;
  delivered_cost: string;
  gross_margin: string;
}

export interface SalesSettings {
  company_id: string;
  receivable_account_id: string;
  revenue_account_id: string;
  vat_account_id: string | null;
  vat_percent: string;
  payment_terms_days: number;
}

export function useSalesOrders() {
  return useQuery({
    queryKey: ["sal", "orders"],
    queryFn: async (): Promise<SalesOrder[]> => (await apiClient.get("/sal/sales-orders")).data.data,
  });
}

export function useSalesInvoices() {
  return useQuery({
    queryKey: ["sal", "invoices"],
    queryFn: async (): Promise<SalesInvoice[]> => (await apiClient.get("/sal/invoices")).data.data,
  });
}

export function useSalesSettings() {
  return useQuery({
    queryKey: ["sal", "settings"],
    queryFn: async (): Promise<SalesSettings | null> => (await apiClient.get("/sal/settings")).data.data,
  });
}

export function useSaveSalesSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      company_id: string;
      receivable_account_id: string;
      revenue_account_id: string;
      vat_account_id: string | null;
      vat_percent: string;
      payment_terms_days: number;
    }) => apiClient.put("/sal/settings", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sal", "settings"] }),
  });
}

export function useCreateSalesOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      client_id: string;
      warehouse_id: string;
      lines: { material_item_id: string; quantity: string; unit_price: string | null }[];
    }) => apiClient.post("/sal/sales-orders", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sal"] }),
  });
}

export function useSalesOrderAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "confirm" | "cancel" | "invoice" }) =>
      apiClient.post(`/sal/sales-orders/${id}/${action}`),
    // Invoicing posts to the ledger, so finance views are stale too.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sal"] });
      qc.invalidateQueries({ queryKey: ["fin"] });
    },
  });
}

export function useDeliver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, lines }: { id: string; lines: { order_line_id: string; quantity: string }[] }) =>
      apiClient.post(`/sal/sales-orders/${id}/deliveries`, { lines }),
    // Delivering takes stock out of the warehouse.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sal"] });
      qc.invalidateQueries({ queryKey: ["inv"] });
    },
  });
}
