# SPEC v1.0 — İnceleme Bulguları

Tarih: 2026-08-26. Kaynak: `SPEC.md` — bulgular v1.0 üzerinde çıkarıldı, B1–B5 v1.1'e işlendi.
Durum kolonu: ⬜ açık · ✅ spec'e işlendi.

## Bloke edici — 1. oturumdan (İskelet) önce çözülmeli · **hepsi SPEC v1.1'e işlendi**

| # | Bulgu | Etki | Durum |
|---|-------|------|-------|
| B1 | `Event` üzerinde dedup anahtarı yok; §4'ün "aynı olayı iki kez üretme" kuralı şema düzeyinde uygulanamaz. Ayrıca `collect()`'in döndürdüğü nesneleri kimin kaydettiği tanımsız. | Çift brifing maddesi, çift ProposedAction | ✅ |
| B2 | `ModuleContext` içinde DataSource erişimi yok; `collect()` kimlik bilgisine ve `sync_cursor`'a ulaşamıyor. | Modüller çekirdek modellerine doğrudan uzanır, §4 sözleşmesi ilk oturumda delinir | ✅ |
| B3 | `on_event` dağıtım kuralı tanımsız — modülün hangi event tiplerine abone olduğu bildirilmiyor. | Her modül her event'i alır; gereksiz LLM çağrısı | ✅ |
| B4 | §9'daki "`gmail.compose` ile gönderme izni istenmez" ifadesi yanlış: Google'da taslak-only scope yoktur, `gmail.compose` `messages.send`'i de kapsar. | Güvenlik iddiası gerçeği yansıtmıyor | ✅ |
| B5 | Google OAuth "test mode"da refresh token 7 günde geçersizleşir; MVP bitti tanımı tam olarak "7 ardışık sabah". | MVP kabul kriteri kendi altyapısıyla çakışıyor | ✅ |

**Uygulanan çözümler** (SPEC v1.1)

- B1: `Event.dedup_key` (CharField) + `unique_together = (entity, type, dedup_key)`. `collect()` kaydedilmemiş instance döner, çekirdek `get_or_create` ile yazar. Aynı desen `ProposedAction` için de geçerli.
- B2: `ModuleContext`'e `sources(kind) -> list[DataSource]` ve `cursor_commit(source, cursor)` eklenir. Modül DB'ye doğrudan dokunmaz.
- B3: `ModuleBase.subscribes: list[str]` sınıf alanı (glob destekli, ör. `"email.*"`). Çekirdek dağıtımı buna göre yapar.
- B4: Scope listesi olduğu gibi bırakılır, ancak kısıt kod düzeyinde ifade edilir: executor yalnızca `drafts.create` çağırır, `messages.send` çağrısı yasaklı (test ile korunur) ve her çağrı AuditLog'a yazılır. Spec metni bu gerçeği yansıtacak şekilde düzeltilir.
- B5: 5. oturuma token sağlık kontrolü + süre dolduğunda Telegram üzerinden yeniden yetkilendirme bağlantısı dahil edilir. Alternatif: MVP kabul kriteri "7 sabah" yerine "7 brifing (yeniden yetkilendirme sayılmaz)".

## Önemli — açık

| # | Bulgu | Öneri |
|---|-------|-------|
| Ö1 | Bütçe tavanı aşılınca brifing hiç gitmiyor; tek arayüz susuyor. Ayrıca maliyet çağrıdan sonra yazıldığı için tavan kontrolü yarış koşuluna açık. | Degrade modu: TIER_FRONTIER sentezi atlanır, bölümler ham gönderilir + uyarı satırı. Tavan kontrolü ön-tahmin + atomic increment ile. |
| Ö2 | Çelişki kontrolü iki yerde tarif edilmiş: §5 write-time (TIER_SMALL), §6 gece batch taraması. | Write-time yalnızca ucuz benzerlik flag'i; çözüm `memory_maintenance` içinde batch. |
| Ö3 | `VectorField(dimensions=1536)` koda gömülü — tier soyutlamasını kırar, model değişimi tam re-embed gerektirir. | `MemoryItem.embedding_model` alanı + boyut ayardan okunur. |
| Ö4 | Webhook güvenliği tanımsız: Telegram `secret_token` header'ı ve Shopify HMAC doğrulaması §9'da yok. | Her iki webhook için imza doğrulaması zorunlu; beyaz liste chat_id tek başına yeterli değil. |
| Ö5 | Executor kayıt yeri belirsiz — `email.reply_draft` Gmail'e bağlı, ama modüller birbirini import edemez ve ApprovalService modülü bilmemeli. | `core/services/executors.py` registry; modül kendi executor'ını kayıt eder. §2 dizin yapısına eklenir. |

## Küçük — açık

- `FeedbackSignal` üzerinde unique kısıt yok → çift 👍 çift kayıt üretir.
- `decay()`: `last_used_at` NULL (hiç kullanılmamış) kayıtlar için davranış tanımsız.
- Beat sabit saat zinciri kırılgan: 06:30 senkronu uzarsa 07:35 bayat veriyle brifing kurar. Chain/chord kullanılmalı, 08:00 teslimi her hâlükârda garanti.
- `Entity.settings` şemasız; "config değişikliği kod değişikliği gerektirmez" ilkesi için doğrulayıcı bir dataclass gerekir.
- Fernet anahtar rotasyonu için `credentials_enc` zarfına `key_version` şimdiden eklenmeli (maliyeti sıfır).
- Beat sabit `Europe/Istanbul`; `Entity.timezone` alanı kullanılmıyor. MVP için kabul, şirket varyantında kırılır.

## Test borcu — açık

§12 her serviste birim test istiyor, ancak en yüksek riskli özellik olan idempotency için test yok.
Her modülün geçmek zorunda olduğu ortak bir `ModuleContractTestCase` önerilir:

- `collect()` iki kez çağrılınca ikinci çağrı 0 yeni Event üretir
- `briefing_contribution()` veri yokken `None` döner, patlamaz
- `propose_actions()` hiçbir dış yan etki üretmez (executor çağrılmaz)
