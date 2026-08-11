# Run plan (interleaved, N=2 first)

Order: a-1 (running) → c-0 → a-2 → c-1 → assess N=2 → maybe a-3,c-3 for N=4.
Each run = its own tracked background task (batched wrapper gets killed).
Score: DEBUG=true DATABASE_URL=':memory:' python manage.py test drafts_probe

Results so far:
- a-0: 8/8  (naive agent found all surfaces — A can succeed)
