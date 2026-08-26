# LIFE OS

Bir varlığın (kişi veya şirket) dijital ikizi. Sahibini tanır, dünyayı sahibinin maruziyetleri üzerinden okur, kendi başına internette araştırır, başka ikizlerle müzakere eder ve sonuç doğuran her adımı sahibinin onayına sunar.

**Durum:** §13 madde 2 tamam — iskelet, veri modeli ve LLMService (tier yönlendirme, maliyet muhasebesi, bütçe tavanı). Sıradaki iş madde 3 (MemoryService).

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

## Kurulum

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # DJANGO_SECRET_KEY ve FERNET_KEY doldur
docker compose up             # postgres(pgvector) + redis + web + worker + beat
```

Testler (yerel PostgreSQL 16 + pgvector ile):

```bash
POSTGRES_HOST=localhost .venv/bin/python -m pytest
```

Yönetim komutları:

```bash
python manage.py export_entity <id> -o export.json   # tüm veri, sırlar hariç
python manage.py purge_entity <id> --yes             # geri dönüşsüz silme
```

## Sonraki adım

SPEC §13 madde 3 — MemoryService: pgvector kurulumu, write/search, gece çelişki batch'i, decay ve keşif istisnası, `memory_add` / `memory_query` CLI'ları.
