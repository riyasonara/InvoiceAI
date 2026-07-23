import { useEffect, useMemo, useState } from "react";
import {
  Box, Card, Typography, TextField,
  Table, TableBody, TableCell, TableHead, TableRow,
} from "@mui/material";
import { api, formatMoney, formatDate } from "../api";
import type { Invoice } from "../types";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

interface Supplier {
  name: string;
  count: number;
  total: number;
  last: string;
}

export default function SuppliersPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api("/invoices")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setInvoices((d as Invoice[]) || []))
      .finally(() => setLoading(false));
  }, []);

  // Group invoices by supplier → count, total spend, most recent invoice.
  const suppliers = useMemo<Supplier[]>(() => {
    const map = new Map<string, Supplier>();
    for (const inv of invoices) {
      const name = inv.vendor || "Unknown";
      const s = map.get(name) || { name, count: 0, total: 0, last: "" };
      s.count += 1;
      s.total += Number(inv.total) || 0;
      if (String(inv.invoice_date || "") > s.last) s.last = inv.invoice_date || "";
      map.set(name, s);
    }
    return [...map.values()].sort((a, b) => b.total - a.total);
  }, [invoices]);

  const filtered = suppliers.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>Suppliers</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Every supplier across your workspace, ranked by total spend.
      </Typography>

      <TextField size="small" type="search" placeholder="Search suppliers…"
        value={search} onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2, width: "100%", maxWidth: 320 }} />

      <Card variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
        {loading ? (
          <SkeletonLines count={6} />
        ) : filtered.length === 0 ? (
          <EmptyState icon="🏢" title="No suppliers yet"
            message="Suppliers appear here once you upload invoices." />
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Supplier</TableCell><TableCell>Invoices</TableCell>
                  <TableCell>Total Spend</TableCell><TableCell>Latest Invoice</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.map((s) => (
                  <TableRow key={s.name} hover>
                    <TableCell sx={{ fontWeight: 600 }}>{s.name}</TableCell>
                    <TableCell>{s.count}</TableCell>
                    <TableCell>{formatMoney(s.total)}</TableCell>
                    <TableCell>{formatDate(s.last)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Card>
    </Box>
  );
}
