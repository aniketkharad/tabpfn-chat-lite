import type { ColumnType, CellValue } from '../../types/contract';

const DATE_REGEX = /^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const INT_REGEX = /^-?\d+$/;
const FLOAT_REGEX = /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/;

/**
 * Infer column data types from an array of sample/all rows.
 */
export function inferColumnTypes(cols: string[], rows: CellValue[][]): ColumnType[] {
  return cols.map((_, colIdx) => {
    const nonNullValues: string[] = [];

    for (let r = 0; r < rows.length; r++) {
      const val = rows[r]?.[colIdx];
      if (val !== null && val !== undefined && val !== '') {
        nonNullValues.push(String(val).trim());
      }
    }

    if (nonNullValues.length === 0) {
      return 'string';
    }

    // Check boolean
    const allBool = nonNullValues.every((v) => {
      const lower = v.toLowerCase();
      return lower === 'true' || lower === 'false' || lower === 'yes' || lower === 'no';
    });
    if (allBool) return 'boolean';

    // Check integer
    const allInt = nonNullValues.every((v) => INT_REGEX.test(v));
    if (allInt) return 'int';

    // Check float
    const allFloat = nonNullValues.every((v) => FLOAT_REGEX.test(v));
    if (allFloat) return 'float';

    // Check datetime
    const allDate = nonNullValues.every((v) => DATE_REGEX.test(v) && !isNaN(Date.parse(v)));
    if (allDate) return 'datetime';

    return 'string';
  });
}
