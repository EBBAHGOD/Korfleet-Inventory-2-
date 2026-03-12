from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
import json
from datetime import datetime
import io
from openpyxl import load_workbook

from .models import InventoryItem, SerializedItem, InventoryTransaction


class DashboardTests(TestCase):
    """Regression tests for dashboard quantities."""

    def setUp(self):
        # create a regular user and authenticate; make sure password-change
        # middleware doesn't interfere with dashboard tests by clearing the
        # flag that is True by default on new accounts.
        self.user = User.objects.create_user('tester', password='secret')
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.client.login(username='tester', password='secret')

        # create an item with a legacy quantity value and some serials.
        # quantity should now be ignored completely; only the serial records
        # influence counts.
        self.item = InventoryItem.objects.create(
            name='Widget', category='Tools', quantity=10
        )
        # serialized instances: 2 available (New), 1 damaged, 1 faulty
        SerializedItem.objects.create(
            inventory_item=self.item,
            imei="IMEI0",
            status='Available',
            condition='New',
            brand='Acme'
        )
        SerializedItem.objects.create(
            inventory_item=self.item,
            imei="IMEI1",
            status='Available',
            condition='New',
            brand='Acme'
        )
        SerializedItem.objects.create(
            inventory_item=self.item,
            imei="IMEI2",
            status='Issued',
            condition='Used',
            brand='Acme'
        )
        SerializedItem.objects.create(
            inventory_item=self.item,
            imei="IMEI3",
            status='Available',
            condition='Faulty',
            brand='Acme'
        )

        # transactions for coverage
        InventoryTransaction.objects.create(
            item=self.item, transaction_type='OUT', quantity=2
        )

    def test_stock_card_reflects_serialized_count(self):
        resp = self.client.get(reverse('inventory:dashboard'))
        self.assertEqual(resp.status_code, 200)
        # total_units now reflects only the number of serialized records
        # (legacy quantity is ignored when any serials exist).  that should
        # be 4 for our widget item.
        self.assertEqual(resp.context['total_units'], 4)
        # available count now includes every serial except the faulty one
        # (status is ignored for display purposes).  that gives three units.
        self.assertEqual(resp.context['total_available'], 3)

    def test_category_distribution_and_available_by_item(self):
        resp = self.client.get(reverse('inventory:dashboard'))
        dist = json.loads(resp.context['category_distribution'])
        avail = json.loads(resp.context['available_by_item'])
        # Charts should reflect the updated display logic: only serials
        # that are available and not faulty (2 items)
        self.assertEqual(dist.get('Tools'), 2)
        self.assertEqual(avail.get('Widget'), 2)

    def test_inventory_list_shows_total_and_available(self):
        """The inventory list page should expose the same calculated fields
        used by dashboard.

        Previously the template referenced ``item.total_qty`` and
        ``item.available_qty`` without the view populating them; the count
        would render as an empty string.  The view also used to attempt
        assigning to ``total_qty`` (a read-only property) which raised an
        AttributeError.  This regression test guards against both breakage
        and accidental reassignment in the future.
        """
        resp = self.client.get(reverse('inventory:inventory_list'))
        self.assertEqual(resp.status_code, 200)
        page_items = resp.context['page_obj'].object_list
        # find our widget item by name
        widget = next((i for i in page_items if i.name == 'Widget'), None)
        self.assertIsNotNone(widget, msg="Expected Widget in inventory list")
        # there are four serialized records attached in setUp; total_qty
        # should equal 4 and available_qty should equal 2 (faulty and issued
        # serials excluded).  quantity field is ignored even though it was
        # set to 10.
        self.assertEqual(widget.total_qty, 4)
        self.assertEqual(widget.available_qty, 2)

    def test_empty_item_with_legacy_quantity_is_zero(self):
        # create an item that has only the legacy quantity field filled,
        # no serialized records at all.  all counts should be zero now.
        empty = InventoryItem.objects.create(name='Empty', category='Misc', quantity=123)
        resp = self.client.get(reverse('inventory:inventory_list'))
        page_items = resp.context['page_obj'].object_list
        found = next((i for i in page_items if i.name == 'Empty'), None)
        self.assertIsNotNone(found)
        self.assertEqual(found.total_qty, 0)
        self.assertEqual(found.available_qty, 0)
        self.assertNotIn('total_qty', widget.__dict__,
            msg="View should not assign to total_qty property")


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='start123')
        # profile created by signal; ensure flag is True
        self.assertTrue(self.user.profile.force_password_change)

    def test_first_login_forced(self):
        # login should redirect to change-password rather than dashboard
        self.client.login(username='alice', password='start123')
        response = self.client.get(reverse('inventory:dashboard'))
        self.assertRedirects(response, reverse('inventory:change_password'))

    def test_change_password_view(self):
        self.client.login(username='alice', password='start123')
        # post wrong current password
        response = self.client.post(
            reverse('inventory:change_password'),
            {'current_password': 'wrong', 'new_password': 'newpass', 'confirm_password': 'newpass'}
        )
        self.assertContains(response, 'Current password is incorrect.')

        # post mismatched confirmation
        response = self.client.post(
            reverse('inventory:change_password'),
            {'current_password': 'start123', 'new_password': 'newpass', 'confirm_password': 'oops'}
        )
        self.assertContains(response, 'New password and confirmation do not match.')

        # now do a successful change
        response = self.client.post(
            reverse('inventory:change_password'),
            {'current_password': 'start123', 'new_password': 'newpass', 'confirm_password': 'newpass'}
        )
        # should redirect to dashboard and flag cleared
        self.assertRedirects(response, reverse('inventory:dashboard'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.force_password_change)
        # ensure new credential works
        self.client.logout()
        login_ok = self.client.login(username='alice', password='newpass')
        self.assertTrue(login_ok)

    def test_login_redirects_to_dashboard(self):
        # all users (including staff) should land on the inventory dashboard
        staff = User.objects.create_user('bob', password='pw', is_staff=True)
        staff.profile.force_password_change = False
        staff.profile.save()
        resp = self.client.post(reverse('inventory:login'),
                                {'username': 'bob', 'password': 'pw'})
        self.assertRedirects(resp, reverse('inventory:dashboard'))

    def test_admin_link_contains_next_parameter(self):
        # when rendering the custom login page, the "Login as Admin" link
        # should carry ?next=/admin/ so admins end up in the proper place.
        response = self.client.get(reverse('inventory:login'))
        self.assertContains(response, '?next=/admin/')

    def test_password_reset_flag(self):
        # manually set flag to simulate admin reset
        self.user.profile.force_password_change = True
        self.user.profile.save()
        self.client.login(username='alice', password='start123')
        response = self.client.get(reverse('inventory:dashboard'))
        self.assertRedirects(response, reverse('inventory:change_password'))


class AdminDisplayTests(TestCase):
    """Ensure the admin count matches dashboard semantics."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin', password='pw', email='a@b.com')
        # create an inventory item with three serialized records
        self.item = InventoryItem.objects.create(name='MDVR', category='Video Devices (MDVRs)')
        SerializedItem.objects.create(inventory_item=self.item, imei='1', status='Available', condition='New')
        SerializedItem.objects.create(inventory_item=self.item, imei='2', status='Available', condition='Faulty')
        SerializedItem.objects.create(inventory_item=self.item, imei='3', status='Issued', condition='Used')

    def test_admin_available_count_excludes_faulty(self):
        self.client.force_login(self.user)
        # access changelist and check displayed count
        changelist = self.client.get(reverse('admin:inventory_inventoryitem_changelist'))
        # should show 'Available Items' column with value 2 (two serials
        # are non‑faulty even though one is already issued)
        self.assertContains(changelist, 'Available Items')
        self.assertContains(changelist, '>2<')


class InventoryItemTests(TestCase):
    """Basic CRUD tests for inventory items via the public views."""

    def setUp(self):
        self.user = User.objects.create_user('creator', password='pw')
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.client.login(username='creator', password='pw')

    def test_add_item_via_post(self):
        resp = self.client.post(
            reverse('inventory:inventory_add'),
            {'name': 'NewThing', 'category': InventoryItem.CATEGORY_CHOICES[0][0]}
        )
        self.assertRedirects(resp, reverse('inventory:inventory_list'))
        item = InventoryItem.objects.get(name='NewThing')
        self.assertEqual(item.quantity, 0, msg="New items should start with zero quantity")

    def test_edit_item_via_post(self):
        item = InventoryItem.objects.create(name='Old', category='Accessories')
        resp = self.client.post(
            reverse('inventory:inventory_edit', args=[item.id]),
            {'name': 'Renamed', 'category': 'Accessories'}
        )
        self.assertRedirects(resp, reverse('inventory:inventory_list'))
        item.refresh_from_db()
        self.assertEqual(item.name, 'Renamed')


class BulkUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('uploader', password='pw')
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.client.login(username='uploader', password='pw')
        self.item = InventoryItem.objects.create(name='BulkThing', category='Accessories')

    def make_excel(self, rows):
        from openpyxl import Workbook
        f = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(["Item Name", "IMEI", "Brand", "Date Added", "Price", "Condition"])
        for r in rows:
            ws.append(r)
        wb.save(f)
        f.seek(0)
        return f

    def test_bulk_template_has_validations(self):
        resp = self.client.get(reverse('inventory:bulk_upload_template'))
        self.assertEqual(resp.status_code, 200)
        wb = load_workbook(filename=io.BytesIO(resp.content))
        ws = wb['Bulk Upload Template']
        # there should be two data validations: one on col A, one on col F
        dvs = list(ws.data_validations.dataValidation)
        self.assertTrue(any('A2' in dv.sqref for dv in dvs))
        self.assertTrue(any('F2' in dv.sqref for dv in dvs))
        # hidden sheet should exist and contain our item name
        self.assertIn('lists', wb.sheetnames)
        self.assertEqual(wb['lists'].cell(row=1, column=1).value, 'BulkThing')

    def test_bulk_upload_creates_serial_and_txn(self):
        excel = self.make_excel([
            [self.item.name, 'ZZZ1', 'BrandX', '2026-03-01', 9.99, 'New'],
        ])
        resp = self.client.post(reverse('inventory:bulk_upload'),
                                {'excel_file': excel},
                                format='multipart')
        self.assertEqual(resp.status_code, 200)
        si = SerializedItem.objects.get(imei='ZZZ1')
        tx = InventoryTransaction.objects.filter(serialized_item=si, transaction_type='IN').first()
        self.assertIsNotNone(tx)

    def test_bulk_upload_shows_on_dashboard(self):
        excel = self.make_excel([
            [self.item.name, 'ZZZ2', None, '2026-03-02', None, None],
        ])
        self.client.post(reverse('inventory:bulk_upload'), {'excel_file': excel}, format='multipart')
        resp = self.client.get(reverse('inventory:dashboard'))
        self.assertContains(resp, 'ZZZ2')


class StockInTests(TestCase):
    """Tests for the stock-in view and form behaviour."""

    def setUp(self):
        self.user = User.objects.create_user('stocker', password='pw')
        # disable forced password change so middleware doesn't interfere
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.client.login(username='stocker', password='pw')
        self.item = InventoryItem.objects.create(name='Gadget', category='Accessories')


class StockOutTests(TestCase):
    """Ensure issuance logic respects usable vs displayed availability."""

    def setUp(self):
        self.user = User.objects.create_user('issuing', password='pw')
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.client.login(username='issuing', password='pw')
        self.item = InventoryItem.objects.create(name='Thing', category='Tools')
        # three serials: one available, one issued, one faulty
        self.s1 = SerializedItem.objects.create(
            inventory_item=self.item, imei='X1', status='Available', condition='New'
        )
        self.s2 = SerializedItem.objects.create(
            inventory_item=self.item, imei='X2', status='Issued', condition='Used'
        )
        self.s3 = SerializedItem.objects.create(
            inventory_item=self.item, imei='X3', status='Available', condition='Faulty'
        )

    def test_get_form_context(self):
        resp = self.client.get(reverse('inventory:stock_out') + f'?item_id={self.item.id}')
        self.assertEqual(resp.status_code, 200)
        # display count should equal two serials not faulty
        self.assertContains(resp, 'Available Items')
        self.assertContains(resp, '>2<')
        # available_items dropdown must include only the truly free unit
        self.assertContains(resp, 'X1')
        self.assertNotContains(resp, 'X2')
        self.assertNotContains(resp, 'X3')

    def test_issue_validation_limits(self):
        # try to issue more than usable_quantity (which is 1)
        data = {'item_id': str(self.item.id), 'quantity': '2', 'date_taken': '2026-03-01T12:00'}
        resp = self.client.post(reverse('inventory:stock_out'), data, follow=True)
        self.assertContains(resp, 'Only 1 available for issue')

    def test_successful_issue_updates_status(self):
        data = {'item_id': str(self.item.id), 'quantity': '1',
                'serialized_item_id': str(self.s1.id), 'date_taken': '2026-03-01T12:00'}
        resp = self.client.post(reverse('inventory:stock_out'), data)
        self.assertRedirects(resp, reverse('inventory:transactions'))
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.status, 'Issued')

    def test_issue_link_post_without_hidden_item_id(self):
        # simulate old behaviour where form didn't include hidden field
        # POST to stock_out with only querystring should still work
        data = {'quantity': '1', 'serialized_item_id': str(self.s1.id),
                'date_taken': '2026-03-01T12:00'}
        resp = self.client.post(reverse('inventory:stock_out') + f'?item_id={self.item.id}', data)
        self.assertRedirects(resp, reverse('inventory:transactions'))

    def test_get_stock_in_includes_conditions(self):
        # requesting the form for a specific item should expose condition choices
        resp = self.client.get(reverse('inventory:stock_in') + f'?item_id={self.item.id}')
        self.assertEqual(resp.status_code, 200)
        # check that the context contains the expected choices tuple
        self.assertIn('conditions', resp.context)
        self.assertEqual(resp.context['conditions'], SerializedItem.CONDITION_CHOICES)
        # and the rendered HTML should include each label from the choices
        for _code, label in SerializedItem.CONDITION_CHOICES:
            self.assertContains(resp, label)

    def test_post_creates_serialized_item_and_transaction(self):
        data = {
            'item_id': str(self.item.id),
            'imei': 'ABC123',
            'condition': 'Used',
            'brand': 'TestCorp',
            'price': '15.50',
            'date_added': '2026-03-01',
            'purpose': 'New stock',
        }
        resp = self.client.post(reverse('inventory:stock_in'), data)
        # should redirect to transactions page after successful creation
        self.assertRedirects(resp, reverse('inventory:transactions'))
        si = SerializedItem.objects.get(imei='ABC123')
        self.assertEqual(si.condition, 'Used')
        self.assertEqual(si.brand, 'TestCorp')
        self.assertEqual(si.status, 'Available')
        # verify corresponding transaction exists
        tx = InventoryTransaction.objects.filter(serialized_item=si, transaction_type='IN').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.item, self.item)


class ReportsTests(TestCase):
    def setUp(self):
        # create an item and transactions spanning two months
        self.user = User.objects.create_user('reporter', password='r')
        # clear password-change requirement so middleware doesn't redirect
        self.user.profile.force_password_change = False
        self.user.profile.save()
        self.item = InventoryItem.objects.create(name='Widget', category='Tools', quantity=100)
        # two serialized units: one existing before period and one added in January
        from django.utils import timezone
        from datetime import timezone as dt_tz
        utc = dt_tz.utc
        si1 = SerializedItem.objects.create(
            inventory_item=self.item, imei='S1', status='Available', condition='New',
            date_added=timezone.make_aware(datetime(2025,12,15), utc)
        )
        si2 = SerializedItem.objects.create(
            inventory_item=self.item, imei='S2', status='Available', condition='New',
            date_added=timezone.make_aware(datetime(2026,1,5), utc)
        )
        # transactions on first serial: one IN then OUT in January, plus movements in February
        InventoryTransaction.objects.create(
            item=self.item, serialized_item=si1, transaction_type='IN', quantity=1,
            date_taken=timezone.make_aware(datetime(2026,1,15), utc)
        )
        InventoryTransaction.objects.create(
            item=self.item, serialized_item=si1, transaction_type='OUT', quantity=1,
            date_taken=timezone.make_aware(datetime(2026,1,20), utc)
        )
        InventoryTransaction.objects.create(
            item=self.item, serialized_item=si1, transaction_type='IN', quantity=1,
            date_taken=timezone.make_aware(datetime(2026,2,1), utc)
        )
        InventoryTransaction.objects.create(
            item=self.item, serialized_item=si1, transaction_type='OUT', quantity=1,
            date_taken=timezone.make_aware(datetime(2026,2,5), utc)
        )
        InventoryTransaction.objects.create(
            item=self.item, serialized_item=si1, transaction_type='IN', quantity=1,
            date_taken=timezone.make_aware(datetime(2026,2,10), utc)
        )
        # second serial has no transactions, just existence starting Jan 5

    def test_reports_default_period(self):
        self.client.login(username='reporter', password='r')
        resp = self.client.get(reverse('inventory:reports'))
        self.assertEqual(resp.status_code, 200)
        # context should include usage_per_item dictionary (may be empty
        # depending on current date); at least the key exists
        self.assertIn('usage_per_item', resp.context)
        # also verify current qty is correctly computed
        from django.utils import timezone
        today = timezone.now().date()
        # manual snapshot logic replicates view helper, including legacy
        # quantity which should always contribute to the balance.
        def manual_available_up_to(target_date):
            """Replicate the view's report quantity semantics for a given date.

            Faulty serials are *included* (they contribute to the balance) so
            the totals are never negative.  Legacy quantity is ignored when any
            serial exists.
            """
            counts = {}
            sis = SerializedItem.objects.filter(date_added__date__lte=target_date)
            for si in sis:
                # include faulty items in report counts
                iid = si.inventory_item_id
                counts[iid] = counts.get(iid, 0) + 1
            # if no serials exist for an item, fall back to its legacy quantity
            for item in InventoryItem.objects.all():
                if item.id not in counts:
                    counts[item.id] = item.quantity
            return counts
        manual = manual_available_up_to(today)
        balances = resp.context['item_balances']
        # convert names to ids mapping to check each item
        for item in InventoryItem.objects.all():
            name = item.name
            expected = manual.get(item.id, 0)
            self.assertEqual(balances[name]['current'], expected)

    def test_reports_with_specific_dates(self):
        self.client.login(username='reporter', password='r')
        resp = self.client.get(reverse('inventory:reports'),
                               {'start_date': '2026-01-01', 'end_date': '2026-01-31'})
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        # only the January serialized transactions should be counted;
        # there was one OUT and one IN in that month
        self.assertEqual(ctx['total_used'], 1)
        self.assertEqual(ctx['total_increased'], 1)
        self.assertIn('Widget', ctx['items_taken_out_summary'])
        self.assertEqual(ctx['items_taken_out_summary']['Widget']['total_quantity'], 1)

    def test_export_csv(self):
        self.client.login(username='reporter', password='r')
        resp = self.client.get(reverse('inventory:export_report_csv') +
                               '?start_date=2026-01-01&end_date=2026-01-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode()
        self.assertIn('Report Period', content)
        self.assertIn('Widget', content)

    def test_export_excel(self):
        self.client.login(username='reporter', password='r')
        resp = self.client.get(reverse('inventory:export_report_excel') +
                               '?start_date=2026-01-01&end_date=2026-01-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'],
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # basic header presence
        self.assertIn('inventory_report_2026-01-01_to_2026-01-31', resp['Content-Disposition'])

