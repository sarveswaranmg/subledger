from django.db import IntegrityError
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Plan, Customer, Subscription, Invoice, PaymentAttempt, LedgerEntry
from .serializers import PlanSerializer, CustomerSerializer, SubscriptionSerializer, InvoiceSerializer, PaymentAttemptSerializer, LedgerEntrySerializer, RecordPaymentSerializer
from .services import SubscriptionService, InvoiceService, PaymentService

class SafeModelViewSet(viewsets.ModelViewSet):
    def handle_exception(self, exc):
        return super().handle_exception(exc)
    def perform_create(self, serializer):
        try: serializer.save()
        except IntegrityError: raise ValidationError("This record conflicts with an existing record or business constraint.")

class PlanViewSet(SafeModelViewSet):
    queryset=Plan.objects.all(); serializer_class=PlanSerializer
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        plan=self.get_object(); plan.is_active=False; plan.save(update_fields=["is_active","updated_at"]); return Response(self.get_serializer(plan).data)

class CustomerViewSet(SafeModelViewSet):
    queryset=Customer.objects.all(); serializer_class=CustomerSerializer
    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        customer=self.get_object(); qs=LedgerEntry.objects.filter(customer=customer).select_related("invoice")
        return Response(LedgerEntrySerializer(qs, many=True).data)

class SubscriptionViewSet(SafeModelViewSet):
    queryset=Subscription.objects.select_related("customer","plan").all(); serializer_class=SubscriptionSerializer
    def create(self, request, *args, **kwargs):
        serializer=self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        data=serializer.validated_data
        try:
            sub=SubscriptionService.create(customer_id=data["customer"].id, plan_id=data["plan"].id, status=data.get("status","active"), start_date=data.get("start_date",timezone.now()), end_date=data.get("end_date"))
        except IntegrityError: raise ValidationError("Customer already has an active subscription to this plan.")
        return Response(self.get_serializer(sub).data, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub=self.get_object()
        if sub.status != "active": raise ValidationError("Only active subscriptions can be cancelled.")
        sub.status="cancelled"; sub.cancelled_at=timezone.now(); sub.save(update_fields=["status","cancelled_at","updated_at"])
        return Response(self.get_serializer(sub).data)

class InvoiceViewSet(SafeModelViewSet):
    queryset=Invoice.objects.select_related("subscription","customer").all(); serializer_class=InvoiceSerializer
    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        subscription_id=request.data.get("subscription_id")
        if not subscription_id: raise ValidationError({"subscription_id":"This field is required."})
        invoice=InvoiceService.generate(subscription_id)
        return Response(self.get_serializer(invoice).data, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        invoice=self.get_object(); serializer=RecordPaymentSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        attempt, updated=PaymentService.record(invoice_id=invoice.id, **serializer.validated_data)
        return Response({"payment_attempt":PaymentAttemptSerializer(attempt).data,"invoice":self.get_serializer(updated).data}, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=["get"])
    def payment_attempts(self, request, pk=None):
        invoice=self.get_object(); return Response(PaymentAttemptSerializer(invoice.payment_attempts.all(), many=True).data)

class PaymentAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=PaymentAttempt.objects.select_related("invoice").all(); serializer_class=PaymentAttemptSerializer
class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=LedgerEntry.objects.select_related("customer","invoice").all(); serializer_class=LedgerEntrySerializer
