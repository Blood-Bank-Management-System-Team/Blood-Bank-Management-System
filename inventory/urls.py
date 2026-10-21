
from django.urls import path

from .views import BloodUnitListCreateView, BloodUnitDetailView

urlpatterns = [
    path("", BloodUnitListCreateView.as_view(), name="blood-unit-list-create"),
    path("<int:pk>/", BloodUnitDetailView.as_view(), name="blood-unit-detail"),
]
