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
