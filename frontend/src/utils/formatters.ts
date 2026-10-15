/**
 * Formats numeric values or strings into standard Indian Rupee currency format
 * e.g. 201402126.89 -> ₹20,14,02,126.89
 *      1443.84 -> ₹1,443.84
 *      950000 -> ₹9,50,000.00
 */
export function formatINR(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') {
    return '₹0.00';
  }

  let num: number;
  if (typeof amount === 'string') {
    const cleaned = amount.replace(/[₹Rs,\s]/g, '');
    num = parseFloat(cleaned);
    if (isNaN(num)) {
      return amount; // Return raw string if not a parseable number
    }
  } else {
    num = amount;
  }

  const isNegative = num < 0;
  const absNum = Math.abs(num);

  const [intStr, decStr = '00'] = absNum.toFixed(2).split('.');

  let formattedInt: string;
  if (intStr.length <= 3) {
    formattedInt = intStr;
  } else {
    const lastThree = intStr.substring(intStr.length - 3);
    const otherNumbers = intStr.substring(0, intStr.length - 3);
    const groups: string[] = [];
    let rem = otherNumbers;
    while (rem.length > 2) {
      groups.unshift(rem.slice(-2));
      rem = rem.slice(0, -2);
    }
    if (rem.length > 0) {
      groups.unshift(rem);
    }
    formattedInt = `${groups.join(',')},${lastThree}`;
  }

  const result = `₹${formattedInt}.${decStr}`;
  return isNegative ? `-${result}` : result;
}

/**
 * Formats file size in bytes to human-readable KB, MB
 */
export function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Formats ISO date string into readable accountant date
 */
export function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return '-';
  try {
    const date = new Date(isoStr);
    return date.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return isoStr;
  }
}

/**
 * Formats ISO date string into readable accountant datetime
 */
export function formatDateTime(isoStr: string | null | undefined): string {
  if (!isoStr) return '-';
  try {
    const date = new Date(isoStr);
    return date.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
}
