import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone

class Plan(models.Model):
    class BillingCycle(models.TextChoices): MONTHLY="monthly", "Monthly"; QUARTERLY="quarterly", "Quarterly"; YEARLY="yearly", "Yearly"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    billing_cycle = models.CharField(max_length=12, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering=["name"]
    def __str__(self): return self.name

class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=[("active","Active"),("inactive","Inactive")], default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering=["email"]
    def __str__(self): return self.email

class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=[("active","Active"),("cancelled","Cancelled"),("expired","Expired")], default="active")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["customer","plan"], condition=Q(status="active"), name="unique_active_customer_plan")]
        ordering=["-created_at"]

class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=20, choices=[("draft","Draft"),("issued","Issued"),("partially_paid","Partially paid"),("paid","Paid"),("overdue","Overdue"),("void","Void")], default="issued")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class PaymentAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payment_attempts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=20, choices=[("succeeded","Succeeded"),("failed","Failed")])
    provider_reference = models.CharField(max_length=180, unique=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="ledger_entries")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_type = models.CharField(max_length=40, choices=[("invoice_created","Invoice created"),("payment_success","Payment success"),("payment_failure","Payment failure")])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    reference_id = models.CharField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]
    def save(self, *args, **kwargs):
        if self.pk and LedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValueError("Ledger entries are append-only and cannot be updated")
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs): raise ValueError("Ledger entries are append-only and cannot be deleted")
