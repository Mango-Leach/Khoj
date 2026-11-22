/** Keeps only digits, drops a +91 / 91 / 0 prefix, and caps at 10 digits. */
export function cleanPhone(raw: string): string {
  let digits = raw.replace(/\D/g, "");
  if (digits.length > 10 && digits.startsWith("91")) digits = digits.slice(2);
  if (digits.length > 10 && digits.startsWith("0")) digits = digits.slice(1);
  return digits.slice(0, 10);
}

/** An Indian mobile number: 10 digits starting with 6 to 9. */
export function isValidPhone(digits: string): boolean {
  return /^[6-9]\d{9}$/.test(digits);
}

/** "98765 43210" for display while typing. */
export function formatPhone(digits: string): string {
  return digits.length > 5 ? `${digits.slice(0, 5)} ${digits.slice(5)}` : digits;
}

/** "+91 98••• ••210": enough to recognise the number, not enough to read it aloud. */
export function maskPhone(digits: string): string {
  if (digits.length < 10) return `+91 ${digits}`;
  return `+91 ${digits.slice(0, 2)}••• ••${digits.slice(-3)}`;
}
