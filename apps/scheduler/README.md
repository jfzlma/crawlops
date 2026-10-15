# Scheduler service

Entrypoint: `python -m crawlops.scheduler`.

This independent process invokes authenticated transactional API ticks. PostgreSQL owns schedule state and occurrence uniqueness; restarting the process does not erase timers. Multiple scheduler callers are safe on PostgreSQL via row locking and unique idempotency keys. It also invokes bounded retention hourly. Redis is not required for correctness.
