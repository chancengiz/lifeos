# LIFE OS — Claude Bağlam Dosyası

## Çalışma Kuralları

1. Onay almadan hiçbir işleme başlama. Önce ne yapılacağını açıkla, onay geldikten sonra işleme geç.
2. Gereksiz soru sorma. Plan belliyse anlat ve onay iste, fazladan seçenek üretme.
3. Test geçmeden hiçbir kod projeye dahil edilmez. Önce test yazılır, sonra bileşen.
4. Oturum başına tek `SPEC.md` §13 maddesi. Kapsam genişletme önerme, sor.
5. `core/`, `agent/`, `mesh/` içindeki sözleşme imzaları (§4, §5, §6) değiştirilecekse önce gerekçe sun, onay al.
6. Yeni bağımlılık eklemeden önce sor.
7. Kod ve yorumlar İngilizce, kullanıcıya açıklamalar Türkçe.
8. Her serviste birim test; entegrasyonlar mock'lanır, gerçek API testleri ayrı `manage.py` komutlarıyla manuel.

## Token Verimliliği

- Her oturumda sadece o fazla ilgili dosyalar okunur, tüm proje taranmaz
- Bir dosya oturumda bir kez okunur; büyük dosyalarda sadece gerekli satır aralığı
- Tam dosya yeniden yazılmaz, sadece değişen kısım düzenlenir
- Bağımsız değişiklikler tek mesajda paralel yapılır
- Yanıtlar kısa; giriş cümlesi, özet ve dolgu yok
- İlerleme takip tablosuna işlenir, ayrıca özetlenmez

## Geliştirme Ortamı

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # DJANGO_SECRET_KEY ve FERNET_KEY doldur
docker compose up             # postgres(pgvector) + redis + web + worker + beat
```

Docker'sız yerel test: PostgreSQL 16 + `postgresql-16-pgvector`, sonra
`POSTGRES_HOST=localhost .venv/bin/python -m pytest`.
Migration kontrolü: `manage.py makemigrations --check` (testte de koşuyor).

## Referanslar

- `SPEC.md` v2.0 — vizyon, veri modeli, modül sözleşmesi (§4), ajan döngüsü (§5), mesh protokolü (§6), keşif kotası (§7), güvenlik (§12), oturum planı (§13)
- `REVIEW.md` — Bölüm A kapanan bulgular, Bölüm B v2.0'ın açık riskleri (R1–R9), Bölüm C test borçları.

## Faz Durumu

| Oturum | İçerik | Durum |
|---|---|---|
| 0 | Spec incelemesi + repo kurulumu | ✅ |
| 0b | B1–B5 → SPEC v1.1 | ✅ |
| 0c | Kapsam değişikliği → SPEC v2.0 | ✅ |
| 1 | İskelet: Django + docker-compose + §3 modelleri + admin + export/purge | ✅ |
| 2 | LLMService + tier + ön-tahminli bütçe + degrade modu | ⬜ |
| 3 | MemoryService + pgvector + decay/keşif istisnası | ⬜ |
| 4 | Telegram botu (webhook + secret_token) | ⬜ |
| 5 | self_model: kimlik / maruziyet / ilgi + `/ben` | ⬜ |
| 6 | AgentRuntime: döngü, araç sözleşmesi, tavanlar, izolasyon | ⬜ |
| 7 | Web araçları + **injection savunma testleri** (R1) | ⬜ |
| 8 | world_impact exploit: ImpactFinding + gerekçe zorunluluğu | ⬜ |
| 9 | Keşif kotası: üç şerit + ExplorationLedger + dönüşüm ölçümü | ⬜ |
| 10 | Google OAuth + calendar_mod + yeniden yetkilendirme (B5) | ⬜ |
| 11 | email_triage (yalnızca tespit) | ⬜ |
| 12 | ecom_ops: Shopify + Meta + maruziyet beslemesi | ⬜ |
| 13 | BriefingService + beat: uçtan uca brifing | ⬜ |
| 14 | ApprovalService + executors registry + AuditLog | ⬜ |
| 15 | Mesh v1: kimlik, sözleşme, redaksiyon, yerel taşıma | ⬜ |
| 16 | Mesh v2: müzakere + çift taraflı onay | ⬜ |
| 17 | Ölçüm + kapanış: geri bildirim, maliyet, dönüşüm raporu | ⬜ |
