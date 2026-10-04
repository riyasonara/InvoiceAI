import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  AppBar, Box, Button, Chip, Divider, Drawer, IconButton, Tooltip,
  List, ListItemButton, ListItemIcon, ListItemText, Toolbar, Typography,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import type { Theme } from "@mui/material/styles";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import GridViewRoundedIcon from "@mui/icons-material/GridViewRounded";
import ReceiptLongRoundedIcon from "@mui/icons-material/ReceiptLongRounded";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import BarChartRoundedIcon from "@mui/icons-material/BarChartRounded";
import SettingsRoundedIcon from "@mui/icons-material/SettingsRounded";
import MailRoundedIcon from "@mui/icons-material/MailRounded";
import CreditCardRoundedIcon from "@mui/icons-material/CreditCardRounded";
import Brand from "./Brand";
import ColorModeToggle from "./ColorModeToggle";
import type { CurrentUser } from "../types";
import type { ReactNode } from "react";

const DRAWER_WIDTH = 248;
const COLLAPSED_WIDTH = 76;
const COLLAPSE_KEY = "sidebar-collapsed";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: <GridViewRoundedIcon />, end: true },
  { to: "/invoices", label: "Invoices", icon: <ReceiptLongRoundedIcon /> },
  { to: "/suppliers", label: "Suppliers", icon: <PeopleAltRoundedIcon /> },
  { to: "/reports", label: "Reports", icon: <BarChartRoundedIcon /> },
  { to: "/emails", label: "Emails", icon: <MailRoundedIcon /> },
  { to: "/billing", label: "Billing", icon: <CreditCardRoundedIcon /> },
  { to: "/settings", label: "Settings", icon: <SettingsRoundedIcon /> },
];

interface LayoutProps {
  user: CurrentUser;
  onLogout: () => void | Promise<void>;
}

export default function Layout({ user, onLogout }: LayoutProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  // Desktop collapse state, remembered across visits (per-viewer convenience).
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
  });

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      try { localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
      return next;
    });
  }

  const itemSx = (mini: boolean) => ({
    borderRadius: 2,
    mb: 0.5,
    py: 1,
    px: mini ? 1.5 : 2,
    color: "text.secondary",
    justifyContent: mini ? "center" : "flex-start",
    "&:hover": { bgcolor: "action.hover" },
    "&.active": {
      bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.14),
      color: "primary.main",
      "&:hover": { bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.2) },
    },
  });

  // `mini` collapses the desktop rail to icons only. `desktop` adds the
  // in-sidebar collapse toggle (the mobile drawer closes with the backdrop).
  function drawerContent(mini: boolean, desktop: boolean) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <Toolbar sx={{ px: mini ? 1 : 2, justifyContent: mini ? "center" : "flex-start" }}>
          {desktop ? (
            <Tooltip title={mini ? "Expand sidebar" : "Collapse sidebar"} placement="right" arrow>
              <Box
                onClick={toggleCollapsed}
                role="button"
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                sx={{ cursor: "pointer", display: "inline-flex", borderRadius: 2 }}
              >
                <Brand compact={mini} />
              </Box>
            </Tooltip>
          ) : (
            <Brand compact={mini} />
          )}
        </Toolbar>
        <Divider />

        <List sx={{ px: 1.25, pt: 1.5, flexGrow: 1 }}>
          {NAV.map((item) => (
            <Tooltip key={item.to} title={mini ? item.label : ""} placement="right" arrow>
              <ListItemButton
                component={NavLink}
                to={item.to}
                end={item.end}
                onClick={() => setMobileOpen(false)}
                sx={itemSx(mini)}
              >
                <ListItemIcon sx={{ minWidth: mini ? 0 : 38, color: "inherit", justifyContent: "center" }}>
                  {item.icon}
                </ListItemIcon>
                {!mini && (
                  <ListItemText primary={item.label} slotProps={{ primary: { sx: { fontSize: 14, fontWeight: 600 } } }} />
                )}
              </ListItemButton>
            </Tooltip>
          ))}
        </List>

        {!mini && (
          <>
            <Divider />
            <Box sx={{ p: 1.25 }}>
              <Chip label={user.organization.name} size="small" color="primary" variant="outlined"
                sx={{ maxWidth: "100%" }} />
            </Box>
          </>
        )}
      </Box>
    );
  }

  const desktopWidth = collapsed ? COLLAPSED_WIDTH : DRAWER_WIDTH;

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar
        position="fixed"
        elevation={0}
        color="default"
        sx={{
          bgcolor: "background.paper",
          borderBottom: 1,
          borderColor: "divider",
          width: { md: `calc(100% - ${desktopWidth}px)` },
          ml: { md: `${desktopWidth}px` },
          transition: "width 0.2s ease, margin 0.2s ease",
        }}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setMobileOpen(true)}
            sx={{ mr: 1, display: { md: "none" } }} aria-label="Open menu">
            <MenuRoundedIcon />
          </IconButton>
          <Box sx={{ flexGrow: 1 }} />
          <Typography variant="body2" color="text.secondary"
            sx={{ mr: 2, display: { xs: "none", sm: "block" } }}>
            {user.email}
          </Typography>
          <ColorModeToggle />
          <Button variant="outlined" color="inherit" size="small" onClick={onLogout} sx={{ ml: 1 }}>
            Log out
          </Button>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: desktopWidth }, flexShrink: { md: 0 },
        transition: "width 0.2s ease" }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" },
          }}
        >
          {drawerContent(false, false)}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": {
              width: desktopWidth, boxSizing: "border-box", overflowX: "hidden",
              bgcolor: "background.paper", borderRight: 1, borderColor: "divider",
              transition: "width 0.2s ease",
            },
          }}
        >
          {drawerContent(collapsed, true)}
        </Drawer>
      </Box>

      <Box component="main" sx={{ flexGrow: 1, width: { md: `calc(100% - ${desktopWidth}px)` },
        transition: "width 0.2s ease" }}>
        <Toolbar />
        <Box sx={{ maxWidth: 1200, mx: "auto", p: { xs: 2, md: 4 } }}>
          <Outlet context={{ user }} />
        </Box>
      </Box>
    </Box>
  );
}
