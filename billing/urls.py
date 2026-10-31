from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, CustomerViewSet, SubscriptionViewSet, InvoiceViewSet, PaymentAttemptViewSet, LedgerEntryViewSet
router=DefaultRouter()
router.register("plans", PlanViewSet)
router.register("customers", CustomerViewSet)
router.register("subscriptions", SubscriptionViewSet)
router.register("invoices", InvoiceViewSet)
router.register("payment-attempts", PaymentAttemptViewSet)
router.register("ledger-entries", LedgerEntryViewSet)
urlpatterns=router.urls
