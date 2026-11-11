# Yem İhale Simülasyonu

Yem tüketimini simüle eden, kritik kapsamaya düşen ürünler için **kullanıcının elle ihale açtığı**, NPC tedarikçilerden gelen teklifleri **kısmi miktarlarla kabul ettiği** ve nakliye hariç teklifler için **nakliyeci atadığı** yönetici uygulamasıdır.

Simülasyon saati gerçek zamandan bağımsız ölçeklenir (Dur · 0,5x · 1x · 2x · 3x); stok, depo kapasitesi, ağırlıklı ortalama maliyet ve ihale akışı bu saat üzerinde ilerler.

## Kurulum

Docker Desktop ve Docker Compose v2 yeterlidir.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Arayüz: http://localhost:8080

Health: http://localhost:8080/api/v1/health

Swagger: http://localhost:8080/api/docs

Angular'ı Docker dışında çalıştırmak için backend ve veritabanını Compose ile başlatın, ayrı bir pencerede:

```powershell
cd frontend
npm start
```

Bu komut `frontend/proxy.conf.json` üzerinden `/api` isteklerini `http://localhost:8000` adresindeki backend'e yönlendirir. Arayüz `http://localhost:4200` adresinden açılır.

Hostta Python, Node veya MariaDB gerekmez. Gerçek `.env` dosyası git'e eklenmez.

## Katmanlar

- `backend/`: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 senkron, PyMySQL, Alembic.
- `frontend/`: Angular 21 standalone, Reactive Forms, HttpClient, Türkçe yönetici arayüzü.
- `compose.yaml`: MariaDB 11.4, backend ve Nginx servisleri.
- `backend/migrations/`: iki migration (ilk şema + manuel ihale/kapasite/nakliye/maliyet).
- `backend/app/simulation/`: saf iş kuralları, NPC teklif üretimi ve kronolojik tick motoru.

Backend ve MariaDB host portu açmaz; yalnız Nginx 127.0.0.1:8080 üzerinden yayın yapar (yerelde backend ayrıca 127.0.0.1:8000'de dinler). Backend tek Uvicorn worker ile çalışır.

## Simülasyon davranışı

- **Hız:** `POST /simulation/speed` yalnızca `0.5`, `1`, `2`, `3` değerlerini kabul eder. Tick'te `delta = gerçek_delta * hız` uygulanır. Hız değiştirilirken önce eski hızla geçen süre işlenir, sonra `last_tick_at` sıfırlanır; böylece geçmiş zaman yanlış ölçeklenmez. Hız veritabanında kalıcıdır, yeniden başlatmada simülasyon durur ama hız korunur.
- **Tüketim:** `max(0, stok - kg/dakika * geçen_saniye / 60)`. Tüketim yalnızca stoğu düşürür, ortalama maliyeti değiştirmez.
- **Kapsama:** `stok / tüketim`.
- **İhale açma:** Yalnızca kullanıcı `POST /tenders` ile açar. Otomatik açılış, otomatik değerlendirme ve 30 saniyelik yeniden deneme **yoktur**. Üründe `OPEN`, `EVALUATION` veya `AWARDED` süreç varken ikinci ihale açılamaz.
- **Depo sınırı:** Ürün başına `capacity_kg`. Kullanılan kapasite = stok + yoldaki (teslim edilmemiş) award miktarı. Sınırı aşan ihale açılışı ve teklif kabulü `422 CAPACITY_EXCEEDED` ile reddedilir.
- **Teklif gizliliği:** `OPEN` aşamasında teklif fiyatı, miktarı ve nakliye modu API'den hiç gönderilmez (`/offers` ucu 409 `OFFERS_HIDDEN`). Süre dolunca ihale `EVALUATION` olur ve teklifler açılır.
- **Kabul:** Kullanıcı bir tekliften `quantity_kg` kadar kabul eder. Üst sınır `min(teklif miktarı, kalan ihtiyaç, boş kapasite)`. Bir tekliften yalnızca bir kez miktar alınır; miktar teklifin tamamıysa `ACCEPTED`, azıysa `PARTIAL`. İhale birden fazla NPC'den karşılanabilir.
- **Tamamlama:** `POST /tenders/{id}/finalize` ihaleyi kapatır. En az bir award varsa `AWARDED`, hiç yoksa `NO_AWARD`; kabul edilmeyen teklifler `REJECTED` olur. Karşılanmayan miktar kaybolur, kullanıcı gerekirse yeni ihale açar.
- **Teslimat:** Her award ayrı teslim edilir. Nakliye dahil teklifler kabul anında `IN_TRANSIT` olur; hariç olanlar nakliyeci atanana kadar `AWAITING_CARRIER` bekler. Teslimde stok `quantity_kg` kadar artar ve ortalama maliyet `landed_cost_tl` ile ağırlıklı ortalamaya girer. Aynı award ikinci kez stok eklemez (idempotent).
- **Backend yeniden başlarsa** simülasyon duraklatılır; kapalı gerçek zaman tüketim olarak yazılmaz.
- **Sıfırlama:** `POST /simulation/reset` tüm ihaleleri, teklifleri, award'ları ve stok geçmişini siler; ürün, NPC kuralı ve nakliyeci değerlerini seed başlangıç değerlerine döndürür; saati 0'a alır, hızı 1x yapar ve simülasyonu duraklatır. Arayüzde üst bardaki **Sıfırla** düğmesi onay penceresi gösterir; onaylanınca sayfa yenilenir. İşlem geri alınamaz.

## Maliyet hesabı

- Teslim maliyeti: `landed_cost_tl = quantity_kg/1000 * (NPC TL/ton + nakliyeci TL/ton)`.
- Ortalama maliyet: `(stok*ortalama + eklenen_toplam_maliyet) / (stok + eklenen_kg)`, 6 basamak.
- **Son alım birim fiyatı:** her teslimatta `landed_cost_tl / quantity_kg` olarak ayrıca saklanır (`products.last_purchase_unit_price`). Stok sıfıra düşse bile bu alan ve ortalama maliyet **korunur**; birim fiyat 0'a inmez. Depo tamamen boşken toplam birim fiyat, ürünlerin son bilinen birim fiyatlarının ortalaması olarak gösterilir.
- Stok değeri: `stok * ortalama maliyet` (stok yoksa 0 TL; fiyat bilgisi ayrı alanda korunur).
- Her tick sonunda ve her teslimattan hemen sonra tüm ürünler için **aynı `elapsed_seconds`** ile `stock_snapshots` satırı yazılır. Ürün başına yaklaşık 3000 nokta tutulur; daha eskiler seyrek bir DELETE ile silinir. `GET /stock-metrics/history?limit=300` noktaları eşit aralıklı örnekler.

## API özeti

`/api/v1` altında:

- `GET /health`
- `GET|POST /simulation`, `/simulation/start`, `/simulation/pause`, `/simulation/speed`, `/simulation/reset`
- `GET /products`, `PATCH /products/{id}` (kapasite, ortalama maliyet ve son alım birim fiyatı dahil)
- `GET /npc-rules?product_id=`, `PATCH /npc-rules/{id}` (nakliye modu, mevcut miktar aralığı dahil)
- `GET /tenders?product_id=&status=`, `POST /tenders`
- `GET /tenders/{id}`, `POST /tenders/{id}/accept`, `POST /tenders/{id}/finalize`
- `GET /tenders/{id}/offers`
- `GET /carriers`, `GET /shipments?status=`, `POST /shipments/{award_id}/assign-carrier`
- `GET /stock-metrics`, `GET /stock-metrics/history?limit=`

Decimal değerler JSON'da dizge olarak döner. Liste yanıtları `{items:[...]}`, hatalar `{error:{code,message}}` biçimindedir.

## Seed verisi

Entrypoint sırası:

1. `alembic upgrade head`
2. `python -m app.seed`
3. Tek Uvicorn worker

Seed **eklemelidir**: mevcut kayıtları ve ayarları değiştirmez, yalnızca eksikleri ekler.

- 3 ürün (MISR 5000 kg, ARPA 4000 kg, SOYA 6000 kg kapasite; 8,75 / 7,75 / 13,00 TL/kg ortalama maliyet).
- **10 NPC** (A–J). Cevap olasılıkları 0,00–1,00; teslim süreleri 1–8 dk; 4 NPC nakliye hariç ve bu yüzden %5–10 daha ucuz; teklif miktarları 300–6000 kg arasında değişir, böylece 2–3 tonluk bir ihale genelde tek NPC'den karşılanmaz.
- Her NPC için her üründe bir kural (30 kural).
- **4 nakliyeci:** Toplu Yük (150 TL/ton, 12 dk), Ekonomik (180, 8), Standart (450, 5), Ekspres (900, 2).

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

Frontend için ayrı bir tarayıcı birim test paketi yoktur; `npm test` üretim derlemesini çalıştıran smoke test komutudur:

```powershell
cd frontend
npm test
```

Test kapsamı: tüketim, negatif stok koruması, kapsama, yukarı yuvarlama, olasılık sınırları, fiyat/teslim/miktar üretimi, kapasite sınırı ve yoldaki miktar, kısmi kabul üst sınırı, landed cost, ağırlıklı ortalama maliyet, teslim zamanı (nakliye dahil/hariç), award idempotency, kronolojik olay sırası, şema doğrulaması.

## Ekranlar

- `/`: Özet — simülasyon saati, stok maliyeti kartları, iki çizgi grafik, süreç akışı, ürün doluluk çubukları.
- `/products`: Ürün Ayarları — stok, tüketim, eşikler, teklif penceresi, **depo kapasitesi**, **ortalama maliyet**, doluluk göstergesi.
- `/npc-rules`: NPC Kuralları — davet, olasılık, fiyat, teslim, **nakliye dahil/hariç**, **mevcut miktar aralığı**; ürün filtresi.
- `/tenders`: İhale Listesi — **yeni ihale açma paneli** (önerilen miktar ve boş kapasite ile), filtreler, kabul özeti.
- `/tenders/:id`: İhale Detayı — üstte **kompakt stok şeridi** (depo doluluğu, yoldaki miktar, boş kapasite, **son alım birim fiyatı**, ortalama maliyet), gizli teklifler, **teklif kabul tablosu (kısmi miktar)**, "İhaleyi tamamla", teslimat/award listesi.
- `/shipping`: Nakliye — nakliyeci bekleyenler, nakliyeci seçimi ve maliyet/teslim önizlemesi, yoldakiler ve teslim edilenler, nakliyeci listesi.

Üst bardaki ortak hız çubuğu (**Dur · 0,5x · 1x · 2x · 3x**), simülasyon saati ve onay penceresi açan **Sıfırla** düğmesi tüm ekranlarda görünür. Tekliflerin açık ihalede gizliliği CSS ile değil, API veri modeliyle sağlanır.

## Frontend notları

- Angular 21, `bootstrapApplication` çağrısında **zone.js yüklü olsa bile zoneless change detection** kullanır. Bu uygulama RxJS abonelikleri, `timer` ve HTTP geri dönüşleriyle klasik biçimde yazıldığı için `app.config.ts` içindeki `provideZoneChangeDetection({ eventCoalescing: true })` zorunludur. Bu sağlayıcı kaldırılırsa veri gelir ama ekran güncellenmez.
- `src/index.html` içindeki `<base href="/">` sayesinde `/tenders/7` gibi derin bağlantılar ve o sayfada F5 doğrudan çalışır.
- Üretim derlemesi içerik hash'li dosya üretir (`main-XXXXXXXX.js`); Nginx `index.html` için `Cache-Control: no-cache` döner.
- Grafikler bağımlılıksız SVG bileşenidir (`shared/line-chart.component.ts`); renk + çizgi deseni + işaretçi şekli birlikte kullanılır.

## Kabul kontrol listesi

Her madde, yanında yazan komut/doğrulama ile çalıştırıldı.

1. **PASS** — Depo sınırı: `check_capacity` birim testleri; canlı API'de 6 tonluk ihale `422 CAPACITY_EXCEEDED` ("Boş kapasite: 5166.502 kg"), daraltılmış kapasitede 1.000 kg kabul `422 CAPACITY_EXCEEDED` ("Boş kapasite: 500.000 kg").
2. **PASS** — Yalnızca kullanıcı ihale açar: `engine.py` içinde `_open_needed_tenders` ve `_evaluate_tender` yok; ürünler 0 kg stoğa düşerken kendiliğinden ihale oluşmadı (yalnızca elle açılanlar listelendi).
3. **PASS** — Teklif gizliliği ve kabul: `OPEN` yanıtında fiyat/miktar alanları yok; `EVALUATION`'da teklifler görünür; UI'da 500 kg kısmi kabul sonrası satır `Kısmi kabul 500 kg` oldu ve aynı teklife ikinci kabul `409 OFFER_ALREADY_ACCEPTED` döndü.
4. **PASS** — Çoklu NPC: 800 kg + kısmi kabullerle toplam kabul ≤ istenen miktar; `remaining_need_kg` ve `accepted_total_kg` yanıtlarda doğrulandı.
5. **PASS** — Nakliye: hariç teklif `AWAITING_CARRIER` doğdu, nakliyeci atanınca `IN_TRANSIT` oldu, teslim `max(hazırlık, atama) + taşıma` anında gerçekleşti ve maliyet `landed_cost_tl` olarak yazıldı.
6. **PASS** — Seed: mevcut veritabanında `python -m app.seed` sonrası 10 NPC, 30 kural, 4 nakliyeci; ikinci çalıştırma yeni kayıt eklemedi (idempotent).
7. **PASS** — Hız: 10 sn'de 3x → 29,23 sim sn, 0,5x → 4,98 sn, Dur → 0,00 sn; backend restart sonrası `speed=2.00` korundu ve simülasyon duraklatıldı.
8. **PASS** — Maliyet: teslimat sonrası ortalama maliyet 13,00 → 12,084493 TL/kg düştü, stok değeri arttı; `/stock-metrics/history` noktaları üretildi.
9. **PASS** — Testler/derleme: `pytest -q` 19 passed; `npm test` (üretim derlemesi) başarılı; 6 route headless Chrome'da hatasız render edildi.
10. **PASS** — Migration: dolu veritabanında `alembic upgrade head` çalıştı; backfill (kapasite/maliyet) uygulandı, veri kaybı olmadı.
11. **PASS** — Birim fiyat korunması: stok 0 iken MISR `avg_cost_per_kg=8.360075` ve `last_purchase_unit_price=8.360075` döndü (0 değil); 1.000 kg teslim alınınca ikisi de 9,060270 oldu; depo boşken toplam birim fiyat `_last_known_avg` ile korunuyor (birim testi).
12. **PASS** — Sıfırlama: 24 ihale ve 4 award varken `POST /simulation/reset` sonrası ihale/teslimat/geçmiş 0, ürünler 900/700/3000 kg ve 8,75/7,75/13,00 TL/kg'a döndü, saat 0, hız 1x, durum duraklatıldı. Arayüzde Sıfırla → onay penceresi → "Vazgeç" kapatıyor, "Evet, sıfırla" sonrası sayfa `/` adresine dönüp 0,0 sn gösteriyor.

## Veri kalıcılığı

`docker compose down` container'ları durdurur, `db_data` volume'unu korur. `docker compose down -v` volume'u siler ve yalnız temiz başlangıç gerektiğinde kullanılmalıdır.

## Bilinen notlar

- Eski demo verileri (otomatik açılmış ihaleler, 3 NPC'lik kural seti) volume'da kalabilir; seed eklemeli çalıştığı için bunlar silinmez. Temiz bir demo için kullanıcı kontrollü `docker compose down -v` sonrası yeniden başlatın.
- Eski ihalelerin `evaluate_at_seconds` ve `winning_participation_id` alanları geriye dönük uyumluluk için durur, yeni akışta kullanılmaz.
- Nakliye hariç bir award, nakliyeci atanmadan teslim edilmez ve boş kapasiteyi işgal etmeye devam eder.
