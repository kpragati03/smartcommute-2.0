from django.contrib import admin
from .models import (FavouriteRoute, FavouriteStop, SavedJourney, PassApplication,
                     TransportPass, Complaint, Feedback, Incident)

for m in (FavouriteRoute, FavouriteStop, SavedJourney, PassApplication, TransportPass, Complaint, Feedback, Incident):
    admin.site.register(m)
