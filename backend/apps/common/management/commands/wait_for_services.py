"""
Block until Postgres and Redis are reachable.

Run from the container entrypoint before migrations so the app doesn't crash-loop
while dependencies are still starting (compose ``depends_on`` only waits for the
container to start, not for the service inside it to accept connections).
"""

from __future__ import annotations

import time

import redis
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait for Postgres and Redis to accept connections."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--timeout", type=int, default=60, help="Seconds before giving up.")
        parser.add_argument("--interval", type=float, default=1.0, help="Seconds between retries.")

    def handle(self, *args, **options) -> None:
        timeout: int = options["timeout"]
        interval: float = options["interval"]

        self._wait("PostgreSQL", self._check_postgres, timeout, interval)
        self._wait("Redis", self._check_redis, timeout, interval)
        self.stdout.write(self.style.SUCCESS("All services are available."))

    def _wait(self, name, check, timeout, interval) -> None:
        deadline = time.monotonic() + timeout
        self.stdout.write(f"Waiting for {name}...")
        while True:
            ok, err = check()
            if ok:
                self.stdout.write(self.style.SUCCESS(f"{name} is ready."))
                return
            if time.monotonic() >= deadline:
                self.stderr.write(self.style.ERROR(f"{name} not ready after {timeout}s: {err}"))
                raise SystemExit(1)
            time.sleep(interval)

    @staticmethod
    def _check_postgres():
        try:
            connections["default"].cursor().execute("SELECT 1")
            return True, None
        except OperationalError as exc:
            return False, str(exc)

    @staticmethod
    def _check_redis():
        try:
            client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            client.ping()
            return True, None
        except Exception as exc:
            return False, str(exc)
