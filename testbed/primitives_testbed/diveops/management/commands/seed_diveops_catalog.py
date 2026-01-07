"""Seed diveops catalog items.

Creates essential catalog items for dive operations:
- Equipment rentals (tanks, BCDs, wetsuits, etc.)
- Services (guide fees, park fees, nitrox fills, etc.)

Usage:
    python manage.py seed_diveops_catalog
    python manage.py seed_diveops_catalog --clear  # Clear existing items first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from django_catalog.models import CatalogItem


DIVEOPS_CATALOG_ITEMS = [
    # Equipment (stock_item)
    {
        "kind": "stock_item",
        "display_name": "Tank Rental",
        "display_name_es": "Alquiler de Tanque",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "BCD Rental",
        "display_name_es": "Alquiler de Chaleco",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "Wetsuit Rental",
        "display_name_es": "Alquiler de Traje",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "Mask & Fins Rental",
        "display_name_es": "Alquiler de Máscara y Aletas",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "Dive Computer Rental",
        "display_name_es": "Alquiler de Computadora de Buceo",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "Underwater Camera Rental",
        "display_name_es": "Alquiler de Cámara Subacuática",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    {
        "kind": "stock_item",
        "display_name": "Dive Light Rental",
        "display_name_es": "Alquiler de Linterna de Buceo",
        "default_stock_action": "dispense",
        "is_billable": True,
    },
    # Services
    {
        "kind": "service",
        "display_name": "Guide Fee",
        "display_name_es": "Tarifa de Guía",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Park Entry Fee",
        "display_name_es": "Tarifa de Entrada al Parque",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Boat Fee",
        "display_name_es": "Tarifa de Lancha",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Nitrox Fill (EAN32)",
        "display_name_es": "Carga de Nitrox (EAN32)",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Nitrox Fill (EAN36)",
        "display_name_es": "Carga de Nitrox (EAN36)",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Equipment Delivery",
        "display_name_es": "Entrega de Equipo",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Night Dive Surcharge",
        "display_name_es": "Recargo por Buceo Nocturno",
        "is_billable": True,
    },
    {
        "kind": "service",
        "display_name": "Private Guide",
        "display_name_es": "Guía Privado",
        "is_billable": True,
    },
]


class Command(BaseCommand):
    help = "Seed diveops catalog items (equipment rentals and services)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing catalog items before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            count = CatalogItem.objects.count()
            CatalogItem.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {count} existing catalog items")
            )

        created_count = 0
        updated_count = 0

        for item_data in DIVEOPS_CATALOG_ITEMS:
            item, created = CatalogItem.objects.update_or_create(
                display_name=item_data["display_name"],
                defaults={
                    "kind": item_data["kind"],
                    "display_name_es": item_data.get("display_name_es", ""),
                    "default_stock_action": item_data.get("default_stock_action", ""),
                    "service_category": item_data.get("service_category", ""),
                    "is_billable": item_data.get("is_billable", True),
                    "active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created: {item.display_name}")
            else:
                updated_count += 1
                self.stdout.write(f"  Updated: {item.display_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created {created_count}, updated {updated_count} catalog items."
            )
        )

        # Summary
        equipment_count = CatalogItem.objects.filter(kind="stock_item", active=True).count()
        service_count = CatalogItem.objects.filter(kind="service", active=True).count()
        self.stdout.write(
            f"\nCatalog now has {equipment_count} equipment items and {service_count} services."
        )
