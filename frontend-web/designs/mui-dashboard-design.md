# Material-UI Dashboard Design Specification

## Overview
Modern enterprise e-commerce analytics dashboard with Material-UI v5, React, TypeScript. Replaces current Tailwind implementation with professional Material-UI components while maintaining all existing functionality.

## Color Palette
- **Primary**: #1976D2 (Blue 700) - Main navigation, primary buttons, headers
- **Secondary**: #2196F3 (Blue 600) - Accent elements, hover states, chart lines
- **Accent**: #FF9800 (Orange 500) - Highlight metrics, warnings, interactive elements
- **Surface**: #FFFFFF - Cards, backgrounds
- **Background**: #F8FAFC - Main canvas
- **Text Primary**: #0F172A - Dark gray for readability
- **Text Secondary**: #64748B - Lighter gray for labels, descriptions

## Typography
- **Headings**: Roboto Slab, weight 700, size 24-32px
- **Subheadings**: Roboto, weight 600, size 16-20px
- **Body**: Roboto, weight 400, size 14px
- **Labels**: Roboto, weight 500, size 12px

## Layout Structure

### Header (72px)
- Fixed top bar with sidebar toggle
- Primary brand logo left, user menu right
- Breadcrumb navigation for context
- Search bar with rounded corners

### Sidebar (280px collapsed, 320px expanded)
- Material-UI Drawer with elevation 2
- Collapsible sections with accordion
- Icons: Material-UI icons in primary color
- Footer with app version

### Main Content Area
- Padding: 32px on desktop, 24px on tablet
- Max-width: 1600px centered
- Grid spacing: 24px between sections

## Responsive Breakpoints
- **xs**: < 600px (mobile)
- **sm**: 600-960px (tablet)
- **md**: 960-1280px (small desktop)
- **lg**: 1280-1920px (desktop)
- **xl**: > 1920px (large desktop)

## Component Designs

### 1. Enhanced KPI Cards
```tsx
<Card sx={{ 
  background: 'linear-gradient(135deg, #E3F2FD 0%, #FFFFFF 100%)',
  border: '1px solid #E3F2FD',
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  transition: 'transform 0.2s ease, box-shadow 0.2s ease'
}}>
  <CardContent sx={{ p: 3 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
      <Icon sx={{ color: '#1976D2', mr: 1, fontSize: 20 }} />
      <Typography variant="overline" color="textSecondary">
        Total Revenue
      </Typography>
    </Box>
    <Typography variant="h3" component="h2" sx={{ fontWeight: 700, mb: 1 }}>
      ₹{value.toLocaleString('en-IN')}
    </Typography>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <TrendingUpIcon sx={{ fontSize: 16, color: '#388E3C' }} />
      <Typography variant="body2" color="success.main">
        12.5% vs last period
      </Typography>
    </Box>
  </CardContent>
</Card>
```
- 5 cards per row on xl, 3 on lg, 2 on md, 1 on sm
- Hover: elevation change, slight scale
- Gradient varies by card type

### 2. Chart Container with Material-UI Wrappers
```tsx
<Card sx={{ 
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  overflow: 'hidden'
}}>
  <CardHeader sx={{ pb: 2 }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Box>
        <Typography variant="h6" component="h3">Product Sales Analysis</Typography>
        <Typography variant="body2" color="textSecondary">Real-time revenue trends</Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button variant="outlined" size="small" color="secondary">Line</Button>
        <Button variant="outlined" size="small" color="secondary">Bar</Button>
        <Button variant="contained" size="small" color="primary">Map</Button>
      </Box>
    </Box>
  </CardHeader>
  
  <CardContent sx={{ p: 0 }}>
    <Box sx={{ position: 'relative', height: 400 }}>
      <Box sx={{ position: 'absolute', inset: 0 }}>
        {/* Chart.js/Plotly container */}
        <Box ref={chartRef} sx={{ width: '100%', height: '100%' }} />
      </Box>
      {/* Country filter dropdown */}
      <FormControl sx={{ position: 'absolute', top: 16, right: 16, minWidth: 160 }}>
        <Select value={country} onChange={handleCountryChange}>
          <MenuItem value="">All Countries</MenuItem>
          {countries.map(c => (
            <MenuItem key={c} value={c}>{c}</MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  </CardContent>
</Card>
```
- Chart area maintains 16:9 aspect ratio
- Controls inside CardHeader with Material-UI buttons
- Dropdowns styled with Material-UI Select

### 3. Styled Data Table
```tsx
<TableContainer component={Paper} sx={{ 
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  maxHeight: 500
}}>
  <Table sx={{ minWidth: 650 }}>
    <TableHead>
      <TableRow>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9' }}>Customer ID</TableCell>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9' }}>RFM Segment</TableCell>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9' }}>K-Means Tier</TableCell>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9' }}>Recency</TableCell>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9', textAlign: 'right' }}>Orders</TableCell>
        <TableCell sx={{ fontWeight: 600, backgroundColor: '#F1F5F9', textAlign: 'right' }}>Spend</TableCell>
      </TableRow>
    </TableHead>
    <TableBody>
      {rows.map(row => (
        <TableRow hover key={row.id} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
          <TableCell>{row.id}</TableCell>
          <TableCell>
            <Chip 
              label={row.segment} 
              color={segmentColor(row.segment)}
              size="small"
              sx={{ fontWeight: 500 }}
            />
          </TableCell>
          <TableCell>{row.tier}</TableCell>
          <TableCell>{row.recency}d</TableCell>
          <TableCell align="right">{row.orders.toLocaleString()}</TableCell>
          <TableCell align="right" sx={{ fontWeight: 600 }}>
            ₹{row.spend.toLocaleString('en-IN')}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
</TableContainer>
```
- Sticky header with background
- Row hover effects with Material-UI transitions
- Chips for segmentation badges
- Right-aligned numeric data

### 4. Interactive Map Integration
```tsx
<Card sx={{ 
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',n  overflow: 'hidden'
}}>
  <CardHeader>
    <Typography variant="h6">Geographic Distribution</Typography>
  </CardHeader>
  <CardContent sx={{ p: 0 }}>
    <Box sx={{ position: 'relative', height: 400 }}>
      {/* Map container */}
      <Box ref={mapRef} sx={{ width: '100%', height: '100%' }} />
      
      {/* Interactive country cards overlay */}
      <Box sx={{ 
        position: 'absolute', 
        bottom: 16, 
        left: 16, 
        right: 16,
        display: 'flex', 
        flexWrap: 'wrap', 
        gap: 1,
        maxHeight: 120,
        overflow: 'auto'
      }}>
        {countries.map(country => (
          <Paper 
            key={country}
            sx={{ 
              p: 1, 
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': { backgroundColor: '#E3F2FD' }
            }}
            onClick={() => drillDown(country)}
          >
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {country}
            </Typography>
            <Typography variant="caption" color="textSecondary">
              ₹{revenue.toLocaleString('en-IN')}
            </Typography>
          </Paper>
        ))}
      </Box>
    </Box>
  </CardContent>
</Card>
```

## Dashboard Layout Mockup

### Desktop (>1280px)
- Header: 72px
- Sidebar: 280px (expanded)
- Main: Grid 12 columns
  - Row 1: 12 cols (5 KPI cards = 5 cols each)
  - Row 2: 12 cols (8 cols chart + 4 cols leaderboard)
  - Row 3: 12 cols (8 cols table + 4 cols inspector)
  - Row 4: 12 cols (RFM matrix)

### Tablet (960-1280px)
- Header: 64px
- Sidebar: collapsed (72px toggle)
- Main: Grid 8 columns
  - Row 1: 8 cols (4 KPI cards)
  - Row 2: 8 cols (6 cols chart + 2 cols leaderboard)
  - Row 3: 8 cols (6 cols table + 2 cols inspector)
  - Row 4: 8 cols (RFM matrix)

### Mobile (<600px)
- Header: 56px
- Sidebar: hidden (bottom navigation)
- Main: Full width
  - Stack sections vertically
  - KPI cards: 1 per row
  - Chart: full width
  - Tables: scroll horizontally

## Implementation Notes
- Use Material-UI v5 with Joy UI components for modern design
- Implement responsive grid using Grid2 component
- Add theme provider with custom palette
- Use React Query for data fetching
- Implement chart switching with Material-UI Tabs
- Add export functionality using csv-exporter library
- Maintain existing API endpoints from backend
- Add loading states and error boundaries

## Files to Create/Modify
- `frontend-web/src/components/KpiCard.tsx`
- `frontend-web/src/components/ChartContainer.tsx`
- `frontend-web/src/components/DataTable.tsx`
- `frontend-web/src/components/InteractiveMap.tsx`
- `frontend-web/src/theme.ts`
- `frontend-web/src/layouts/DashboardLayout.tsx`
- `frontend-web/src/pages/Dashboard.tsx`

This design maintains all current functionality while providing a professional Material-UI interface with the specified color palette and responsive behavior.
