# Material-UI Dashboard Design Mockup

## Overview
A modern enterprise analytics dashboard using Material-UI with clean typography, responsive grid, and professional data visualization. Replaces current Tailwind implementation while preserving all functionality.

## Color Palette
- Primary: #1976D2 (Blue 700) - Main actions, headers
- Secondary: #2196F3 (Blue 500) - Interactive elements, accents
- Surface: #FFFFFF - Cards, backgrounds
- Text Primary: #1E293B - Dark slate for readability
- Text Secondary: #64748B - Supporting text
- Border: #E2E8F0 - Subtle separators
- Error: #F44336 - Validation, warnings
- Success: #4CAF50 - Positive states

## Typography
- Heading 1: Roboto Slab, 32px, 700
- Heading 2: Roboto Slab, 24px, 600
- Heading 3: Roboto Slab, 20px, 500
- Body: Roboto, 14px, 400
- Caption: Roboto, 12px, 400

## Layout Structure

### Header (72px)
- Left: Logo + Navigation
- Right: User profile, notifications, settings
- Fixed position with shadow

### Sidebar (240px)
- Collapsible on mobile
- Dataset selector (primary)
- Quick actions
- Bottom: Help/ docs

### Main Content
- Grid layout with 12-column system
- 20px gutters, 40px row spacing

## Component Designs

### KPI Cards (Row 1)
5 cards in a row on desktop, 2-3 on tablet, 1 on mobile
Each card:
- Gradient background (white to primary/secondary)
- Icon on left
- Metric value with large typography
- Subtext with secondary color
- Hover: elevation change, shadow

### Chart Area (Row 2)
Left: 8 columns
- Card with rounded corners
- Chart container with Material-UI Paper wrapper
- Controls bar above: tabs for chart type, date range picker, country filter
- Search input for products
- Selected products chips
- Chart canvas (Chart.js wrapper)
- Map fallback for geographic data

Right: 4 columns
- Leaderboard card
- Table with sorting
- Click to add to chart

### Customer Table (Row 3)
Full width
- Filter bar above
- Sticky header
- Row hover states
- Click to drill down
- Export button

### RFM Distribution (Row 4)
Full width
- Horizontal scrollable table
- Color-coded segment badges
- Revenue share indicators

## Responsive Breakpoints
- xs: < 600px (mobile)
- sm: 600-960px (tablet)
- md: 960-1280px (small desktop)
- lg: 1280px+ (large desktop)

## Interactive Elements
- All charts responsive to viewport
- Map pins clickable to filter by country
- Product search with dropdown suggestions
- Customer row click opens 360 view
- Export functionality for tables
- Toast notifications for file uploads

## Data Flow
1. User selects dataset from sidebar
2. API calls fetch insights (/api/insights)
3. KPIs update with animated numbers
4. Charts render with selected products
5. Customer table populates with filtered results
6. Click customer to see order history

## Migration Path
1. Create React TypeScript structure
2. Implement Material-UI theme provider
3. Port existing JS logic to React components
4. Replace Chart.js/Plotly with wrappers
5. Add state management (Redux/Zustand)
6. Implement responsive grid system

This design maintains all current features while providing a modern, professional enterprise interface with better accessibility and maintainability.