from django.contrib import admin
from .models import Route, Stop, Vehicle, Driver, Schedule, Trip, Device

for m in (Route, Stop, Vehicle, Driver, Schedule, Trip, Device):
    admin.site.register(m)
