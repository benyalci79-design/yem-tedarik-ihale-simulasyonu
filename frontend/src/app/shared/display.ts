export const SECONDS_PER_DAY = 30;
export const DAYS_PER_MONTH = 30;
export const MONTHS_PER_YEAR = 12;
export const SECONDS_PER_MONTH = SECONDS_PER_DAY * DAYS_PER_MONTH;
export const SECONDS_PER_YEAR = SECONDS_PER_MONTH * MONTHS_PER_YEAR;

export function simCalendarText(totalSeconds: string | number): { date: string; time: string; combined: string } {
  const total = Math.max(0, Number(totalSeconds) || 0);
  const years = Math.floor(total / SECONDS_PER_YEAR);
  let rest = total - years * SECONDS_PER_YEAR;
  const months = Math.floor(rest / SECONDS_PER_MONTH);
  rest -= months * SECONDS_PER_MONTH;
  const days = Math.floor(rest / SECONDS_PER_DAY);
  rest -= days * SECONDS_PER_DAY;

  const dayFraction = rest / SECONDS_PER_DAY;
  const hours = Math.floor(dayFraction * 24);
  const minutes = Math.floor((dayFraction * 24 - hours) * 60);

  const parts: string[] = [];
  if (years) parts.push(`${years} yıl`);
  if (months) parts.push(`${months} ay`);
  if (days || parts.length === 0) parts.push(`${days} gün`);
  const date = parts.join(' ');
  const time = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
  return { date, time, combined: `${date} ${time}` };
}

export function simDurationShort(totalSeconds: string | number): string {
  return simCalendarText(totalSeconds).combined;
}

export function numberTr(value: string | number, digits = 2): string {
  const parsed = typeof value === 'number' ? value : Number(value);
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(Number.isFinite(parsed) ? parsed : 0);
}

export function statusLabel(status: string): string {
  return {
    OPEN: 'Teklif toplanıyor',
    EVALUATION: 'Karar bekliyor',
    AWARDED: 'Teslimatta',
    DELIVERED: 'Teslim edildi',
    NO_AWARD: 'Sonuçsuz'
  }[status] ?? status;
}

export function statusIcon(status: string): string {
  return {
    OPEN: '●',
    EVALUATION: '◐',
    AWARDED: '◆',
    DELIVERED: '✓',
    NO_AWARD: '—'
  }[status] ?? '•';
}

export function awardStatusLabel(status: string): string {
  return {
    AWAITING_CARRIER: 'Nakliyeci bekliyor',
    IN_TRANSIT: 'Yolda',
    DELIVERED: 'Teslim edildi'
  }[status] ?? status;
}

export function decisionLabel(decision?: string | null): string {
  return {
    PENDING: 'Bekliyor',
    ACCEPTED: 'Kabul edildi',
    PARTIAL: 'Kısmi kabul',
    REJECTED: 'Reddedildi'
  }[decision ?? ''] ?? (decision ?? '—');
}
