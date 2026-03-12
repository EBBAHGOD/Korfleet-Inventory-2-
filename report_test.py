from django.utils import timezone
from datetime import date, timedelta
from inventory.models import InventoryItem, SerializedItem, InventoryTransaction


def available_snapshot(date):
    counts={}
    sis=SerializedItem.objects.filter(date_added__date__lte=date)
    for si in sis:
        if si.condition=='Faulty':
            continue
        status='Available'
        for tx in si.transactions.filter(date_taken__date__lte=date).order_by('date_taken'):
            status='Available' if tx.transaction_type=='IN' else 'Issued'
        if status=='Available':
            counts[si.inventory_item_id]=counts.get(si.inventory_item_id,0)+1
    return counts


if __name__ == '__main__':
    mdvr = InventoryItem.objects.filter(name__icontains='MDVR').first()
    if not mdvr:
        print("MDVR not found")
    else:
        start = date(2025,3,10)
        end = date(2025,3,13)
        opening = available_snapshot(start - timedelta(days=1)).get(mdvr.id,0)
        closing = available_snapshot(end).get(mdvr.id,0)
        current = mdvr.available_quantity()
        print("MDVR", mdvr.id, mdvr.name)
        print("opening",opening,"closing",closing,"current",current)

