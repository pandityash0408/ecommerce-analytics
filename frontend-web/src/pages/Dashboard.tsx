import React, { useState, useEffect } from 'react';
import { Box, Grid, Card, CardHeader, CardContent, Typography, Select, MenuItem, FormControl, InputLabel, Button } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import KpiCard from '../components/KpiCard';
import ChartContainer from '../components/ChartContainer';
import DataTable from '../components/DataTable';
import { useOutletContext } from 'react-router-dom';

const Dashboard = () => {
  const theme = useTheme();
  const { setTitle } = useOutletContext();
  const [kpiData, setKpiData] = useState({ revenue: 0, customers: 0, orders: 0, avgSpend: 0, repeatRate: 0 });
  const [chartData, setChartData] = useState({ series: [], periods: [], selectedProducts: [] });
  const [customerData, setCustomerData] = useState([]);
  const [chartType, setChartType] = useState('line');
  const [countryFilter, setCountryFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setTitle('Analytics Dashboard');
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const res = await fetch('/api/store-insights', {
        headers: { 'x-api-key': 'key-sample-sales' },
      });
      if (!res.ok) throw new Error('Failed to load data');
      const data = await res.json();
      setKpiData({
        revenue: data.kpis.total_revenue || 0,
        customers: data.kpis.total_customers || 0,
        orders: data.kpis.total_orders || 0,
        avgSpend: data.kpis.avg_spend || 0,
        repeatRate: data.kpis.repeat_rate_pct || 0,
      });
      setCustomerData(data.customer_behavior || []);
      setIsLoading(false);
    } catch (error) {
      console.error('Dashboard load error:', error);
      setIsLoading(false);
    }
  };

  const loadChartData = async () => {
    try {
      const params = new URLSearchParams({
        granularity: 'month',
        country: countryFilter,
        products: chartData.selectedProducts.join(','),
      });
      const res = await fetch(`/api/products/trends?${params.toString()}`, {
        headers: { 'x-api-key': 'key-sample-sales' },
      });
      if (!res.ok) throw new Error('Failed to load chart');
      const data = await res.json();
      setChartData({
        series: data.series || [],
        periods: data.periods || [],
        selectedProducts: data.selected_products || [],
      });
    } catch (error) {
      console.error('Chart load error:', error);
    }
  };

  const handleChartTypeChange = (type: string) => {
    setChartType(type);
    if (type === 'map') {
      setCountryFilter(''); // Reset country filter for map view
    }
    loadChartData();
  };

  const handleCountryChange = (country: string) => {
    setCountryFilter(country);
    loadChartData();
  };

  const kpiCards = [
    {
      title: 'Total Revenue',
      value: kpiData.revenue,
      subtitle: `${kpiData.orders.toLocaleString()} verified orders`,
      trend: 12.5,
      trendDirection: 'up',
      color: 'primary',
    },
    {
      title: 'Total Customers',
      value: kpiData.customers,
      subtitle: `${knpData.repeatRate.toFixed(1)}% repeat buyer rate`,
      trend: 8.3,
      trendDirection: 'up',
      color: 'secondary',
    },
    {
      title: 'Avg Spend / Customer',
      value: kpiData.avgSpend,
      subtitle: 'Mean customer LTV',
      trend: 5.2,
      trendDirection: 'up',
      color: 'accent',
    },
    {
      title: 'Best Customer',
      value: '—',
      subtitle: `${(data.kpis.best_customer?.spend || 0).toLocaleString()} • ${(data.kpis.best_customer?.units || 0).toLocaleString()} units`,
      trend: null,
      color: 'primary',
    },
    {
      title: 'Worst Customer',
      value: '—',
      subtitle: `${(data.kpis.worst_customer?.spend || 0).toLocaleString()} • ${(data.kpis.worst_customer?.units || 0).toLocaleString()} units`,
      trend: null,
      color: 'secondary',
    },
  ];

  const customerColumns = [
    { id: 'CustomerID', label: 'Customer ID', align: 'left' },
    { id: 'Segment', label: 'RFM Segment', align: 'left' },
    { id: 'KMeans_ML_Cluster', label: 'K-Means Tier', align: 'left' },
    { id: 'Recency_Days', label: 'Recency', align: 'right' },
    { id: 'Orders', label: 'Orders', align: 'right' },
    { id: 'Total_Products', label: 'Units', align: 'right' },
    { id: 'Total_Spent', label: 'Spend', align: 'right' },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Loading State */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
          <Typography>Loading dashboard...</Typography>
        </Box>
      )}

      {/* KPI Row */}
      <Grid container spacing={3}>
        {kpiCards.map((card, index) => (
          <Grid item xs={12} sm={6} lg={2.4} xl={2.4} key={index}>
            <KpiCard {...card} />
          </Grid>
        ))}
      </Grid>

      {/* Chart and Leaderboard Row */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={8} xl={8}>
          <ChartContainer
            title="Product Sales Analysis"
            subtitle="Real-time revenue trends"
            chartType={chartType}
            data={{ series: chartData.series, periods: chartData.periods, locations: [] }}
            onChartTypeChange={handleChartTypeChange}
            onCountryChange={handleCountryChange}
            countries={[]}
          />
        </Grid>
        <Grid item xs={12} lg={4} xl={4}>
          <Card sx={{ borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
            <CardHeader title="Top Products" sx={{ pb: 2 }} />
            <CardContent>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Click any product to add to chart
              </Typography>
              {/* Product leaderboard would go here */}
              <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="textSecondary">Product leaderboard loading...</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Customer Table Row */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={8} xl={8}>
          <DataTable
            columns={customerColumns}
            data={customerData}
            enableSearch
            searchPlaceholder="Search customers..."
          />
        </Grid>
        <Grid item xs={12} lg={4} xl={4}>
          <Card sx={{ borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', height: '100%' }}>
            <CardHeader title="Customer Inspector" sx={{ pb: 2 }} />
            <CardContent>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Select a customer from the table
              </Typography>
              <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="textSecondary">Select customer to inspect</Typography>
              </Box>
          </Card>
        </Grid>
      </Grid>

      {/* RFM Segment Row */}
      <Grid item xs={12}>
        <Card sx={{ borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
          <CardHeader title="RFM Segment Distribution" sx={{ pb: 2 }} />
          <CardContent>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
              Customer behavior analysis
            </Typography>
            <Box sx={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography color="textSecondary">RFM matrix loading...</Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Box>
  );
};

export default Dashboard;