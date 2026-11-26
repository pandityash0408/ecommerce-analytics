import React, { useRef, useEffect } from 'react';
import { Card, CardHeader, CardContent, Box, Typography, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Chart from 'chart.js/auto';

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  chartType: 'line' | 'bar' | 'map';
  data: any;
  onChartTypeChange?: (type: string) => void;
  onCountryChange?: (country: string) => void;
  countries?: string[];
}

const ChartContainer: React.FC<ChartContainerProps> = ({
  title,
  subtitle,
  chartType,
  data,
  onChartTypeChange,
  onCountryChange,
  countries = [],
}) => {
  const theme = useTheme();
  const chartRef = useRef<HTMLCanvasElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chartType === 'map' && mapRef.current && data?.locations) {
      renderMapChart(data.locations);
    } else if (chartType !== 'map' && chartRef.current) {
      renderChart(chartType, data?.series, data?.periods);
    }
    // Cleanup on unmount
    return () => {
      if (window.chartInstance) {
        window.chartInstance.destroy();
        window.chartInstance = null;
      }
    };
  }, [chartType, data]);

  const renderChart = (type: string, series: any[], periods: string[]) => {
    if (!chartRef.current) return;

    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;

    const colors = ['#1976D2', '#2196F3', '#FF9800', '#673AB7', '#009688', '#FF5722'];

    const datasets = (series || []).map((s, idx) => ({
      label: s.product,
      data: (s[type as keyof typeof s] || []),
      borderColor: colors[idx % colors.length],
      backgroundColor: type === 'bar' ? colors[idx % colors.length] + '40' : colors[idx % colors.length],
      borderWidth: type === 'bar' ? 1 : 2,
      tension: type === 'line' ? 0.2 : 0,
      fill: type === 'area' ? true : false,
    }));

    window.chartInstance = new Chart(ctx, {
      type: type === 'area' ? 'line' : type,
      data: {
        labels: periods || [],
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: {
              color: theme.palette.text.secondary,
              boxWidth: 12,
              font: { size: 11 },
            },
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleFont: { size: 12, weight: 'bold' },
            bodyFont: { size: 11 },
            padding: 8,
          },
        },
        scales: {
          x: {
            ticks: { color: theme.palette.text.secondary, font: { size: 11 } },
            grid: { color: theme.palette.divider, drawBorder: false },
          },
          y: {
            ticks: { color: theme.palette.text.secondary, font: { size: 11 } },
            grid: { color: theme.palette.divider, drawBorder: false },
          },
        },
      },
    });
  };

  const renderMapChart = (locations: any[]) => {
    if (!mapRef.current) return;

    const maxVal = Math.max(...locations.map(l => Math.abs(l.revenue || 0)), 1);
    const sorted = locations.sort((a, b) => (b.revenue || 0) - (a.revenue || 0));

    mapRef.current.innerHTML = locations.map(l => `
      <div
        class="map-pin"
        style="
          position: absolute;
          left: ${((l.longitude || 0.5) * 100)}%;
          top: ${((l.latitude || 0.5) * 100)}%;
          width: ${Math.max(20, Math.min(40, Math.round(20 + (Math.abs(l.revenue || 0) / maxVal) * 16))}px;
          height: ${Math.max(20, Math.min(40, Math.round(20 + (Math.abs(l.revenue || 0) / maxVal) * 16))}px;
        }"
        onClick={() => onCountryChange?.(l.location)}
      >
        <div style="backgroundColor: '#1976D2'; color: 'white'; fontSize: '10px'; fontWeight: 'bold'; textAlign: 'center'; lineHeight: '${Math.max(20, Math.min(40, Math.round(20 + (Math.abs(l.revenue || 0) / maxVal) * 16))}px';">
          ${l.location?.charAt(0)}
        </div>
      </div>
    `).join('');
  };

  return (
    <Card sx={{ borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', overflow: 'hidden' }}>
      <CardHeader sx={{ pb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h6" component="h3">{title}</Typography>
            {subtitle && (
              <Typography variant="body2" color="textSecondary">{subtitle}</Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {['line', 'bar', 'map'].map(type => (
              <Box
                key={type}
                sx={{
                  px: 2,
                  py: 0.5,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  backgroundColor: chartType === type ? theme.palette.primary.main : 'transparent',
                  color: chartType === type ? 'white' : theme.palette.text.secondary,
                  '&:hover': { backgroundColor: theme.palette.primary.light },
                }}
                onClick={() => onChartTypeChange?.(type)}
              >
                <Typography variant="caption" sx={{ fontWeight: 600 }}>{type}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </CardHeader>

      <CardContent sx={{ p: 0 }}>
        <Box sx={{ position: 'relative', height: 400 }}>
          {chartType !== 'map' ? (
            <canvas ref={chartRef} style={{ width: '100%', height: '100%' }} />
          ) : (
            <Box
              ref={mapRef}
              sx={{
                width: '100%',
                height: '100%',
                position: 'relative',
                backgroundColor: theme.palette.background.paper,
              }}
            />
          )}
        </Box>

        {chartType === 'map' && countries.length > 0 && (
          <FormControl
            sx={{
              position: 'absolute',
              top: 16,
              right: 16,
              minWidth: 160,
              backgroundColor: 'white',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          >
            <InputLabel sx={{ fontSize: '0.875rem' }}>Filter by Country</InputLabel>
            <Select
              value={''}
              onChange={(e) => onCountryChange?.(e.target.value)}
              sx={{ fontSize: '0.875rem' }}
            >
              <MenuItem value="">All Countries</MenuItem>
              {countries.map(country => (
                <MenuItem key={country} value={country}>{country}</MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </CardContent>
    </Card>
  );
};

export default ChartContainer;