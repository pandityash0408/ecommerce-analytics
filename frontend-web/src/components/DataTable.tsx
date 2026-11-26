import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip, Box } from '@mui/material';
import { styled } from '@mui/system';

const StyledTableContainer = styled(TableContainer)(({ theme }) => ({
  borderRadius: '12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  maxHeight: '500px',
  '&::-webkit-scrollbar': { width: '8px' },
  '&::-webkit-scrollbar-track': { backgroundColor: '#F1F5F9' },
  '&::-webkit-scrollbar-thumb': {
    backgroundColor: '#94A3B8',
    borderRadius: '4px',
    '&:hover': { backgroundColor: '#64748B' }
  },
}));

interface DataTableProps {
  columns: Array<{ id: string; label: string; align?: 'left' | 'right'; sortable?: boolean }>;
  data: any[];
  onRowClick?: (row: any) => void;
  renderRow?: (row: any) => React.ReactNode;
  enableSearch?: boolean;
  searchPlaceholder?: string;
}

const DataTable: React.FC<DataTableProps> = ({
  columns,
  data,
  onRowClick,
  renderRow,
  enableSearch = false,
  searchPlaceholder = 'Search...',
}) => {
  const [searchQuery, setSearchQuery] = React.useState('');
  const filteredData = enableSearch
    ? data.filter(row =>
        Object.values(row).some(val =>
          String(val).toLowerCase().includes(searchQuery.toLowerCase())
        )
      )
    : data;

  const getColumnAlign = (align: string | undefined) => align === 'right' ? 'flex' : 'block';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {enableSearch && (
        <Box
          sx={{
            position: 'relative',
            width: '100%',
            maxWidth: '400px',
          }}
        >
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid #E2E8F0',
              backgroundColor: '#F8FAFC',
              fontSize: '0.875rem',
              transition: 'all 0.2s ease',
              '&:focus': {
                outline: 'none',
                borderColor: '#1976D2',
                backgroundColor: '#FFFFFF',
              },
            }}
          />
        </Box>
      )}

      <StyledTableContainer component={Paper}>
        <Table sx={{ minWidth: 650 }} stickyHeader>
          <TableHead>
            <TableRow>
              {columns.map(col => (
                <TableCell
                  key={col.id}
                  align={col.align || 'left'}
                  sx={{
                    fontWeight: 600,
                    backgroundColor: '#F1F5F9',
                    color: '#334155',
                    fontSize: '0.875rem',
                    padding: '12px 16px',
                  }}
                >
                  {col.label}
                  {col.sortable && (
                    <Box component="span" sx={{ ml: 1, fontSize: '0.75rem', color: '#94A3B8' }}>
                      ↕
                    </Box>
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredData.map((row, rowIndex) => (
              <TableRow
                key={rowIndex}
                hover
                onClick={() => onRowClick?.(row)}
                sx={{
                  '&:hover': { backgroundColor: '#E3F2FD' },
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background-color 0.2s ease',
                }}
                selected={row.selected}
              >
                {columns.map(col => {
                  const value = row[col.id];
                  const displayValue = typeof value === 'number'
                    ? value.toLocaleString('en-IN')
                    : String(value);

                  return (
                    <TableCell
                      key={col.id}
                      align={col.align || 'left'}
                      sx={{
                        padding: '12px 16px',
                        fontSize: '0.875rem',
                        color: 'text.primary',
                      }}
                    >
                      {col.id === 'Segment' && typeof value === 'string' && (
                        <Chip
                          label={value}
                          size="small"
                          color={getSegmentColor(value)}
                          sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                        />
                      )}
                      {displayValue}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </StyledTableContainer>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
        <Typography variant="body2" color="textSecondary">
          {filteredData.length} records
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" color="secondary">Previous</Button>
          <Typography variant="body2" sx={{ px: 2, py: 0.5, backgroundColor: '#F1F5F9', borderRadius: '4px' }}>1</Typography>
          <Button variant="outlined" size="small" color="secondary">Next</Button>
        </Box>
      </Box>
    </Box>
  );
};

const getSegmentColor = (segment: string) => {
  const segmentMap = {
    'Champions (VIP)': 'success',
    'Loyal Customers': 'warning',
    'At-Risk / Slipping': 'error',
    'Hibernating / Inactive': 'default',
  };
  return segmentMap[segment] || 'default';
};

export default DataTable;