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

## İzole geliştirme ortamı

Ana demo ortamına (8080) dokunmadan ikinci bir stack çalıştırmak için:

```powershell
Copy-Item .env.dev.example .env.dev
docker compose -p yem-dev --env-file .env.dev up -d --build
```

- Arayüz: http://localhost:18080
- API: http://localhost:18000
- Veritabanı: `yem_simulation_dev`, kendi volume'u: `yem-dev_db_data`

Proje adı (`-p yem-dev`) sayesinde container'lar, ağ ve volume'lar ana ortamdan ayrıdır; ana demo http://localhost:8080 üzerinde çalışmaya devam eder. Kapatmak için:

```powershell
docker compose -p yem-dev down -v
```

`-v` dev veritabanını da siler. Ana ortamı yeniden derlerken `Developer` dalında olun; aksi hâlde ana stack, üzerinde çalışılan dalın kodunu derler.

## Katmanlar

- `backend/`: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 senkron, PyMySQL, Alembic.
- `frontend/`: Angular 21 standalone, Reactive Forms, HttpClient, Türkçe yönetici arayüzü.
- `compose.yaml`: MariaDB 11.4, backend ve Nginx servisleri.
- `backend/migrations/`: iki migration (ilk şema + manuel ihale/kapasite/nakliye/maliyet).
- `backend/app/simulation/`: saf iş kuralları, NPC teklif üretimi ve kronolojik tick motoru.

Backend ve MariaDB host portu açmaz; yalnız Nginx 127.0.0.1:8080 üzerinden yayın yapar (yerelde backend ayrıca 127.0.0.1:8000'de dinler). Backend tek Uvicorn worker ile çalışır.

## Zaman ölçeği

Simülasyon saati gerçek zamandan bağımsız, hızlandırılmış bir takvimle gösterilir:

- 1 sim günü = 30 saniye, 1 ay = 30 gün = 900 saniye, 1 yıl = 12 ay = 10.800 saniye.
- Simülasyon süresi `X yıl Y ay Z gün SS:DD:SS` biçiminde gösterilir (üst bar kısa, Özet tam biçim).
- Mevsim döngüsü bir sim yılıdır (10.800 sn); yani her mevsim ~2.700 sn sürer ve timeline otomatik ilerler.
- Bütçe dönemi bir sim ayıdır (900 sn).
- Demo başlangıcı 1.750 sn'dir (1 ay 28 gün); geçmiş alımlar bu tarihten öncedir.

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
- **Fire:** Her ürünün `loss_percent` oranı vardır (MISR %1, ARPA %0,5, SOYA %1,5). Teslimatta kabul edilen kg `quantity × (1 − fire)` olur; ödenen tutar değişmediği için **birim maliyet yükselir**. Fire miktarı award'da `loss_kg` olarak saklanır.
- **Mevsimsellik:** Mevsim ilerlemesi (`simulation_state.season_progress`, 0–1) simülasyon zamanıyla yavaşça artar (1 sim saati = 1 yıl) ve üst bardaki **mevsim timeline'ından sürüklenerek** elle değiştirilebilir. Her ürünün `season_amplitude` genliği vardır; teklif fiyatı `1 + genlik × sin(2π ilerleme + faz)` katsayısıyla üretilir ve teklifte `season_factor` olarak saklanır. Böylece aynı NPC farklı mevsimlerde farklı fiyat verir.
- **Bütçe:** Aylık (900 sim saniyelik dönem) satın alma limiti `budgets` tablosunda tutulur (varsayılan 500.000 TL). Dönem harcaması, kabul edilen award'ların maliyetiyle hesaplanır; %80'de uyarı, limit aşımında teklif kabulü `422 BUDGET_EXCEEDED` ile reddedilir. Limit `PATCH /budget` ile (simülasyon duraklatılmışken) değiştirilir.
- **Backend yeniden başlarsa** simülasyon duraklatılır; kapalı gerçek zaman tüketim olarak yazılmaz.
- **Sıfırlama:** `POST /simulation/reset` tüm ihaleleri, teklifleri, award'ları ve stok geçmişini siler; ürün, NPC kuralı ve nakliyeci değerlerini seed başlangıç değerlerine döndürür; ardından **demo geçmişini** (5 tamamlanmış ihale, award'ları ve stok geçmişi) yeniden yükler. Saat demo geçmişinin bittiği ana (1.750 sn = 1 ay 28 gün) alınır, mevsim İlkbahar'a döner, hız 1x olur ve simülasyon duraklatılır. Arayüzde üst bardaki **Sıfırla** düğmesi onay penceresi gösterir; onaylanınca sayfa yenilenir. İşlem geri alınamaz.

## Maliyet hesabı

- Teslim maliyeti: `landed_cost_tl = quantity_kg/1000 * (NPC TL/ton + nakliyeci TL/ton)`.
- Ortalama maliyet: `(stok*ortalama + eklenen_toplam_maliyet) / (stok + eklenen_kg)`, 6 basamak.
- **Son alım birim fiyatı:** teklif kabul edildiği anda `unit_price_per_ton / 1000` olarak saklanır (`products.last_purchase_unit_price`); **nakliye hariç mal fiyatıdır** ve teklif fiyatlarıyla birebir karşılaştırılabilir. Stok sıfıra düşse bile bu alan ve ortalama maliyet **korunur**; birim fiyat 0'a inmez. Depo tamamen boşken toplam birim fiyat, ürünlerin son bilinen birim fiyatlarının ortalaması olarak gösterilir.
- **Alım istatistikleri:** `GET /purchase-stats` her ürün için son alım, en ucuz alım, en pahalı alım ve miktar ağırlıklı ortalama alım fiyatını (TL/kg) döner. İhale listesinin üstündeki kompakt bar bu değerleri tüm ürünler için gösterir.
- Stok değeri: `stok * ortalama maliyet` (stok yoksa 0 TL; fiyat bilgisi ayrı alanda korunur).
- Her tick sonunda ve her teslimattan hemen sonra tüm ürünler için **aynı `elapsed_seconds`** ile `stock_snapshots` satırı yazılır. Ürün başına yaklaşık 3000 nokta tutulur; daha eskiler seyrek bir DELETE ile silinir. `GET /stock-metrics/history?limit=300` noktaları eşit aralıklı örnekler.

## API özeti

`/api/v1` altında:

- `GET /health`
- `GET|POST /simulation`, `/simulation/start`, `/simulation/pause`, `/simulation/speed`, `/simulation/season`, `/simulation/reset`
- `GET /products`, `PATCH /products/{id}` (kapasite, ortalama maliyet ve son alım birim fiyatı dahil)
- `GET /npc-rules?product_id=`, `PATCH /npc-rules/{id}` (nakliye modu, mevcut miktar aralığı dahil)
- `GET /tenders?product_id=&status=`, `POST /tenders`
- `GET /tenders/{id}`, `POST /tenders/{id}/accept`, `POST /tenders/{id}/finalize`
- `GET /tenders/{id}/offers`
- `GET /carriers`, `GET /shipments?status=`, `POST /shipments/{award_id}/assign-carrier`
- `GET /stock-metrics`, `GET /stock-metrics/history?limit=`
- `GET /purchase-stats`
- `GET|PATCH /budget`
- `GET /supplier-scores`
- `GET /notifications`

Decimal değerler JSON'da dizge olarak döner. Liste yanıtları `{items:[...]}`, hatalar `{error:{code,message}}` biçimindedir.

## Seed verisi

Entrypoint sırası:

1. `alembic upgrade head`
2. `python -m app.seed`
3. Tek Uvicorn worker

Seed **eklemelidir**: mevcut kayıtları ve ayarları değiştirmez, yalnızca eksikleri ekler.

- 3 ürün (MISR 5000 kg, ARPA 4000 kg, SOYA 6000 kg kapasite; 8,75 / 7,75 / 13,00 TL/kg ortalama maliyet; fire %1 / %0,5 / %1,5; mevsim genliği %8 / %6 / %10).
- **Demo geçmişi:** veritabanı boşsa (ilk kurulum veya sıfırlama sonrası) 300–1500 sn aralığında tamamlanmış **5 ihale**, teklifleri, award'ları ve stok geçmişi eklenir. Böylece kullanıcı ilk açılışta ürünlerin son/en ucuz/en pahalı/ortalama alım fiyatlarını görür. Geçmiş doluysa seed dokunmaz.
- 1 bütçe kaydı (`YEM-HAM`, aylık 500.000 TL).
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
- `/tenders`: İhale Listesi — üstte **tüm ürünlerin alım fiyatı barı** (son / en ucuz / en pahalı / ortalama), **yeni ihale açma paneli** (önerilen miktar ve boş kapasite ile), filtreler, kabul özeti.
- `/tenders/:id`: İhale Detayı — üstte **kompakt stok şeridi** (depo doluluğu, yoldaki miktar, boş kapasite, **son alım birim fiyatı**, ortalama maliyet), gizli teklifler, **teklif kabul tablosu (kısmi miktar)**, her teklifte son alıma göre **yeşil ▲ (daha ucuz) / kırmızı ▼ (daha pahalı)** işareti, "İhaleyi tamamla", teslimat/award listesi.
- `/shipping`: Nakliye — nakliyeci bekleyenler, nakliyeci seçimi ve maliyet/teslim önizlemesi, yoldakiler ve teslim edilenler, nakliyeci listesi.
- `/suppliers`: Tedarikçiler — NPC performans skorları (fiyat rekabeti, katılım, kazanma oranı, ortalama teslim süresi).

Üst bardaki ortak hız çubuğu (**Dur · 0,5x · 1x · 2x · 3x**), simülasyon saati, onay penceresi açan **Sıfırla** düğmesi ve **bildirim zili** (okunmamış sayacı + panel) tüm ekranlarda görünür. Üst bar ve altındaki **mevsim timeline'ı** sayfa kaydırıldığında sabit kalır (sticky); timeline sürüklenerek mevsim (İlkbahar/Yaz/Sonbahar/Kış) değiştirilebilir. Tekliflerin açık ihalede gizliliği CSS ile değil, API veri modeliyle sağlanır.

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
12. **PASS** — Sıfırlama: `POST /simulation/reset` sonrası tüm eski ihaleler silindi, yerine 5 demo ihalesi (300–1500 sn, DELIVERED) geldi; ürünler 900/700/3000 kg ve 8,75/7,75/13,00 TL/kg'a döndü, saat 1.750 sn ("1 ay 28 gün 08:00"), mevsim İlkbahar, hız 1x, durum duraklatıldı.
13. **PASS** — Alım barı ve yön işaretleri: `GET /purchase-stats` demo geçmişiyle MISR 8,90/8,60/8,90/8,736, ARPA 7,90/7,60/7,90/7,733 ve SOYA 13,00 döndü; teklif ekranında son alıma göre yeşil ▲ / kırmızı ▼ işaretleri render edildi (headless Chrome DOM).
14. **PASS** — Demo geçmişi: sıfırlama sonrası ihale listesinde 5 tamamlanmış ihale, `purchase-stats`'ta 2/2/1 alım ve `stock-metrics/history`'de 11 nokta oluştu; ilk açılışta alım fiyatı barı dolu geliyor.
15. **PASS** — Fire: 500 kg'lık teslimat %1 fire ile 495 kg kabul edildi (`loss_kg=5`), ortalama maliyet 8,75 → 8,794 TL/kg yükseldi; `stock-metrics.total_loss_kg/tl` 5 kg / 43,75 TL döndü.
16. **PASS** — Mevsimsellik: teklifler açılış anındaki katsayıyla üretildi (×0,934); ürün detayında "Sezon ×0,93", teklif satırında "sezon ×0,93" göründü.
17. **PASS** — Bütçe: 500.000 TL limit, 34.990 TL harcama (%7,00), 465.010 TL kalan ve `period_index=2` döndü; limit 1.000 TL'ye çekilince 100 kg kabul `422 BUDGET_EXCEEDED` ("Kalan: 0.00 TL, bu alım: 919.33 TL") ile reddedildi.
18. **PASS** — Tedarikçi skorcard: 10 NPC için skor üretildi (NPC-A 91 … NPC-C/I 0); `/suppliers` tablosu skor çubuğu ve metriklerle render edildi.
19. **PASS** — Bildirim kutusu: 5 aktif bildirim (kritik stok, karar bekleyen ihale, sezon) üretildi; zil sayacı 5, panel 5 satır gösterdi, konsol hatası yok.
20. **PASS** — İzole dev ortamı: 18080/18000 ayrı stack ve ayrı veritabanı; ana demo 8080 sağlıklı kaldı.
21. **PASS** — Mevsim timeline'ı: 0,75'e sürüklendiğinde `season_progress=0.7500`, etiket "Kış" oldu ve sunucuya yazıldı; 3x hızda 10 sn'de ilerleme 0 → 0,0076 (otomatik akış); üst bar `position: sticky` doğrulandı.
22. **PASS** — Takvim gösterimi: 1.750 sn için `elapsed_display="1 ay 28 gün 08:00:00"`, kısa biçim `"1 ay 28 gün 08:00"`; grafiklerin x ekseni de aynı kısa takvim biçimini kullanıyor.

## Veri kalıcılığı

`docker compose down` container'ları durdurur, `db_data` volume'unu korur. `docker compose down -v` volume'u siler ve yalnız temiz başlangıç gerektiğinde kullanılmalıdır.

## Bilinen notlar

- Eski demo verileri (otomatik açılmış ihaleler, 3 NPC'lik kural seti) volume'da kalabilir; seed eklemeli çalıştığı için bunlar silinmez. Temiz bir demo için kullanıcı kontrollü `docker compose down -v` sonrası yeniden başlatın.
- Eski ihalelerin `evaluate_at_seconds` ve `winning_participation_id` alanları geriye dönük uyumluluk için durur, yeni akışta kullanılmaz.
- Nakliye hariç bir award, nakliyeci atanmadan teslim edilmez ve boş kapasiteyi işgal etmeye devam eder.
- Bildirim kutusunda "okundu" durumu tarayıcıda (`localStorage`) tutulur; kullanıcı/oturum yönetimi (A1) eklendiğinde sunucu tarafına taşınmalıdır.
- Bütçe dönemi demo için 3600 sim saniyedir (1 sim saati = 1 ay). Gerçek takvim entegrasyonu kapsam dışıdır.
