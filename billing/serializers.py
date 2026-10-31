from rest_framework import serializers
from .models import Plan, Customer, Subscription, Invoice, PaymentAttempt, LedgerEntry

class PlanSerializer(serializers.ModelSerializer):
    class Meta: model=Plan; fields="__all__"; read_only_fields=["id","created_at","updated_at"]
    def validate_price(self, value):
        if value <= 0: raise serializers.ValidationError("Plan price must be greater than 0.")
        return value
class CustomerSerializer(serializers.ModelSerializer):
    class Meta: model=Customer; fields="__all__"; read_only_fields=["id","created_at","updated_at"]
    def validate_email(self, value): return value.strip().lower()
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta: model=Subscription; fields="__all__"; read_only_fields=["id","created_at","updated_at","cancelled_at"]
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta: model=Invoice; fields="__all__"; read_only_fields=["id","amount_due","amount_paid","currency","status","period_start","period_end","created_at"]
class PaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta: model=PaymentAttempt; fields="__all__"; read_only_fields=["id","created_at"]
class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta: model=LedgerEntry; fields="__all__"; read_only_fields=["id","customer","invoice","entry_type","amount","currency","reference_id","description","created_at"]
class RecordPaymentSerializer(serializers.Serializer):
    amount=serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    currency=serializers.CharField(max_length=3, default="INR")
    status=serializers.ChoiceField(choices=["succeeded","failed"])
    provider_reference=serializers.CharField(max_length=180)
    failure_reason=serializers.CharField(required=False, allow_blank=True, default="")
