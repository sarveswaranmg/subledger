
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework.exceptions import NotFound, ValidationError

from .models import (
    Plan,
    Customer,
    Subscription,
    Invoice,
    PaymentAttempt,
    LedgerEntry,
)


class SubscriptionService:
    @staticmethod
    @transaction.atomic
    def create(*, customer_id, plan_id, **kwargs):
        try:
            customer = Customer.objects.select_for_update().get(
                pk=customer_id
            )
        except Customer.DoesNotExist:
            raise NotFound("Customer not found.")

        try:
            plan = Plan.objects.select_for_update().get(pk=plan_id)
        except Plan.DoesNotExist:
            raise NotFound("Plan not found.")

        if customer.status != "active":
            raise ValidationError(
                "Cannot subscribe an inactive customer."
            )

        if not plan.is_active:
            raise ValidationError(
                "Cannot subscribe to an inactive plan."
            )

        existing_subscription = Subscription.objects.filter(
            customer=customer,
            plan=plan,
            status="active",
        ).exists()

        if existing_subscription:
            raise ValidationError(
                "Customer already has an active subscription "
                "to this plan."
            )

        try:
            return Subscription.objects.create(
                customer=customer,
                plan=plan,
                **kwargs,
            )
        except IntegrityError:
            # A database uniqueness constraint should enforce
            # the active-subscription rule under concurrency.
            raise ValidationError(
                "An active subscription to this plan already exists."
            )


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def generate(subscription_id):
        try:
            subscription = (
                Subscription.objects.select_for_update()
                .select_related("customer", "plan")
                .get(pk=subscription_id)
            )
        except Subscription.DoesNotExist:
            raise NotFound("Subscription not found.")

        if subscription.status != "active":
            raise ValidationError(
                "Invoice can only be generated for an active subscription."
            )

        plan = subscription.plan

        if plan.price <= Decimal("0.00"):
            raise ValidationError(
                "Plan price must be greater than zero."
            )

        # Explicitly document the assignment's fixed-duration
        # billing-period assumption.
        billing_days = {
            "monthly": 30,
            "quarterly": 90,
            "yearly": 365,
        }

        try:
            days = billing_days[plan.billing_cycle]
        except KeyError:
            raise ValidationError("Unsupported billing cycle.")

        period_start = timezone.now()
        period_end = period_start + timedelta(days=days)

        # Copy the current plan price into the invoice.
        # Subsequent plan price changes won't affect this invoice.
        invoice = Invoice.objects.create(
            subscription=subscription,
            customer=subscription.customer,
            amount_due=plan.price,
            amount_paid=Decimal("0.00"),
            currency=plan.currency,
            status="issued",
            period_start=period_start,
            period_end=period_end,
            due_date=period_start + timedelta(days=14),
        )

        LedgerEntry.objects.create(
            customer=subscription.customer,
            invoice=invoice,
            entry_type="invoice_created",
            amount=invoice.amount_due,
            currency=invoice.currency,
            reference_id=f"invoice:{invoice.pk}:created",
            description="Invoice generated",
        )

        return invoice


class PaymentService:
    @staticmethod
    @transaction.atomic
    def record(
        *,
        invoice_id,
        amount,
        currency,
        status,
        provider_reference,
        failure_reason="",
    ):
        try:
            invoice = (
                Invoice.objects.select_for_update()
                .select_related("customer")
                .get(pk=invoice_id)
            )
        except Invoice.DoesNotExist:
            raise NotFound("Invoice not found.")

        # Validate payment amount without accepting NaN or infinity.
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Invalid payment amount.")

        if not amount.is_finite():
            raise ValidationError(
                "Payment amount must be finite."
            )

        if amount <= Decimal("0.00"):
            raise ValidationError(
                "Payment amount must be greater than zero."
            )

        if status not in ("succeeded", "failed"):
            raise ValidationError(
                "Payment status must be succeeded or failed."
            )

        if not isinstance(currency, str) or not currency.strip():
            raise ValidationError("Payment currency is required.")

        currency = currency.strip().upper()

        if currency != invoice.currency.upper():
            raise ValidationError(
                "Payment currency must match invoice currency."
            )

        if (
            not isinstance(provider_reference, str)
            or not provider_reference.strip()
        ):
            raise ValidationError(
                "Provider reference is required."
            )

        provider_reference = provider_reference.strip()

        if invoice.status in ("paid", "void"):
            raise ValidationError(
                "Cannot record payment against a paid or void invoice."
            )

        # Idempotency check: avoid applying the same provider
        # reference more than once to the same invoice.
        existing_attempt = PaymentAttempt.objects.filter(
            invoice=invoice,
            provider_reference=provider_reference,
        ).first()

        if existing_attempt:
            same_attempt = (
                existing_attempt.amount == amount
                and existing_attempt.currency.upper() == currency
                and existing_attempt.status == status
            )

            if not same_attempt:
                raise ValidationError(
                    "Provider reference has already been used "
                    "for a different payment attempt."
                )

            # Return the existing attempt without changing the
            # invoice or creating another ledger entry.
            return existing_attempt, invoice

        if status == "succeeded":
            remaining_amount = invoice.amount_due - invoice.amount_paid

            if amount > remaining_amount:
                raise ValidationError(
                    "Payment cannot exceed the remaining unpaid amount."
                )

        try:
            attempt = PaymentAttempt.objects.create(
                invoice=invoice,
                amount=amount,
                currency=currency,
                status=status,
                provider_reference=provider_reference,
                failure_reason=(
                    failure_reason or "Payment failed"
                    if status == "failed"
                    else ""
                ),
            )
        except IntegrityError:
            # A database uniqueness constraint on the provider
            # reference is recommended as an additional safeguard.
            existing_attempt = PaymentAttempt.objects.filter(
                invoice=invoice,
                provider_reference=provider_reference,
            ).first()

            if existing_attempt:
                same_attempt = (
                    existing_attempt.amount == amount
                    and existing_attempt.currency.upper() == currency
                    and existing_attempt.status == status
                )

                if same_attempt:
                    return existing_attempt, invoice

            raise ValidationError(
                "This provider reference has already been recorded."
            )

        if status == "succeeded":
            invoice.amount_paid += amount

            if invoice.amount_paid == invoice.amount_due:
                invoice.status = "paid"
            else:
                invoice.status = "partially_paid"

            invoice.save(
                update_fields=["amount_paid", "status"]
            )

            entry_type = "payment_success"
            description = "Successful payment recorded"

        else:
            # Failed payments must never increase amount_paid.
            entry_type = "payment_failure"
            description = (
                failure_reason or "Payment failed; invoice balance unchanged"
            )

        LedgerEntry.objects.create(
            customer=invoice.customer,
            invoice=invoice,
            entry_type=entry_type,
            amount=amount,
            currency=invoice.currency,
            reference_id=(
                f"payment:{provider_reference}:{entry_type}"
            ),
            description=description,
        )

        return attempt, invoice
