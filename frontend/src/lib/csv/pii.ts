import type { TableData } from '../../types/contract';

export interface PIIDetection {
  detected: boolean;
  type?: 'email' | 'phone' | 'credit_card' | 'ssn' | 'sensitive_column';
  column?: string;
  sample?: string;
  message: string;
}

const EMAIL_REGEX = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/;
const PHONE_REGEX = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/;
const SSN_REGEX = /\b\d{3}-\d{2}-\d{4}\b/;
const CARD_REGEX = /\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{13,19}\b/;

const SENSITIVE_COLUMN_NAMES = [
  'email',
  'e-mail',
  'phone',
  'telephone',
  'mobile',
  'ssn',
  'social_security',
  'credit_card',
  'card_number',
  'password',
  'secret',
];

/**
 * Standard Luhn algorithm to check if a numeric sequence is a valid credit card.
 */
function isValidLuhn(numStr: string): boolean {
  const digits = numStr.replace(/\D/g, '');
  if (digits.length < 13 || digits.length > 19) return false;

  let sum = 0;
  let alternate = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = parseInt(digits.charAt(i), 10);
    if (alternate) {
      n *= 2;
      if (n > 9) n = (n % 10) + 1;
    }
    sum += n;
    alternate = !alternate;
  }
  return sum % 10 === 0;
}

/**
 * Screens table columns and cell values for PII.
 * Refuses table if personal data patterns are matched.
 */
export function screenForPII(table: TableData): PIIDetection {
  // 1. Check column headers
  for (const col of table.cols) {
    const lower = col.toLowerCase().trim();
    for (const sens of SENSITIVE_COLUMN_NAMES) {
      if (lower === sens || lower.includes(sens)) {
        return {
          detected: true,
          type: 'sensitive_column',
          column: col,
          message: `Column "${col}" suggests personal identifiable information.`,
        };
      }
    }
  }

  // 2. Check sample cell values (up to first 100 rows for high performance)
  const rowsToCheck = table.rows.slice(0, 100);

  for (let r = 0; r < rowsToCheck.length; r++) {
    const row = rowsToCheck[r];
    if (!row) continue;

    for (let c = 0; c < row.length; c++) {
      const val = row[c];
      if (val === null || val === undefined) continue;
      const str = String(val).trim();
      if (!str) continue;

      if (EMAIL_REGEX.test(str)) {
        return {
          detected: true,
          type: 'email',
          column: table.cols[c],
          message: `Email address pattern detected in column "${table.cols[c]}".`,
        };
      }

      if (PHONE_REGEX.test(str)) {
        return {
          detected: true,
          type: 'phone',
          column: table.cols[c],
          message: `Phone number pattern detected in column "${table.cols[c]}".`,
        };
      }

      if (SSN_REGEX.test(str)) {
        return {
          detected: true,
          type: 'ssn',
          column: table.cols[c],
          message: `Social Security / ID number pattern detected in column "${table.cols[c]}".`,
        };
      }

      if (CARD_REGEX.test(str) && isValidLuhn(str)) {
        return {
          detected: true,
          type: 'credit_card',
          column: table.cols[c],
          message: `Credit card number detected in column "${table.cols[c]}".`,
        };
      }
    }
  }

  return {
    detected: false,
    message: 'No personal information patterns detected.',
  };
}
