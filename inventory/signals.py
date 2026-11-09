from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import BloodStock, BloodUnit


@receiver(post_delete, sender=BloodUnit)
def remove_mirrored_stock(sender, instance, **kwargs):
    """Remove a deleted unit's stock row, or retire it if reservations point at it."""
    if not instance.stock_id:
        return
    stock = BloodStock.objects.filter(pk=instance.stock_id).first()
    if stock is None:
        return
    if stock.reservations.exists():
        stock.available_units = 0
        stock.status = BloodStock.StockStatus.DISPOSED
        stock.save(update_fields=["available_units", "status", "updated_at"])
    else:
        stock.delete()
