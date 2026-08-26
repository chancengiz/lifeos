# LIFE OS — Kişisel AI İkiz MVP — Teknik Spesifikasyon v1.1

> Bu dosya Claude Code için proje talimatıdır. Oturum planı §10'dadır; her oturumda tek bölüm inşa edilir, çekirdek sözleşmeler (§4) asla modül eklerken değiştirilmez.

**v1.1 değişiklikleri** — `REVIEW.md` B1–B5 bloke edici bulguları işlendi. Kod yazılmadı, yalnızca sözleşme ve şema netleştirildi:

- **B1** — `Event.dedup_key` + unique kısıt; kayıt sorumluluğu çekirdeğe verildi (§3, §4)
- **B2** — `ModuleContext.sources()` / `cursor_commit()` kapıları (§4)
- **B3** — `ModuleBase.subscribes` olay abonelik bildirimi (§4)
- **B4** — `gmail.compose` scope'unun gerçek yetkisi ve kod düzeyi kısıtı (§9)
- **B5** — test mode refresh token 7 gün ömrü: yeniden yetkilendirme akışı (§10)

Açık kalan bulgular (Ö1–Ö5 önemli, 6 küçük, test borçları) `REVIEW.md` içinde izlenir.

---

## 0. Vizyon ve MVP Kapsamı

**Ürün:** Bir varlığın (kişi veya şirket) verilerini toplayan, kalıcı hafıza tutan, her sabah Telegram'dan brifing veren ve aksiyonları yalnızca onayla yürüten proaktif ajan çekirdeği.

**MVP kapsamı (tek kullanıcı, kendi kullanımım):**
- Google Calendar + Gmail (readonly, test mode) senkronizasyonu
- Shopify + Meta Ads operasyon anomalileri (e-ticaret modülü)
- Sabah 08:00 Telegram brifingi
- Onay merkezi (mail cevap taslakları dahil her aksiyon önerisi Telegram inline butonlarıyla onaylanır)
- Geri bildirim sinyalleri (👍/👎)

**MVP dışı (yuva bırakılır, kod yazılmaz):** WhatsApp, ajan-ajan iletişimi, avatar/ses, finans portföy modülü, çok kullanıcılı SaaS katmanı.

**Temel ilkeler (ihlal edilemez):**
1. Karar desteği, otonom otorite değil — sonuç doğuran her aksiyon `ProposedAction` üzerinden geçer.
2. Çekirdek "user" değil "entity" bilir — kişi ve şirket aynı soyutlamadır.
3. Modüller birbirine değil çekirdeğe bağlanır (§4 sözleşmesi).
4. LLM sağlayıcısı koda gömülmez — tier alias'ları üzerinden çağrılır (§7).
5. Her hafıza kaydında kaynak (provenance) ve güven skoru zorunludur.
6. Günlük LLM bütçe tavanı aşılırsa sistem durur ve uyarır, sessizce harcamaz.

---

## 1. Stack

| Katman | Seçim | Not |
|---|---|---|
| Dil / Framework | Python 3.12, Django 5.x | HesapKitap ile aynı desen |
| DB | PostgreSQL 16 + pgvector | embedding'ler için `vector` kolonu |
| Kuyruk / Zamanlama | Celery + Redis, celery-beat | |
| Bot / Arayüz | python-telegram-bot (webhook modu) | MVP'de tek arayüz Telegram; web UI sonra |
| LLM erişimi | litellm kütüphanesi, kendi `LLMService` sarmalayıcımızın arkasında | sağlayıcı-bağımsızlık |
| Google | google-api-python-client, OAuth (test mode) | scope'lar §9'da; test mode refresh token 7 günde düşer (§10/5). Doğrulama/CASA V1'e ertelendi |
| Shopify | Admin GraphQL API | mevcut mağaza token'ı |
| Meta Ads | Marketing API (insights, readonly) | |
| Deploy | Docker Compose, tek VPS | web + worker + beat + postgres + redis |
| Secrets | .env + at-rest şifreleme (Fernet) | OAuth token'ları DB'de şifreli |

---

## 2. Dizin Yapısı

```
lifeos/
  core/            # entity, event, memory, briefing, approval, llm servisleri
    models.py
    services/
      memory.py
      llm.py
      briefing.py
      approval.py
      events.py
    tasks.py       # çekirdek celery görevleri
  modules/
    base.py        # ModuleBase sözleşmesi (§4)
    calendar_mod/
    email_triage/
    ecom_ops/
    world_digest/
  integrations/    # dış API istemcileri (google, shopify, meta, telegram)
  bot/             # telegram webhook + komutlar + inline buton handler'ları
  config/          # settings, llm_tiers.yaml, module_registry.py
```

---

## 3. Veri Modeli (core/models.py)

```python
class Entity(models.Model):
    kind = models.CharField(choices=[("person","person"),("company","company")])
    name = models.CharField(max_length=200)
    timezone = models.CharField(default="Europe/Istanbul")
    settings = models.JSONField(default=dict)   # brifing saati, bütçe tavanı vb.

class EntityMember(models.Model):               # şirket varyantı için şimdiden
    entity = FK(Entity); user = FK(User)
    role = models.CharField(choices=[("owner","owner"),("member","member")])

class DataSource(models.Model):
    entity = FK(Entity)
    kind = models.CharField(choices=[("gmail",...),("gcal",...),("shopify",...),
                                     ("meta_ads",...),("telegram",...),("rss",...)])
    credentials_enc = models.BinaryField(null=True)   # Fernet ile şifreli
    sync_cursor = models.JSONField(default=dict)      # historyId, since_id vb.
    status = models.CharField(default="active")
    last_sync_at = models.DateTimeField(null=True)

class Event(models.Model):
    entity = FK(Entity); source = FK(DataSource, null=True)
    type = models.CharField(max_length=100)   # "email.received", "order.created",
                                              # "ads.anomaly", "calendar.upcoming"...
    dedup_key = models.CharField(max_length=200)      # B1: kaynağın kendi kalıcı
                                                      # kimliği (gmail message id,
                                                      # shopify order gid, gcal
                                                      # event id). Zaman damgası
                                                      # veya hash üretilmez.
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    processed = models.BooleanField(default=False)
    class Meta:
        indexes = [Index(fields=["entity","processed","occurred_at"])]
        constraints = [UniqueConstraint(fields=["entity","type","dedup_key"],
                                        name="uniq_event_dedup")]

class MemoryItem(models.Model):
    entity = FK(Entity)
    kind = models.CharField(choices=[("episodic",...),("semantic",...),
                                     ("relationship",...),("goal",...)])
    content = models.TextField()
    embedding = VectorField(dimensions=1536)
    source_event = FK(Event, null=True)
    provenance = models.CharField(max_length=200)     # zorunlu, boş geçilemez
    confidence = models.FloatField()                  # 0.0–1.0
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True)
    superseded_by = FK("self", null=True)             # çelişki çözümü zinciri
    last_used_at = models.DateTimeField(null=True)    # decay için

class Briefing(models.Model):
    entity = FK(Entity); date = models.DateField()
    sections = models.JSONField()      # [{module,title,items:[{text,ref,feedback}]}]
    delivered_at = models.DateTimeField(null=True)
    telegram_message_id = models.BigIntegerField(null=True)

class ProposedAction(models.Model):
    entity = FK(Entity)
    module = models.CharField(max_length=50)
    action_type = models.CharField(max_length=100)    # "email.reply_draft" vb.
    dedup_key = models.CharField(max_length=200)      # B1: aynı öneri iki kez
                                                      # onaya düşmez; genelde
                                                      # tetikleyen Event'in
                                                      # dedup_key'i
    payload = models.JSONField()                      # taslak içerik, hedef, bağlam
    risk_level = models.CharField(choices=[("low",...),("medium",...),("high",...)])
    status = models.CharField(default="pending",
        choices=[("pending",...),("approved",...),("edited",...),
                 ("rejected",...),("executed",...),("failed",...)])
    decided_at = models.DateTimeField(null=True)
    decision_note = models.TextField(blank=True)      # kullanıcının edit'i buraya
    class Meta:
        constraints = [UniqueConstraint(fields=["entity","action_type","dedup_key"],
                                        name="uniq_action_dedup")]

class ActionPolicy(models.Model):                     # otonomi merdiveni
    entity = FK(Entity)
    action_type = models.CharField(max_length=100)
    mode = models.CharField(default="draft",
        choices=[("suggest",...),("draft",...),("auto_candidate",...),("auto",...)])
    window_stats = models.JSONField(default=dict)     # {"last_50_approved_clean": 47}

class FeedbackSignal(models.Model):
    entity = FK(Entity)
    target_type = models.CharField(choices=[("briefing_item",...),("draft",...)])
    target_ref = models.CharField(max_length=200)
    signal = models.CharField(choices=[("up",...),("down",...),("edited",...)])

class AuditLog(models.Model):                         # yürütülen her aksiyon
    entity = FK(Entity)
    action = FK(ProposedAction, null=True)
    summary = models.CharField(max_length=300)
    detail = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class LLMUsage(models.Model):                         # bütçe takibi
    entity = FK(Entity); date = models.DateField()
    tier = models.CharField(max_length=20)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
```

---

## 4. Modül Sözleşmesi (modules/base.py) — DEĞİŞTİRİLEMEZ ARAYÜZ

Her modül yalnızca şu dört kapıdan çekirdeğe bağlanır. Modüller birbirini import edemez; iletişim Event + Memory üzerinden.

```python
class ModuleContext:
    entity: Entity
    memory: MemoryService      # tek hafıza erişim yolu
    llm: LLMService            # tek LLM erişim yolu
    now: datetime

    # B2 — modül DataSource'a ve ORM'e doğrudan dokunmaz, bu iki kapıdan geçer.
    def sources(self, kind: str) -> list[SourceHandle]: ...
        # O kind'e ait status=="active" kaynaklar. SourceHandle yalnızca
        # {kind, cursor: dict, client: Any} taşır: credentials_enc çözülüp
        # hazır API istemcisi olarak verilir, ham token modüle gösterilmez.
        # reauth_required olan kaynak listeye girmez (§10/5).
    def cursor_commit(self, source: SourceHandle, cursor: dict) -> None: ...
        # Senkron başarıyla bittiğinde çağrılır; çekirdek DataSource.sync_cursor
        # ve last_sync_at alanlarını yazar. Kısmi başarıda ÇAĞRILMAZ — bir
        # sonraki koşu aynı yerden devam eder, mükerrerliği dedup_key keser.

class BriefingSection(TypedDict):
    module: str; title: str; order: int
    items: list[dict]          # {"text": str, "ref": str|None, "feedback_key": str}

class ModuleBase(ABC):
    key: str                   # "ecom_ops" gibi benzersiz
    subscribes: list[str] = [] # B3 — dinlenen event tipleri, glob destekli:
                               # ["email.received", "ads.*"]. Çekirdek dağıtımı
                               # YALNIZCA bu listeye göre yapar; boş liste =
                               # on_event hiç çağrılmaz. Bildirilmeyen bir tipi
                               # işlemek için listeye eklenmesi gerekir.

    def collect(self, ctx) -> list[Event]: ...
        # 1) Veri toplama: ctx.sources() üzerinden çek, KAYDEDİLMEMİŞ Event
        #    nesneleri döndür. B1 — kaydı çekirdek yapar: her Event için
        #    dedup_key zorunlu (boşsa ValueError), çekirdek get_or_create ile
        #    yazar ve mükerrer olanı sessizce atar. Modül save() çağırmaz,
        #    cursor'ı kendisi yazmaz (ctx.cursor_commit kullanır).
    def on_event(self, ctx, event: Event) -> None: ...
        # 2) Olay aboneliği: yalnızca `subscribes` ile eşleşen event'ler gelir.
        #    MemoryItem yazabilir, yeni Event döndürebilir — aynı dedup kuralı
        #    türetilen event'ler için de geçerlidir.
    def briefing_contribution(self, ctx, date) -> BriefingSection | None: ...
        # 3) Brifing katkısı: o günün bölümünü döner. Veri yoksa None —
        #    exception fırlatmaz, boş bölüm döndürmez.
    def propose_actions(self, ctx) -> list[ProposedAction]: ...
        # 4) Aksiyon önerisi: asla doğrudan yürütmez, sadece önerir.
        #    collect() ile aynı kural: kaydedilmemiş nesne döner, dedup_key
        #    zorunlu, kaydı çekirdek yapar.
```

Kayıt: `config/module_registry.py` içinde `ENABLED_MODULES = ["calendar_mod", "email_triage", "ecom_ops", "world_digest"]`. Yeni modül = yeni klasör + registry satırı. Çekirdek koduna dokunulmaz.

---

## 5. Servis Katmanı (core/services/)

**MemoryService**
- `write(entity, content, kind, provenance, confidence, source_event=None)` → embedding üretir (TIER_EMBED), benzerlik ≥0.88 olan aktif kayıt varsa çelişki kontrolü yapar (TIER_SMALL ile "aynı bilgi mi, güncelleme mi, çelişki mi?"), güncelleme ise eskiyi `superseded_by` ile kapatır.
- `search(entity, query, k=8, kinds=None)` → cosine benzerlik + recency ağırlığı; `last_used_at` günceller.
- `decay()` (haftalık görev): 90 gündür kullanılmayan, confidence <0.5 kayıtları `valid_until` ile kapatır.
- Kural: provenance boşsa yazma isteği exception fırlatır.

**LLMService**
- `call(tier, messages, entity, purpose, max_tokens)` → litellm ile `config/llm_tiers.yaml`'daki modele yönlendirir, LLMUsage'a maliyet yazar.
- Bütçe koruması: entity.settings["daily_budget_usd"] (varsayılan 0.50) aşılırsa `BudgetExceeded` fırlatır; nightly görevler bunu yakalayıp Telegram'a uyarı gönderir ve kalan işleri iptal eder.
- Tüm çağrılar loglanır (purpose alanı zorunlu — maliyet kırılımı için).

**BriefingService**
- `build(entity, date)`: enabled modüllerden `briefing_contribution` toplar → TIER_FRONTIER ile tek sentez çağrısı (bölümleri sıralar, tekrarları eler, 1 paragraf "günün özeti" yazar) → Briefing kaydı.
- `deliver(briefing)`: Telegram'a gönderir; her item'a 👍/👎 inline buton (feedback_key ile).

**ApprovalService**
- `submit(proposed_action)`: ActionPolicy'ye bakar; mode=="auto" ve risk=="low" ise doğrudan yürütür + AuditLog; değilse Telegram'a onay kartı (Onayla / Düzenle / Reddet).
- `execute(action)`: action_type'a kayıtlı executor'ı çağırır (ör. `email.reply_draft` → Gmail draft oluştur; MVP'de gönderme YOK, yalnızca draft klasörüne yazar).
- Aylık `autonomy_review` görevi: son 50 karar ≥%95 değişiksiz onay ise mode'u `auto_candidate` yapar ve kullanıcıya tek tıklık teklif gönderir. `auto`'ya geçiş yalnızca kullanıcı onayıyla.

---

## 6. Celery Görev Planı

```python
# celery beat (Europe/Istanbul)
06:30  core.nightly_sync          # tüm DataSource'lar için modül.collect()
07:10  core.process_events        # işlenmemiş Event'leri modül.on_event()'lere dağıt
07:20  core.memory_maintenance    # çelişki taraması (gece biriken), haftada 1 decay
07:35  core.build_briefings       # BriefingService.build
08:00  core.deliver_briefings
*/15m  core.critical_poll         # Gmail important + takvim <2saat hatırlatıcıları
hourly core.drain_events          # gün içi biriken event'ler
Pazar 20:00  core.weekly_jobs     # decay, (ileride: anti-echo bülteni, desen raporu)
Ay başı      core.autonomy_review
her gece     core.usage_report    # dünün LLM maliyeti brifinge küçük satır olarak
```

- Telegram: webhook (anlık). Shopify: webhook (orders/create, refunds/create) + günlük tam senkron. Gmail/GCal: polling (MVP'de Pub/Sub push kurulmaz).
- Tüm görevler idempotent. Mükerrerlik iki katmanda engellenir: `dedup_key` unique kısıtı (B1) ve `ctx.cursor_commit()` ile yalnızca başarılı senkron sonunda yazılan cursor (B2). Hata → 3 retry (exponential) → Telegram'a hata özeti.

---

## 7. LLM Yönlendirme Tablosu (config/llm_tiers.yaml)

Model adları koda yazılmaz; yalnızca tier alias'ı kullanılır. Modeller bu YAML'dan güncellenir.

| Tier | İş | Örnek görevler | Frekans |
|---|---|---|---|
| TIER_EMBED | embedding | MemoryItem yazma/arama | çok yüksek |
| TIER_SMALL | ucuz/hızlı sınıf | mail triyaj sınıflandırma, çelişki kontrolü, event etiketleme | yüksek, batch |
| TIER_MID | orta sınıf | mail cevap taslağı, anomali açıklaması, RSS özetleme | orta |
| TIER_FRONTIER | en güçlü sınıf | günlük brifing sentezi (günde 1), haftalık raporlar | düşük |

Kurallar: TIER_FRONTIER günde entity başına ≤2 çağrı. Triyaj daima batch (tek çağrıda ≤25 mail). Hedef: tek kullanıcı toplam maliyeti <3$/ay — `usage_report` bunu her gün gösterir.

---

## 8. MVP Modülleri

**calendar_mod** — GCal readonly. collect: bugünün+yarının etkinlikleri → Event. briefing: "Bugün" bölümü (saat, başlık, konum). propose_actions: yok.

**email_triage** — Gmail readonly. collect: son senkrondan beri gelen mailler → Event. on_event: TIER_SMALL batch sınıflandırma {öncelik: yüksek/orta/düşük, cevap_bekliyor: bool, kategori}; yüksek öncelikliler için MemoryItem (relationship bağlamı). briefing: "Öncelikli iletişim" (en fazla 5 madde: kimden, konu, neden önemli). propose_actions: cevap_bekliyor==True ve öncelik==yüksek → TIER_MID ile taslak → ProposedAction("email.reply_draft", risk=medium). Executor Gmail Drafts'a yazar, göndermez.

**ecom_ops** — Shopify + Meta Ads. collect: dünün siparişleri, iadeler, stok<eşik varyantlar; Meta insights (spend, ROAS, kampanya bazında). on_event: kural tabanlı anomali tespiti (satış 7g ortalamadan ±%40 sapma; ROAS < entity ayarındaki eşik; iade oranı >%X; stok kritik). Anomali → TIER_MID ile tek paragraf açıklama + Event("ecom.anomaly"). briefing: "İşletme" bölümü (dünün cirosu, sipariş adedi, ROAS, anomaliler). propose_actions: MVP'de yok (öneri metni brifingde kalır).

**world_digest** — entity.settings["rss_feeds"] listesi. collect: yeni başlıklar. briefing: TIER_MID ile "Dünya" bölümü, ≤5 madde, kullanıcının kayıtlı ilgi alanlarıyla (MemoryService.search) ilgililik sıralı. Not: anti-yankı bülteni V1'de buraya eklenecek — şimdilik yuva.

---

## 9. Güvenlik / Gizlilik Temeli

- OAuth token'ları ve API anahtarları: DB'de Fernet ile şifreli, anahtar .env'de.
- Google scope'ları: `gmail.readonly`, `calendar.readonly` ve taslak yazımı için `gmail.compose`.
  **B4 — dikkat:** Google'da "yalnızca taslak" scope'u yoktur; `gmail.compose` teknik olarak `messages.send` yetkisini de kapsar. Gönderme kısıtı OAuth düzeyinde değil, **kod düzeyinde** sağlanır ve üç katmanla korunur:
  1. Gmail istemci sarmalayıcısı dışarıya yalnızca `drafts.create` yüzeyini açar; `messages.send` ve `drafts.send` sarmalayıcıda tanımsızdır.
  2. Bu yasak birim testle korunur: gönderme denemesi exception fırlatmalı (yeşil test olmadan 8. oturum kapanmaz).
  3. Yazılan her taslak AuditLog'a düşer.
- Her yürütülen aksiyon AuditLog'a yazılır.
- Yönetim komutları: `python manage.py export_entity <id>` (tüm veri JSON) ve `purge_entity <id>` (geri dönüşsüz silme) — ilk oturumda iskelet olarak eklensin.
- Telegram bot yalnızca beyaz listedeki chat_id ile konuşur (entity.settings["telegram_chat_id"]).

---

## 10. Oturum Planı (Faz 0 → çalışan MVP)

Her madde bir Claude Code oturumudur. Oturum sonunda testler geçer, migration temiz, README güncellenir.

1. **İskelet:** Django proje + docker-compose (postgres/pgvector, redis, web, worker, beat) + §3 modelleri + admin kayıtları + export/purge komut iskeletleri.
2. **LLMService:** litellm entegrasyonu, llm_tiers.yaml, LLMUsage yazımı, bütçe koruması, birim testleri (mock).
3. **MemoryService:** pgvector kurulumu, write/search/çelişki akışı, `manage.py memory_add / memory_query` CLI'ları, testler.
4. **Telegram botu:** webhook, chat_id eşleme, gelen mesajları Event olarak kaydetme, test mesajı gönderimi.
5. **Google OAuth + calendar_mod:** test mode OAuth akışı (localhost redirect), token şifreleme, takvim senkronu, ilk brifing bölümü.
   **B5 — token ömrü:** Google'da "Testing" yayın durumundaki uygulamalarda refresh token 7 günde geçersizleşir. Bu oturuma şunlar dahildir, yoksa oturum kapanmış sayılmaz: her senkron öncesi token sağlık kontrolü; `invalid_grant` yakalanınca `DataSource.status = "reauth_required"` (bu kaynak `ctx.sources()` listesinden düşer, modül sessizce boş döner); Telegram'a tek tıklık yeniden yetkilendirme bağlantısı; brifingde "Google bağlantısı yenilenmeli" uyarı satırı.
6. **email_triage:** Gmail senkron + batch triyaj + brifing bölümü (taslak akışı henüz yok).
7. **BriefingService + beat:** uçtan uca ilk sabah brifingi (calendar + email + placeholder world_digest) Telegram'da.
8. **ApprovalService:** ProposedAction akışı, inline butonlar, email.reply_draft executor (Gmail Drafts), AuditLog.
9. **ecom_ops:** Shopify senkron + anomali kuralları + brifing bölümü; ardından Meta Ads insights.
10. **Geri bildirim + kullanım raporu:** brifing item'larına 👍/👎, FeedbackSignal kaydı, günlük maliyet satırı; world_digest RSS gerçek implementasyon.

**MVP "bitti" tanımı:** 7 ardışık sabah gerçek veriyle otomatik brifing geldi — B5 gereği kullanıcının bu süre içinde bir kez Google yetkisini tazelemesi kriteri bozmaz, brifingin hiç gelmemesi bozar; ≥1 mail taslağı onaylanıp Drafts'a yazıldı; günlük maliyet raporu hedefin altında; export_entity çalışıyor.

---

## 11. Gelecek Modül Yuvaları (kod yazma, yalnızca bil)

M3 anti-yankı (world_digest genişlemesi, haftalık karşı-argüman bülteni) · M4 finans izleme ("tavsiye değil" çerçevesi) · M5 desen analizi (FeedbackSignal + Event geçmişi üzerinden, ≥6 hafta veri şartı) · M6 takvim müzakeresi lite (ajan↔insan, mail üzerinden) · M7 ajan-ajan (A2A/MCP standartları üzerine, kendi protokolü yazılmaz) · M8 WhatsApp Business API · şirket varyantı (EntityMember aktivasyonu + rol bazlı hafıza erişimi).

## 12. Claude Code Çalışma Kuralları

- Oturum başına tek §10 maddesi; kapsam genişletme önerme, sor.
- `core/` içindeki sözleşme imzaları (§4) değiştirilecekse önce gerekçe sun, onay al.
- Yeni bağımlılık eklemeden önce sor. Kod ve yorumlar İngilizce, kullanıcıya açıklamalar Türkçe.
- Her serviste birim test; entegrasyonlar mock'lanır, gerçek API testleri ayrı `manage.py` komutlarıyla manuel.
