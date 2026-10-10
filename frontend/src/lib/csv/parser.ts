import type { CellValue, TableData } from '../../types/contract';
import { inferColumnTypes } from './inference';

export interface ParseOptions {
  maxRows?: number;
  maxCols?: number;
  maxCellLength?: number;
}

export interface ParseResult {
  table: TableData;
  totalRows: number;
  totalCols: number;
  truncated: boolean;
  errors: string[];
}

/**
 * Hand-rolled RFC 4180 compliant CSV parser.
 * Zero dependencies. Handles quoted fields, escaped quotes (""), multiline fields, CRLF/LF.
 */
export function parseCSV(csvText: string, options: ParseOptions = {}): ParseResult {
  const maxRows = options.maxRows ?? 200;
  const maxCols = options.maxCols ?? 50;
  const maxCellLength = options.maxCellLength ?? 64;

  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = '';
  let insideQuote = false;
  let i = 0;
  const len = csvText.length;
  const errors: string[] = [];

  while (i < len) {
    const char = csvText[i];

    if (insideQuote) {
      if (char === '"') {
        if (i + 1 < len && csvText[i + 1] === '"') {
          // Escaped quote
          currentField += '"';
          i += 2;
          continue;
        } else {
          // Closing quote
          insideQuote = false;
          i++;
          continue;
        }
      } else {
        currentField += char;
        i++;
        continue;
      }
    } else {
      if (char === '"') {
        insideQuote = true;
        i++;
        continue;
      } else if (char === ',') {
        currentRow.push(currentField.trim());
        currentField = '';
        i++;
        continue;
      } else if (char === '\r') {
        if (i + 1 < len && csvText[i + 1] === '\n') {
          i++;
        }
        currentRow.push(currentField.trim());
        if (currentRow.some((f) => f.length > 0)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentField = '';
        i++;
        continue;
      } else if (char === '\n') {
        currentRow.push(currentField.trim());
        if (currentRow.some((f) => f.length > 0)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentField = '';
        i++;
        continue;
      } else {
        currentField += char;
        i++;
        continue;
      }
    }
  }

  // Push final field/row if any
  if (currentField.length > 0 || currentRow.length > 0) {
    currentRow.push(currentField.trim());
    if (currentRow.some((f) => f.length > 0)) {
      rows.push(currentRow);
    }
  }

  if (rows.length === 0) {
    return {
      table: { cols: [], types: [], rows: [] },
      totalRows: 0,
      totalCols: 0,
      truncated: false,
      errors: ['File is empty or contains no parseable records.'],
    };
  }

  const headerRow = rows[0]!;
  const cols = headerRow.map((col, idx) => {
    const cleaned = col.trim() || `col_${idx + 1}`;
    return cleaned.length > maxCellLength ? cleaned.slice(0, maxCellLength) : cleaned;
  });

  const rawDataRows = rows.slice(1);
  const totalRows = rawDataRows.length;
  const totalCols = cols.length;

  if (totalCols > maxCols) {
    errors.push(`Table has ${totalCols} columns, exceeding the limit of ${maxCols}.`);
  }

  if (totalRows > maxRows) {
    errors.push(`Table has ${totalRows} rows, exceeding the limit of ${maxRows}.`);
  }

  const cappedRows = rawDataRows.slice(0, maxRows);
  const processedRows: CellValue[][] = cappedRows.map((row) => {
    return cols.map((_, colIdx) => {
      let rawVal = row[colIdx] ?? '';
      rawVal = rawVal.trim();
      if (rawVal === '' || rawVal.toLowerCase() === 'null' || rawVal.toLowerCase() === 'none' || rawVal === 'NaN') {
        return null;
      }
      if (rawVal.length > maxCellLength) {
        return rawVal.slice(0, maxCellLength);
      }
      return rawVal;
    });
  });

  const types = inferColumnTypes(cols, processedRows);

  // Convert row values to inferred primitive types
  const typedRows: CellValue[][] = processedRows.map((row) => {
    return row.map((val, colIdx) => {
      if (val === null) return null;
      const type = types[colIdx];
      const str = String(val);

      if (type === 'int') {
        const parsed = parseInt(str, 10);
        return isNaN(parsed) ? null : parsed;
      }
      if (type === 'float') {
        const parsed = parseFloat(str);
        return isNaN(parsed) ? null : parsed;
      }
      if (type === 'boolean') {
        const lower = str.toLowerCase();
        if (lower === 'true' || lower === '1') return true;
        if (lower === 'false' || lower === '0') return false;
        return null;
      }
      return str;
    });
  });

  return {
    table: {
      cols,
      types,
      rows: typedRows,
    },
    totalRows,
    totalCols,
    truncated: rawDataRows.length > maxRows,
    errors,
  };
}

/**
 * Generate RFC 4180 compliant CSV string from TableData.
 */
export function generateCSV(table: TableData): string {
  const escapeCell = (val: CellValue): string => {
    if (val === null || val === undefined) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headerLine = table.cols.map(escapeCell).join(',');
  const rowLines = table.rows.map((row) => row.map(escapeCell).join(','));
  return [headerLine, ...rowLines].join('\r\n');
}

/**
 * Trigger client-side file download for TableData.
 */
export function downloadTableAsCSV(table: TableData, filename = 'export.csv'): void {
  const csvContent = generateCSV(table);
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename.endsWith('.csv') ? filename : `${filename}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
