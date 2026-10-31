from decimal import Decimal
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from billing.models import Plan, Customer, Subscription, Invoice, LedgerEntry
from billing.services import SubscriptionService, InvoiceService, PaymentService

class BusinessRuleTests(TestCase):
    def setUp(self):
        self.plan=Plan.objects.create(name="Starter", price=Decimal("100.00"), currency="INR", billing_cycle="monthly")
        self.customer=Customer.objects.create(name="Test Customer", email="test@example.com")
        self.sub=SubscriptionService.create(customer_id=self.customer.id, plan_id=self.plan.id)
    def test_plan_price_must_be_positive(self):
        from billing.serializers import PlanSerializer
        serializer=PlanSerializer(data={"name":"Free","price":"0.00","currency":"INR","billing_cycle":"monthly","is_active":True})
        self.assertFalse(serializer.is_valid()); self.assertIn("price", serializer.errors)
    def test_inactive_plan_cannot_be_subscribed_to(self):
        other=Plan.objects.create(name="Inactive", price=Decimal("50"), is_active=False)
        with self.assertRaises(ValidationError): SubscriptionService.create(customer_id=self.customer.id, plan_id=other.id)
    def test_duplicate_active_subscription_rejected(self):
        with self.assertRaises(ValidationError): SubscriptionService.create(customer_id=self.customer.id, plan_id=self.plan.id)
    def test_invoice_snapshots_plan_price_and_writes_ledger(self):
        invoice=InvoiceService.generate(self.sub.id)
        self.assertEqual(invoice.amount_due, Decimal("100.00"))
        self.assertTrue(LedgerEntry.objects.filter(invoice=invoice, entry_type="invoice_created").exists())
        self.plan.price=Decimal("150.00"); self.plan.save()
        invoice2=InvoiceService.generate(self.sub.id)
        self.assertEqual(invoice.amount_due, Decimal("100.00")); self.assertEqual(invoice2.amount_due, Decimal("150.00"))
    def test_successful_payment_cannot_exceed_balance(self):
        invoice=InvoiceService.generate(self.sub.id)
        with self.assertRaises(ValidationError): PaymentService.record(invoice_id=invoice.id, amount=Decimal("100.01"), currency="INR", status="succeeded", provider_reference="overpay-1")
    def test_partial_then_full_payment_updates_invoice(self):
        invoice=InvoiceService.generate(self.sub.id)
        _, invoice=PaymentService.record(invoice_id=invoice.id, amount=Decimal("40.00"), currency="INR", status="succeeded", provider_reference="pay-1")
        self.assertEqual(invoice.status,"partially_paid"); self.assertEqual(invoice.amount_paid,Decimal("40.00"))
        _, invoice=PaymentService.record(invoice_id=invoice.id, amount=Decimal("60.00"), currency="INR", status="succeeded", provider_reference="pay-2")
        self.assertEqual(invoice.status,"paid"); self.assertEqual(invoice.amount_paid,Decimal("100.00"))
    def test_failed_payment_does_not_increase_amount_paid(self):
        invoice=InvoiceService.generate(self.sub.id)
        _, invoice=PaymentService.record(invoice_id=invoice.id, amount=Decimal("25.00"), currency="INR", status="failed", provider_reference="fail-1", failure_reason="Card declined")
        invoice.refresh_from_db(); self.assertEqual(invoice.amount_paid,Decimal("0.00")); self.assertEqual(invoice.status,"issued")
