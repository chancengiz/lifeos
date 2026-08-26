# İnceleme ve Açık Riskler

Kaynak: `SPEC.md` v2.0. Son güncelleme: 2026-08-26.

---

## Bölüm A — v1.0 incelemesinde bulunanlar (kapandı)

Bloke edici bulgular v1.1'de, önemli/küçük bulguların çoğu v2.0 yeniden yazımında kapandı.

| # | Bulgu | Nerede kapandı |
|---|---|---|
| B1 | `Event`'te dedup anahtarı yok, kayıt sorumluluğu tanımsız | v1.1 — §3 `dedup_key` + unique kısıt, §4 kayıt çekirdekte |
| B2 | `ModuleContext` DataSource'a erişemiyor | v1.1 — §4 `sources()` / `cursor_commit()` |
| B3 | `on_event` dağıtım kuralı yok | v1.1 — §4 `subscribes` |
| B4 | `gmail.compose` gönderme izni verir, spec aksini iddia ediyordu | v1.1 — §9; v2.0'da taslak akışı MVP dışına alındığı için scope hiç istenmiyor |
| B5 | Test mode refresh token 7 günde düşüyor, MVP kriteriyle çakışıyor | v1.1 — §10/5; v2.0 §13/10 |
| Ö1 | Bütçe aşımında brifing hiç gitmiyor; tavan kontrolü yarışa açık | v2.0 §8 — ön-tahminli atomik kontrol + degrade modu |
| Ö2 | Çelişki kontrolü hem write-time hem gece batch olarak tarif edilmiş | v2.0 §8 — write yolunda LLM yok, çözüm gece batch'te |
| Ö3 | Embedding boyutu koda gömülü, model değişimi izlenemiyor | v2.0 §3.2 — `MemoryItem.embedding_model` |
| Ö4 | Webhook imza doğrulaması tanımsız | v2.0 §12 — Telegram `secret_token`, Shopify HMAC |
| Ö5 | Executor kayıt yeri belirsiz | v2.0 §2 + §8 — `core/services/executors.py` |
| K1 | `FeedbackSignal` unique kısıtı yok, çift 👍 çift kayıt | v2.0 §3.6 |
| K2 | `decay()` `last_used_at IS NULL` için tanımsız | v2.0 §8 |
| K3 | Sabit saat beat zinciri kırılgan | v2.0 §9 — chain/chord, 08:00 teslimi garanti |
| K4 | `Entity.settings` şemasız | v2.0 §3.1 — dataclass doğrulaması |
| K5 | Fernet anahtar rotasyonu yok | v2.0 §12 — `{key_version, ciphertext}` zarfı |

**Açık kalan tek eski madde:** beat sabit `Europe/Istanbul`, `Entity.timezone` kullanılmıyor. MVP tek kullanıcı olduğu için kabul; çok entity'li kullanımda kırılır.

---

## Bölüm B — v2.0'ın getirdiği yeni riskler (açık)

Yeni kapsam yeni risk getirdi. Bunlar spec'te ele alındı ama **kanıtlanmadı** — kod ve testle kapanacaklar.

| # | Risk | Neden ciddi | Ne zaman kapanır |
|---|---|---|---|
| R1 | **Injection savunması iddia, henüz kanıt değil** | §12'deki zarf kuralı doğru ama etkinliği ancak saldırı testiyle bilinir. İnternete çıkan + ajanla konuşan sistemde bu birincil tehdit | 7. oturum — savunma testleri geçmeden oturum kapanmaz |
| R2 | **Yanlış maruziyete bağlama** | Gerekçe zorunluluğu (§0/7) bağlantısız iddiayı keser ama LLM **yanlış** `ExposureItem`'ı seçebilir; sonuç yine kendinden emin ve yanlış olur | 8. oturum — finding'lerin insan doğrulamalı örneklemi |
| R3 | **Soğuk başlangıç: `adjacent` şeridi boş harita üstünde çalışamaz** | İlk haftalarda `InterestNode` yok; komşu-alan seçimi anlamsız çıktı üretir | 9. oturum — `self_model` çıktısı yeterli değilse şerit payları geçici olarak `random` lehine kaydırılmalı |
| R4 | **`counter` şeridi `Stance` kaydı yoksa atıl** | Kullanıcı pozisyon girmezse karşı-görüş şeridi boş döner ve yankı kırıcı işlevi sessizce kaybolur | 9. oturum — `Stance` boşsa şerit devre dışı bırakılıp kullanıcıya bildirilmeli, sessiz geçilmemeli |
| R5 | **`random` şeridinin kaynak havuzu tanımsız** | "Tamamen ilişkisiz" nasıl örneklenecek belirsiz. Kötü havuz = gürültü = kullanıcının keşif bölümünü okumayı bırakması | 9. oturum — havuz tanımı ve örnekleme yöntemi kararı |
| R6 | **Mesh yerel taşımada izolasyon gerçek değil** | İki entity aynı DB'de; `ShareContract` fiilen kendi kendine uyguladığı bir kural. Gerçek sınır ancak uzak taşımada oluşur | 15–16. oturum — redaksiyon testleri sınırı kod düzeyinde kanıtlamalı; gerçek izolasyon V1 |
| R7 | **Token muhasebesi çift sayım riski** | `ResearchTask.tokens_used` ve `LLMUsage` aynı harcamayı iki yerde tutuyor; bütçe kontrolü yanlış tarafa bakarsa tavan delinir | 6. oturum — tek kaynak `LLMUsage`, task alanı türev olmalı |
| R8 | **Maliyet bandı ölçülmedi** | 20–40 USD/ay tahmindir. Açık uçlu araştırma tavanlara rağmen beklenenden pahalı çıkabilir | 8–9. oturum sonrası ilk gerçek ölçüm; sapma varsa tavanlar sıkılır |
| R9 | **Mesh n=2'de bağlantı arama değeri üretmez** | Protokol doğru olsa da "fayda sağlayacak bağlantı bulma" ağ büyümeden çalışmaz. MVP bunu kanıtlayamaz, yalnızca mekanizmayı kanıtlar | Ağ büyüdüğünde; MVP kabul kriteri buna göre yazıldı (§13) |

---

## Bölüm C — Test borçları

- `ModuleContractTestCase` — §4'te sözleşme olarak yazıldı, kod olarak yazılmadı (1. veya 5. oturum)
- Injection saldırı test seti — R1 (7. oturum)
- Redaksiyon sınır testleri — R6 (15. oturum)
- Bütçe tavanı yarış testi — Ö1 kapandı ama eşzamanlı çağrı testi yok (2. oturum)
