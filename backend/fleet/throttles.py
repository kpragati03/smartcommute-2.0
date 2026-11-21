"""DRF throttling for device telemetry (Wave 2).

Keyed by the SHA-256 hash of the X-Device-Key header so each physical
device gets its own budget (default 120/min via settings
DEFAULT_THROTTLE_RATES["telemetry"]). Requests without a device key
fall back to the client IP so keyless floods are still limited.
Returns DRF's standard 429 when the budget is exceeded.
"""
import hashlib

from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


class DeviceTelemetryThrottle(SimpleRateThrottle):
    scope = "telemetry"

    def get_rate(self):
        # Read fresh from api_settings (not the import-time class attr) so
        # the rate honours settings/override_settings changes.
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    def get_cache_key(self, request, view):
        raw_key = request.headers.get("X-Device-Key", "") or ""
        if raw_key:
            ident = "device:" + hashlib.sha256(raw_key.encode()).hexdigest()
        else:
            ident = "ip:" + self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
