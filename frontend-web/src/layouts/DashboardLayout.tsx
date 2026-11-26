import React, { useState } from 'react';
import { Box, Drawer, AppBar, Toolbar, List, ListItem, ListItemIcon, ListItemText, IconButton, useMediaQuery, useTheme } from '@mui/material';
import { Menu as MenuIcon, ChevronLeft as ChevronLeftIcon, Home, BarChart, Table, Map, Users } from '@mui/icons-material';
import { styled } from '@mui/system';
import { Link as RouterLink, useLocation } from 'react-router-dom';

const drawerWidth = 280;

const AppBarStyled = styled(AppBar)(({ theme }) => ({
  backgroundColor: '#FFFFFF',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  height: 72,
  zIndex: theme.zIndex.drawer + 1,
  [theme.breakpoints.down('sm')]: {
    height: 56,
  },
}));

const DrawerStyled = styled(Drawer)(({ theme }) => ({
  width: drawerWidth,
  flexShrink: 0,
  '& .MuiDrawer-paper': {
    width: drawerWidth,
    backgroundColor: '#FFFFFF',
    borderRight: '1px solid #E2E8F0',
    marginTop: 72,
    [theme.breakpoints.down('sm')]: {
      marginTop: 56,
      width: '100%',
    },
  },
}));

const MainContent = styled(Box)(({ theme }) => ({
  flexGrow: 1,
  p: 3,
  [theme.breakpoints.down('sm')]: {
    p: 2,
  },
  [theme.breakpoints.up('xl')]: {
    maxWidth: '1600px',
    margin: '0 auto',
  },
}));

interface DashboardLayoutProps {
  children: React.ReactNode;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: '1px solid #E2E8F0' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 32,
              height: 32,
              backgroundColor: theme.palette.primary.main,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 700 }}>IQ</Typography>
          </Box>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary' }}>
              PulseIQ Analytics
            </Typography>
            <Typography variant="caption" color="textSecondary">
              E-Commerce Customer Behavior
            </Typography>
          </Box>
        </Box>
      </Box>

      <List sx={{ flexGrow: 1, p: 0 }}>
        {[
          { text: 'Dashboard', path: '/dashboard', icon: Home },
          { text: 'Product Analysis', path: '/products', icon: BarChart },
          { text: 'Customer Data', path: '/customers', icon: Users },
          { text: 'RFM Insights', path: '/rfm', icon: Table },
        ].map((item) => (
          <ListItem
            key={item.text}
            disablePadding
            sx={{
              '&.Mui-selected': {
                backgroundColor: theme.palette.primary.light,
                '&:hover': { backgroundColor: theme.palette.primary.lighter },
              },
            }}
          >
            <ListItemButton
              component={RouterLink}
              to={item.path}
              selected={location.pathname === item.path}
              sx={{
                py: 2,
                px: 3,
                '&:hover': { backgroundColor: '#E3F2FD' },
              }}
            >
              <ListItemIcon sx={{ minWidth: 24, color: location.pathname === item.path ? theme.palette.primary.main : theme.palette.text.secondary }}>
                <item.icon />
              </ListItemIcon>
              <ListItemText
                primary={item.text}
                primaryTypographyProps={{
                  fontWeight: location.pathname === item.path ? 600 : 500,
                  color: location.pathname === item.path ? 'text.primary' : 'text.secondary',
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Box sx={{ p: 2, borderTop: '1px solid #E2E8F0' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              backgroundColor: '#F1F5F9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="body2" sx={{ color: '#64748B' }}>Y</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>Yash</Typography>
            <Typography variant="caption" color="textSecondary">Administrator</Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: theme.palette.background.default }}>
      <AppBarStyled position="fixed">
        <Toolbar sx={{ justifyContent: 'space-between', px: isMobile ? 1 : 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              color="inherit"
      			  onClick={handleDrawerToggle}
              edge="start"
              sx={{ mr: 2, display: isMobile ? 'block' : 'none' }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
              Analytics Dashboard
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton color="inherit" sx={{ color: theme.palette.text.secondary }}>
              <Notifications sx={{ fontSize: 20 }} />
            </IconButton>
            <IconButton color="inherit" sx={{ color: theme.palette.text.secondary }}>
              <Settings sx={{ fontSize: 20 }} />
            </IconButton>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                backgroundColor: theme.palette.primary.main,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 600 }}>Y</Typography>
            </Box>
          </Box>
        </Toolbar>
      </AppBarStyled>

      <DrawerStyled
        variant={isMobile ? 'temporary' : 'permanent'}
        anchor="left"
        open={isMobile ? mobileOpen : true}
        onClose={handleDrawerToggle}
      >
        {drawerContent}
      </DrawerStyled>

      <MainContent component="main">
        {children}
      </MainContent>
    </Box>
  );
};

export default DashboardLayout;