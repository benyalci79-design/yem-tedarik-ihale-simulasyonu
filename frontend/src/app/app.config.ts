import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    // Angular 21 defaults to zoneless change detection. Bu proje RxJS
    // abonelikleri, setTimeout tabanlı saat ve HTTP geri dönüşleriyle klasik
    // (zone tabanlı) yazıldığı için veri gelse bile ekran güncellenmiyordu.
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideHttpClient(),
    provideRouter(routes),
  ],
};
