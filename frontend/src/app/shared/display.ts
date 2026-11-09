export function numberTr(value: string | number, digits = 2): string {
  const parsed = typeof value === 'number' ? value : Number(value);
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(Number.isFinite(parsed) ? parsed : 0);
}

export function statusLabel(status: string): string {
  return {
    OPEN: 'Açık / Teklif toplanıyor',
    EVALUATION: 'Değerlendirmede',
    AWARDED: 'Kabul edildi / Teslim bekleniyor',
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
