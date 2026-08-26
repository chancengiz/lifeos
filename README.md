# LIFE OS

Bir varlığın (kişi veya şirket) dijital ikizi. Sahibini tanır, dünyayı sahibinin maruziyetleri üzerinden okur, kendi başına internette araştırır, başka ikizlerle müzakere eder ve sonuç doğuran her adımı sahibinin onayına sunar.

**Durum:** Faz 0 — spec v2.0, kod yazılmadı. Sıradaki iş §13 madde 1 (İskelet).

## Dosyalar

| Dosya | İçerik |
|---|---|
| `SPEC.md` | Teknik spesifikasyon v2.0 — referans metin |
| `REVIEW.md` | Kapanan bulgular + v2.0'ın açık riskleri (R1–R9) + test borçları |
| `CLAUDE.md` | Oturum çalışma kuralları |

## Üç sütun

1. **Kendini tanıma** — kimlik, maruziyet ve ilgi haritası (`self_model`)
2. **İnternetle etkileşim** — ne arayacağına kendi karar veren ajan döngüsü (`agent_runtime`, `world_impact`)
3. **Ajan-ajan etkileşim** — protokol, paylaşım sözleşmesi, müzakere (`agent_mesh`)

Dördüncü ilke: **yankı odasına düşmeme** — araştırma ve bağlantıların %15'i bilerek düşük ilişkili veya ilişkisiz alanlara ayrılır (SPEC §7).

## Stack

Python 3.12 · Django 5.x · PostgreSQL 16 + pgvector · Celery + Redis · python-telegram-bot (webhook) · litellm · Docker Compose

## Sonraki adım

SPEC §13 madde 1 — İskelet: Django + docker-compose (postgres/pgvector, redis, web, worker, beat) + §3 modelleri + admin kayıtları + export/purge komut iskeletleri.
