import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly items = new BehaviorSubject<Toast[]>([]);
  private sequence = 0;
  readonly messages: Observable<Toast[]> = this.items.asObservable();

  show(message: string, type: Toast['type'] = 'success'): void {
    const toast: Toast = { id: ++this.sequence, message, type };
    this.items.next([...this.items.value, toast].slice(-4));
    window.setTimeout(() => this.dismiss(toast.id), 3800);
  }

  dismiss(id: number): void {
    this.items.next(this.items.value.filter((item) => item.id !== id));
  }
}
