# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Coverage for the shopping-list add/supplier-management endpoints and the
whole buyer workflow (shopping_buy*, shopping_item_enrich, shopping_buy_add,
shopping_out_of_stock) — the untested two-thirds of shopping.py flagged in
docs/QUALITY_BASELINE.md ("3 of 13 endpoints tested") and Chunk 10 of the
quality pass."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.labs.models import (
    ConsumableItem,
    NeedFlag,
    ProcurementPledge,
    Supplier,
    SupplierRecord,
)
from .common import LabsTestsMixin


class ShoppingItemAddTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_shows_form(self):
        response = self.client.get(reverse("labs-shopping-add"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_item(self):
        response = self.client.post(
            reverse("labs-shopping-add"),
            {
                "name": "Tea bags",
                "category": ConsumableItem.CATEGORY_KITCHEN,
                "notes": "Builders, not fancy",
            },
        )
        self.assertRedirects(response, reverse("labs-shopping"))
        item = ConsumableItem.objects.get(name="Tea bags")
        self.assertEqual(item.category, ConsumableItem.CATEGORY_KITCHEN)
        self.assertEqual(item.notes, "Builders, not fancy")

    def test_post_duplicate_name_case_insensitive_does_not_create_second(self):
        ConsumableItem.objects.create(
            name="Tea Bags", category=ConsumableItem.CATEGORY_KITCHEN
        )
        self.client.post(
            reverse("labs-shopping-add"),
            {"name": "tea bags", "category": ConsumableItem.CATEGORY_KITCHEN},
        )
        self.assertEqual(
            ConsumableItem.objects.filter(name__iexact="tea bags").count(), 1
        )

    def test_post_invalid_category_falls_back_to_other(self):
        self.client.post(
            reverse("labs-shopping-add"),
            {"name": "Mystery item", "category": "not-a-real-category"},
        )
        item = ConsumableItem.objects.get(name="Mystery item")
        self.assertEqual(item.category, ConsumableItem.CATEGORY_OTHER)

    def test_post_blank_name_creates_nothing(self):
        self.client.post(
            reverse("labs-shopping-add"),
            {"name": "  ", "category": ConsumableItem.CATEGORY_OTHER},
        )
        self.assertFalse(ConsumableItem.objects.exists())


class ShoppingSupplierRecordTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Bin liners", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_add_supplier_record(self):
        response = self.client.post(
            reverse(
                "labs-shopping-supplier-add", kwargs={"item_id": self.item.pk}
            ),
            {
                "supplier_name": "Bunzl",
                "approx_price": "12.50",
                "product_code": "BZ-100",
                "unit_desc": "Box of 200",
            },
        )
        self.assertRedirects(
            response,
            reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}),
        )
        record = SupplierRecord.objects.get(item=self.item)
        self.assertEqual(record.supplier_name, "Bunzl")
        self.assertEqual(str(record.approx_price), "12.50")

    def test_add_supplier_record_blank_name_errors(self):
        self.client.post(
            reverse(
                "labs-shopping-supplier-add", kwargs={"item_id": self.item.pk}
            ),
            {"supplier_name": ""},
        )
        self.assertFalse(SupplierRecord.objects.exists())

    def test_add_supplier_record_bad_price_ignored(self):
        self.client.post(
            reverse(
                "labs-shopping-supplier-add", kwargs={"item_id": self.item.pk}
            ),
            {"supplier_name": "Bunzl", "approx_price": "not-a-number"},
        )
        record = SupplierRecord.objects.get(item=self.item)
        self.assertIsNone(record.approx_price)

    def test_delete_supplier_record(self):
        record = SupplierRecord.objects.create(
            item=self.item, supplier_name="Bunzl"
        )
        response = self.client.post(
            reverse(
                "labs-shopping-supplier-delete",
                kwargs={"supplier_id": record.pk},
            )
        )
        self.assertRedirects(
            response,
            reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}),
        )
        self.assertFalse(SupplierRecord.objects.filter(pk=record.pk).exists())


class ShoppingPledgeUpdateTests(LabsTestsMixin, TestCase):
    """shopping_pledge only reaches its "update existing" branch when the
    existing pledge is already fulfilled (an unfulfilled one, of any status,
    short-circuits with "someone already pledged" instead) — re-pledging on
    a fulfilled item reopens it rather than creating a second pledge."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.flag = NeedFlag.objects.create(
            item=self.item, flagged_by=self.vol
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_unfulfilled_pledge_short_circuits_without_updating(self):
        pledge = ProcurementPledge.objects.create(
            need_flag=self.flag,
            pledged_by=self.vol,
            status=ProcurementPledge.STATUS_OUT_OF_STOCK,
        )
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url, {"eta_notes": "Trying elsewhere"})
        pledge.refresh_from_db()
        self.assertEqual(pledge.eta_notes, "")

    def test_pledging_over_a_fulfilled_pledge_reopens_it(self):
        pledge = ProcurementPledge.objects.create(
            need_flag=self.flag,
            pledged_by=self.vol,
            fulfilled_at=timezone.now(),
        )
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url, {"eta_notes": "Trying elsewhere"})
        pledge.refresh_from_db()
        self.assertEqual(pledge.eta_notes, "Trying elsewhere")
        self.assertIsNone(pledge.fulfilled_at)
        self.assertEqual(
            ProcurementPledge.objects.filter(need_flag=self.flag).count(), 1
        )


class ShoppingBuyPickerTests(LabsTestsMixin, TestCase):
    """The supplier-picker entry point (shopping_buy)."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Coffee", category=ConsumableItem.CATEGORY_KITCHEN
        )
        self.supplier = Supplier.objects.create(name="Costco")
        SupplierRecord.objects.create(
            item=self.item, supplier=self.supplier, supplier_name="Costco"
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_renders(self):
        response = self.client.get(reverse("labs-shopping-buy"))
        self.assertEqual(response.status_code, 200)

    def test_needed_total_counts_open_flags_for_supplier(self):
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        response = self.client.get(reverse("labs-shopping-buy"))
        card = next(
            c
            for c in response.context["supplier_cards"]
            if c["supplier"] == self.supplier
        )
        self.assertEqual(card["needed_total"], 1)
        self.assertEqual(card["covered"], 0)

    def test_covered_counts_pledged_and_ordered_flags(self):
        flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        ProcurementPledge.objects.create(
            need_flag=flag,
            pledged_by=self.vol,
            intended_supplier=self.supplier,
            status=ProcurementPledge.STATUS_ORDERED,
        )
        response = self.client.get(reverse("labs-shopping-buy"))
        card = next(
            c
            for c in response.context["supplier_cards"]
            if c["supplier"] == self.supplier
        )
        self.assertEqual(card["covered"], 1)

    def test_out_of_stock_pledge_not_counted_as_covered(self):
        flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        ProcurementPledge.objects.create(
            need_flag=flag,
            pledged_by=self.vol,
            intended_supplier=self.supplier,
            status=ProcurementPledge.STATUS_OUT_OF_STOCK,
        )
        response = self.client.get(reverse("labs-shopping-buy"))
        card = next(
            c
            for c in response.context["supplier_cards"]
            if c["supplier"] == self.supplier
        )
        self.assertEqual(card["covered"], 0)

    def test_unsorted_count_excludes_items_with_suppliers(self):
        unsorted_item = ConsumableItem.objects.create(
            name="Mystery cleaner", category=ConsumableItem.CATEGORY_CLEANING
        )
        NeedFlag.objects.create(item=unsorted_item, flagged_by=self.vol)
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        response = self.client.get(reverse("labs-shopping-buy"))
        self.assertEqual(response.context["unsorted_count"], 1)


class ShoppingBuySupplierSheetTests(LabsTestsMixin, TestCase):
    """The core per-supplier buyer sheet."""

    def setUp(self):
        super().setUp()
        self.supplier = Supplier.objects.create(name="Costco")
        self.other_supplier = Supplier.objects.create(name="Bunzl")
        self.item = ConsumableItem.objects.create(
            name="Coffee", category=ConsumableItem.CATEGORY_KITCHEN
        )
        self.record = SupplierRecord.objects.create(
            item=self.item, supplier=self.supplier, supplier_name="Costco"
        )
        SupplierRecord.objects.create(
            item=self.item,
            supplier=self.other_supplier,
            supplier_name="Bunzl",
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_renders_with_open_flag_row(self):
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        response = self.client.get(
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 1)
        row = response.context["rows"][0]
        self.assertEqual(row["item"], self.item)
        self.assertEqual(row["other_suppliers"], [self.other_supplier])

    def test_records_with_no_open_flag_are_excluded(self):
        response = self.client.get(
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            )
        )
        self.assertEqual(response.context["rows"], [])

    def test_inactive_supplier_404s(self):
        self.supplier.active = False
        self.supplier.save()
        response = self.client.get(
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_row_carries_existing_pledge(self):
        flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        pledge = ProcurementPledge.objects.create(
            need_flag=flag, pledged_by=self.vol
        )
        response = self.client.get(
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            )
        )
        self.assertEqual(response.context["rows"][0]["pledge"], pledge)


class ShoppingBuyUnsortedTests(LabsTestsMixin, TestCase):
    """The enrichment workbench for items with no supplier attached."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_shows_only_unsorted_open_flags(self):
        sorted_item = ConsumableItem.objects.create(
            name="Coffee", category=ConsumableItem.CATEGORY_KITCHEN
        )
        supplier = Supplier.objects.create(name="Costco")
        SupplierRecord.objects.create(
            item=sorted_item, supplier=supplier, supplier_name="Costco"
        )
        NeedFlag.objects.create(item=sorted_item, flagged_by=self.vol)

        unsorted_item = ConsumableItem.objects.create(
            name="Sponges", category=ConsumableItem.CATEGORY_CLEANING
        )
        NeedFlag.objects.create(item=unsorted_item, flagged_by=self.vol)

        response = self.client.get(reverse("labs-shopping-buy-unsorted"))
        items = [f.item for f in response.context["open_flags"]]
        self.assertIn(unsorted_item, items)
        self.assertNotIn(sorted_item, items)


class ShoppingItemEnrichTests(LabsTestsMixin, TestCase):
    """Attaching a supplier to an item from the unsorted workbench."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Sponges", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_enrich_with_existing_supplier_id(self):
        supplier = Supplier.objects.create(name="Costco")
        response = self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {"supplier_id": str(supplier.pk), "product_code": "SP-1"},
        )
        self.assertRedirects(response, reverse("labs-shopping-buy-unsorted"))
        record = SupplierRecord.objects.get(item=self.item)
        self.assertEqual(record.supplier, supplier)
        self.assertEqual(record.supplier_name, "Costco")

    def test_enrich_with_new_supplier_name_creates_supplier(self):
        self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {"supplier_name": "New Supplier Co"},
        )
        supplier = Supplier.objects.get(name="New Supplier Co")
        record = SupplierRecord.objects.get(item=self.item)
        self.assertEqual(record.supplier, supplier)

    def test_enrich_with_existing_name_reuses_supplier_case_insensitively(
        self,
    ):
        supplier = Supplier.objects.create(name="Costco")
        self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {"supplier_name": "costco"},
        )
        self.assertEqual(
            Supplier.objects.filter(name__iexact="costco").count(), 1
        )
        record = SupplierRecord.objects.get(item=self.item)
        self.assertEqual(record.supplier, supplier)

    def test_enrich_with_no_supplier_info_errors(self):
        response = self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {},
        )
        self.assertRedirects(response, reverse("labs-shopping-buy-unsorted"))
        self.assertFalse(SupplierRecord.objects.exists())

    def test_enrich_bad_price_ignored(self):
        self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {"supplier_name": "Costco", "approx_price": "abc"},
        )
        record = SupplierRecord.objects.get(item=self.item)
        self.assertIsNone(record.approx_price)

    def test_enrich_unknown_supplier_id_falls_back_to_error(self):
        response = self.client.post(
            reverse("labs-shopping-enrich", kwargs={"item_id": self.item.pk}),
            {"supplier_id": "999999"},
        )
        self.assertRedirects(response, reverse("labs-shopping-buy-unsorted"))
        self.assertFalse(SupplierRecord.objects.exists())


class ShoppingBuyAddTests(LabsTestsMixin, TestCase):
    """Adding a flagged item to a supplier's order (pledge with status=ordered)."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Coffee", category=ConsumableItem.CATEGORY_KITCHEN
        )
        self.flag = NeedFlag.objects.create(
            item=self.item, flagged_by=self.vol
        )
        self.supplier = Supplier.objects.create(name="Costco")
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_add_with_supplier_creates_ordered_pledge(self):
        response = self.client.post(
            reverse("labs-shopping-buy-add", kwargs={"flag_id": self.flag.pk}),
            {"supplier_id": str(self.supplier.pk)},
        )
        self.assertRedirects(
            response,
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            ),
        )
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertEqual(pledge.status, ProcurementPledge.STATUS_ORDERED)
        self.assertEqual(pledge.intended_supplier, self.supplier)

    def test_add_without_supplier_redirects_to_buy(self):
        response = self.client.post(
            reverse("labs-shopping-buy-add", kwargs={"flag_id": self.flag.pk}),
        )
        self.assertRedirects(response, reverse("labs-shopping-buy"))
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertIsNone(pledge.intended_supplier)

    def test_add_updates_existing_unfulfilled_pledge(self):
        pledge = ProcurementPledge.objects.create(
            need_flag=self.flag, pledged_by=self.vol
        )
        self.client.post(
            reverse("labs-shopping-buy-add", kwargs={"flag_id": self.flag.pk}),
            {"supplier_id": str(self.supplier.pk)},
        )
        pledge.refresh_from_db()
        self.assertEqual(pledge.status, ProcurementPledge.STATUS_ORDERED)
        self.assertEqual(
            ProcurementPledge.objects.filter(need_flag=self.flag).count(), 1
        )


class ShoppingOutOfStockTests(LabsTestsMixin, TestCase):
    """Marking an item out of stock at a supplier — keeps the need open."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Coffee", category=ConsumableItem.CATEGORY_KITCHEN
        )
        self.flag = NeedFlag.objects.create(
            item=self.item, flagged_by=self.vol
        )
        self.supplier = Supplier.objects.create(name="Costco")
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_marks_out_of_stock_with_supplier_note(self):
        response = self.client.post(
            reverse("labs-shopping-oos", kwargs={"flag_id": self.flag.pk}),
            {"supplier_id": str(self.supplier.pk)},
        )
        self.assertRedirects(
            response,
            reverse(
                "labs-shopping-buy-supplier",
                kwargs={"supplier_id": self.supplier.pk},
            ),
        )
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertEqual(pledge.status, ProcurementPledge.STATUS_OUT_OF_STOCK)
        self.assertIn("Costco", pledge.status_notes)
        self.flag.refresh_from_db()
        self.assertIsNone(self.flag.resolved_at)

    def test_marks_out_of_stock_without_supplier(self):
        response = self.client.post(
            reverse("labs-shopping-oos", kwargs={"flag_id": self.flag.pk}),
        )
        self.assertRedirects(response, reverse("labs-shopping-buy"))
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertEqual(pledge.status_notes, "Out of stock")

    def test_updates_existing_unfulfilled_pledge(self):
        pledge = ProcurementPledge.objects.create(
            need_flag=self.flag, pledged_by=self.vol
        )
        self.client.post(
            reverse("labs-shopping-oos", kwargs={"flag_id": self.flag.pk}),
            {"supplier_id": str(self.supplier.pk)},
        )
        pledge.refresh_from_db()
        self.assertEqual(pledge.status, ProcurementPledge.STATUS_OUT_OF_STOCK)
        self.assertEqual(
            ProcurementPledge.objects.filter(need_flag=self.flag).count(), 1
        )
