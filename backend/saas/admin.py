from django.contrib import admin
from .models import SubscriptionPlan, Subscription, Invoice

for m in (SubscriptionPlan, Subscription, Invoice):
    admin.site.register(m)
