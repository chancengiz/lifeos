# LIFE OS

Bir varlığın (kişi veya şirket) verilerini toplayan, kalıcı hafıza tutan, her sabah Telegram'dan brifing veren ve aksiyonları yalnızca onayla yürüten proaktif ajan çekirdeği.

**Durum:** Faz 0 — spec v1.1 (B1–B5 bloke edici bulgular işlendi), kod yazılmadı.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `SPEC.md` | Teknik spesifikasyon v1.1 (referans metin) |
| `REVIEW.md` | İnceleme bulguları — B1–B5 ✅ kapandı; Ö1–Ö5, küçükler ve test borcu açık |
| `CLAUDE.md` | Oturum çalışma kuralları |

## Stack

Python 3.12 · Django 5.x · PostgreSQL 16 + pgvector · Celery + Redis · python-telegram-bot (webhook) · litellm · Docker Compose

## Sonraki adım

§10 madde 1: Django iskeleti + docker-compose (postgres/pgvector, redis, web, worker, beat) + §3 modelleri + admin kayıtları + export/purge komut iskeletleri.
