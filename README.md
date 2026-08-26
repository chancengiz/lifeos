# LIFE OS

Bir varlığın (kişi veya şirket) verilerini toplayan, kalıcı hafıza tutan, her sabah Telegram'dan brifing veren ve aksiyonları yalnızca onayla yürüten proaktif ajan çekirdeği.

**Durum:** Faz 0 — spesifikasyon incelemesi tamam, kod yazılmadı.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `SPEC.md` | Teknik spesifikasyon v1.0 (referans metin) |
| `REVIEW.md` | v1.0 inceleme bulguları — 5 bloke edici madde 1. oturumdan önce çözülmeli |
| `CLAUDE.md` | Oturum çalışma kuralları |

## Stack

Python 3.12 · Django 5.x · PostgreSQL 16 + pgvector · Celery + Redis · python-telegram-bot (webhook) · litellm · Docker Compose

## Sonraki adım

`REVIEW.md` içindeki B1–B5 maddeleri SPEC'e işlenir (v1.1), ardından §10 madde 1: Django iskeleti + docker-compose + veri modeli.
