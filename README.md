# Yem İhale Simülasyonu

Yem tüketimini simüle eden, kritik kapsama ulaşıldığında otomatik ihale açan ve yalnızca backend tarafından yönetilen NPC tedarikçilerden teklif toplayan yönetici uygulamasıdır.

Bu repository, ekli **Yem İhale Simülasyonu v4.0** PDF şartnamesini bağlayıcı kaynak kabul eder. İnsan tedarikçi, kullanıcı hesabı, JWT, manuel teklif/kabul, mesaj, bildirim, ödeme, rapor ve dosya aktarımı bulunmaz.

## Kurulum

Docker Desktop ve Docker Compose v2 yeterlidir.

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Arayüz: http://localhost:8080

Health: http://localhost:8080/api/v1/health

Swagger: http://localhost:8080/api/docs

Kodun çalışması için hostta Python, Node veya MariaDB gerekmez. Gerçek `.env` dosyası git'e eklenmez.

## Katmanlar

- `backend/`: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 senkron, PyMySQL, Alembic.
- `frontend/`: Angular 21 standalone, Reactive Forms, HttpClient, Türkçe yönetici arayüzü.
- `compose.yaml`: MariaDB 11.4, backend ve Nginx servisleri.
- `backend/migrations/`: Altı tabloyu oluşturan Alembic migration.
- `backend/app/simulation/`: saf iş kuralları, NPC üretimi, değerlendirme ve kronolojik tick motoru.

Backend ve MariaDB host portu açmaz; yalnız Nginx 127.0.0.1:8080 üzerinden yayın yapar. Backend tek Uvicorn worker ile çalışır.

## Seed verisi

Entrypoint sırası:

1. `alembic upgrade head`
2. `python -m app.seed`
3. Tek Uvicorn worker

Seed mevcut kayıtları değiştirmez. Üç temel ürün, üç NPC ve dokuz NPC kuralı eksikse eklenir. Simülasyon başlangıçta duraklatılmıştır.

## Simülasyon davranışı

- Stok tüketimi: `max(0, stok - kg/dakika * geçen_saniye / 60)`.
- Kapsama: `stok / tüketim`.
- Kapsama kritik değere eşit veya küçük olduğunda hedef kapsama göre 0,001 ton basamağına yukarı yuvarlanmış ihale açılır.
- Aynı üründe OPEN, EVALUATION veya AWARDED süreç varken ikinci aktif süreç açılamaz.
- Farklı ürünler bağımsız olarak eşzamanlı ilerler.
- NPC davet anında cevap planını tek kez oluşturur; gerçekleşen teklifler participation satırına tek kez yazılır.
- OPEN yanıtlarında fiyat, teslim ve plan alanları public modelden tamamen çıkarılır. `/offers` ucu OPEN için 409 OFFERS_HIDDEN döner.
- Tick olayları tüketim, teslimat, NPC cevapları, kapanış, değerlendirme ve yeni ihtiyaç sırasıyla kronolojik işlenir.
- Teslimat yalnız AWARDED -> DELIVERED geçişinde bir kez stok ekler.
- Backend yeniden başlarsa simülasyon duraklatılır; kapalı gerçek zaman tüketim olarak yazılmaz.

PDF’deki v4.0 kuralı gereği kapanışa tam eşit NPC cevabı kabul edilmez; planlanan cevap aralığı açılıştan 1 saniye sonrası ile kapanıştan 1 saniye öncesidir.

## API özeti

`/api/v1` altında:

- `GET /health`
- `GET|POST /simulation`, `/simulation/start`, `/simulation/pause`
- `GET /products`, `PATCH /products/{id}`
- `GET /npc-rules?product_id=`, `PATCH /npc-rules/{id}`
- `GET /tenders?product_id=&status=`
- `GET /tenders/{id}`
- `GET /tenders/{id}/offers`

Decimal değerler JSON'da dizge olarak döner. Liste yanıtları `{items:[...]}`, hatalar `{error:{code,message}}` biçimindedir.

## Test

Saf iş kuralı testleri DB ve gerçek zaman beklemesi gerektirmez:

```powershell
docker compose run --rm --no-deps backend pytest -q
```

Hosttan çalıştırmak için:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

Frontend için ayrı bir tarayıcı birim test paketi kurulmamıştır; `npm test` üretim derlemesini çalıştıran bir smoke test komutudur:

```powershell
cd frontend
npm test
```

Test kapsamı: tüketim, negatif stok koruması, kapsama, yukarı yuvarlama, olasılık sınırları, fiyat ve teslim sınırları, uygun teklif seçimi, acil kabul, eşitlik, idempotent teslimat ve aynı zamandaki kronolojik olay sırası.

## Ekranlar

Uygulama yalnızca şu beş route'u içerir:

- `/`: Özet
- `/products`: Ürün Ayarları
- `/npc-rules`: NPC Kuralları
- `/tenders`: İhale Listesi
- `/tenders/:id`: İhale Detayı

Teklifler yaklaşık iki saniyede polling ile güncellenir. Ekranlarda yükleniyor, hata, yeniden dene ve boş durumlar bulunur. Açık ihalelerde gizlilik CSS ile değil, API veri modeliyle sağlanır.

## Kabul kontrol listesi

1. **PASS** — Tüketim ve stok tabanı: `simulation/rules.py`, `test_consumption_never_makes_stock_negative`.
2. **PASS** — Kritik kapsama ve hedef miktar: `tender_quantity_ton`, `test_quantity_is_rounded_up_to_thousandth_ton`.
3. **PASS** — Eşzamanlı ürün akışı ve ürün başına aktif süreç kontrolü: `engine.py::_open_needed_tenders`.
4. **PASS** — Davetli NPC, %0/%100 sınırları ve RNG enjeksiyonu: `npc.py`, `test_probability_boundaries`.
5. **PASS** — Planın ve participation satırının tekrar üretilmemesi: DB'deki `will_respond`, `response_at_seconds` ve UNIQUE kısıtı.
6. **PASS** — OPEN gizliliği: public serializer plan/fiyat alanlarını üretmiyor; çalışan Compose testinde `/tenders/11/offers` 409 OFFERS_HIDDEN döndü.
7. **PASS** — Kapanış ve ayrı değerlendirme anı: `close` ve `evaluate` olayları ayrı zamanlanıyor.
8. **PASS** — Uygun teklif, eşitlik ve acil kabul: `evaluation.py`, ilgili pytest senaryoları.
9. **PASS** — Tek teslimat: `deliver_stock_once`, idempotency testi ve AWARDED -> DELIVERED guard'ı.
10. **PASS** — Teklif yoksa NO_AWARD ve 30 saniye yeniden deneme: `engine.py::_evaluate_tender`.
11. **PASS** — Karar anı stok/kapsama snapshot'ı ve kalıcı gerekçe: Tender değerlendirme alanları.
12. **PASS** — Uzun tick olay sırası: `timeline.py`, `test_long_tick_event_order_is_chronological_and_prioritized`.
13. **PASS** — Kilitli ayarlar ve 422 doğrulama: `products.py`, `npc_rules.py`, Pydantic patch şemaları.
14. **PASS** — Restart duraklatması: `initialize_after_restart` is_running=false ve last_tick_at temizliği.
15. **PASS** — Kapsam dışı özellikler yok: route listesi beş ekranla sınırlı; auth/tedarikçi/manuel teklif/mesaj yok.
16. **PASS** — Compose: `docker compose config`, `docker compose build`, `docker compose up -d`, frontend build ve health 200 doğrulandı.

## Veri kalıcılığı

`docker compose down` container'ları durdurur, `db_data` volume'unu korur. `docker compose down -v` volume'u siler ve yalnız temiz başlangıç gerektiğinde kullanılmalıdır.

## Bilinen notlar

- Docker volume daha önce kullanılmışsa seed mevcut kayıtları koruduğu için eski demo kayıtları listede kalabilir. Tamamen temiz demo için kullanıcı kontrollü olarak `docker compose down -v` sonrası yeniden başlatabilir.
- Docker build sırasında npm audit bağımlılık ağacında uyarılar bildirebilir; production build başarılıdır.

