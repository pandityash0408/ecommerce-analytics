import React from 'react';
import { Card, CardContent, Box, Typography, Chip } from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import { styled } from '@mui/system';

const KpiCardRoot = styled(Card)(({ theme }) => ({
  background: 'linear-gradient(135deg, #E3F2FD 0%, #FFFFFF 100%)',
  border: '1px solid #E3F2FD',
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  transition: 'transform 0.2s ease, box-shadow 0.2s ease',
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: '0 8px 16px -2px rgba(0, 0, 0, 0.15)',
  },
}));

interface KpiCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  trend?: number; // percentage change
  trendDirection?: 'up' | 'down' | 'neutral';
  color?: 'primary' | 'secondary' | 'accent';
}

const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  trendDirection = 'neutral',
  color = 'primary',
}) => {
  const getTrendColor = () => {
    if (trendDirection === 'up') return '#388E3C'; // green
    if (trendDirection === 'down') return '#D32F2F'; // red
    return '#64748B'; // neutral gray
  };

  const getTrendIcon = () => {
    if (trendDirection === 'up') return <TrendingUp sx={{ fontSize: 16 }} />;
    if (trendDirection === 'down') return <TrendingDown sx={{ fontSize: 16 }} />;
    return null;
  };

  return (
    <KpiCardRoot>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: color === 'primary' ? '#1976D2' : color === 'secondary' ? '#2196F3' : '#FF9800',
              mr: 2,
            }}
          />
          <Typography
            variant="overline"
            color="textSecondary"
            sx={{ fontWeight: 600, letterSpacing: '0.05em' }}
          >
            {title}
          </Typography>
        </Box>

        <Typography
          variant="h3"
          component="h2"
          sx={{
            fontWeight: 700,
            mb: 1,
            color: 'text.primary',
            lineHeight: 1.2,
          }}
        >
          {typeof value === 'number' ? value.toLocaleString('en-IN') : value}
        </Typography>

        {subtitle && (
          <Typography
            variant="body2"
            color="textSecondary"
            sx={{ mb: 2, fontSize: '0.875rem' }}
          >
            {subtitle}
          </Typography>
        )}

        {trend !== undefined && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {getTrendIcon()}
            <Typography
              variant="caption"
              sx={{
                color: getTrendColor(),
                fontWeight: 600,
                fontSize: '0.75rem',
              }}
            >
              {trend > 0 ? '+' : ''}{trend.toFixed(1)}% vs last period
            </Typography>
          </Box>
        )}
      </CardContent>
    </KpiCardRoot>
  );
};

export default KpiCard;