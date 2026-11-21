from django.contrib import admin
from .models import LocationHistory, OccupancyRecord, ETAPrediction

for m in (LocationHistory, OccupancyRecord, ETAPrediction):
    admin.site.register(m)
