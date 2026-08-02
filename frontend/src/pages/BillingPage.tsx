import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
  Box, Card, Grid, Typography, Button, Chip, Stack, Alert,
  LinearProgress, List, ListItem, ListItemIcon, ListItemText,
} from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import { api } from "../api";
import type { CurrentUser, Plan, Usage } from "../types";
import { SkeletonLines } from "../components/Skeleton";

export default function BillingPage() {
  const { user } = useOutletContext<{ user: CurrentUser }>();
  const isAdmin = user.role === "admin";

  const [usage, setUsage] = useState<Usage | null>(null);
  const [planList, setPlanList] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api("/billing/usage").then((r) => (r.ok ? r.json() : null)),
      api("/billing/plans").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([u, p]) => {
        setUsage(u as Usage | null);
        setPlanList(p as Plan[]);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Card variant="outlined" sx={{ p: 3 }}><SkeletonLines count={5} /></Card>;
  }

  const used = usage?.invoices_used ?? 0;
  const limit = usage?.invoice_limit ?? null;
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>Billing</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Your plan and this month's usage.
      </Typography>

      {usage?.limit_reached && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          You've reached your monthly invoice limit. Upgrade to Pro to keep processing invoices.
        </Alert>
      )}

      {/* Current plan + usage meter */}
      <Card variant="outlined" sx={{ p: 3, mb: 3, maxWidth: 720 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Current plan</Typography>
          <Chip size="small" color={usage?.plan === "pro" ? "primary" : "default"}
            label={usage?.plan_name ?? "Free"} />
          {usage?.subscription_status && (
            <Chip size="small" variant="outlined" label={usage.subscription_status} />
          )}
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
          Invoices this month
        </Typography>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
          {used}{limit !== null ? ` / ${limit}` : " (unlimited)"}
        </Typography>
        {limit !== null && (
          <LinearProgress variant="determinate" value={pct}
            color={usage?.limit_reached ? "error" : "primary"}
            sx={{ height: 8, borderRadius: 4, mb: 1 }} />
        )}
        <Typography variant="caption" color="text.secondary">
          {limit === null
            ? "Unlimited invoice processing"
            : `${usage?.invoices_remaining ?? 0} remaining this month`}
        </Typography>
      </Card>

      {/* Plan comparison */}
      <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>Plans</Typography>
      <Grid container spacing={2} sx={{ maxWidth: 720 }}>
        {planList.map((plan) => {
          const isCurrent = plan.key === usage?.plan;
          return (
            <Grid key={plan.key} size={{ xs: 12, sm: 6 }}>
              <Card variant="outlined" sx={{
                p: 3, height: "100%",
                borderColor: isCurrent ? "primary.main" : undefined,
                borderWidth: isCurrent ? 2 : 1,
              }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>{plan.name}</Typography>
                  {isCurrent && <Chip size="small" color="primary" label="Current" />}
                </Stack>
                <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
                  ${plan.price_monthly}
                  <Typography component="span" variant="body2" color="text.secondary">/mo</Typography>
                </Typography>

                <List dense disablePadding sx={{ mb: 2 }}>
                  {plan.features.map((f) => (
                    <ListItem key={f} disableGutters sx={{ py: 0.25 }}>
                      <ListItemIcon sx={{ minWidth: 28 }}>
                        <CheckCircleRoundedIcon fontSize="small" color="primary" />
                      </ListItemIcon>
                      <ListItemText primary={f} slotProps={{ primary: { sx: { fontSize: 14 } } }} />
                    </ListItem>
                  ))}
                </List>

                {isCurrent ? (
                  <Button fullWidth disabled variant="outlined">Your current plan</Button>
                ) : plan.price_monthly > 0 ? (
                  <Button fullWidth variant="contained" disabled={!isAdmin}>
                    {isAdmin ? "Upgrade to Pro" : "Admins only"}
                  </Button>
                ) : (
                  <Button fullWidth variant="outlined" disabled>Downgrade</Button>
                )}
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {!isAdmin && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
          Only workspace admins can change the plan.
        </Typography>
      )}
    </Box>
  );
}
