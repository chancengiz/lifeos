# LIFE OS — Claude Bağlam Dosyası

## Çalışma Kuralları

1. Onay almadan hiçbir işleme başlama. Önce ne yapılacağını açıkla, onay geldikten sonra işleme geç.
2. Gereksiz soru sorma. Plan belliyse anlat ve onay iste, fazladan seçenek üretme.
3. Test geçmeden hiçbir kod projeye dahil edilmez. Önce test yazılır, sonra bileşen.
4. Oturum başına tek `SPEC.md` §10 maddesi. Kapsam genişletme önerme, sor.
5. `core/` içindeki §4 sözleşme imzaları değiştirilecekse önce gerekçe sun, onay al.
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

## Referanslar

- `SPEC.md` — mimari, veri modeli, modül sözleşmesi, oturum planı
- `REVIEW.md` — açık bulgular. B1–B5 kapanmadan 1. oturum başlamaz.

## Faz Durumu

| Oturum | İçerik | Durum |
|---|---|---|
| 0 | Spec incelemesi + repo kurulumu | ✅ |
| 0b | REVIEW.md B1–B5 → SPEC v1.1 | ⬜ |
| 1 | Django iskeleti + docker-compose + §3 modelleri | ⬜ |
| 2 | LLMService + llm_tiers.yaml + bütçe koruması | ⬜ |
| 3 | MemoryService + pgvector | ⬜ |
| 4 | Telegram botu (webhook) | ⬜ |
| 5 | Google OAuth + calendar_mod | ⬜ |
| 6 | email_triage | ⬜ |
| 7 | BriefingService + beat (uçtan uca ilk brifing) | ⬜ |
| 8 | ApprovalService + email.reply_draft executor | ⬜ |
| 9 | ecom_ops (Shopify + Meta Ads) | ⬜ |
| 10 | Geri bildirim + kullanım raporu + world_digest | ⬜ |
