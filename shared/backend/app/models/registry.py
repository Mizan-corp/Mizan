"""Registers every SQLAlchemy model (core + industry modules) on Base.metadata.

Import this before relying on metadata-wide operations (create_all, mapper
configuration across modules). Each service calls it once at startup.
"""


def load_all_models() -> None:
    import app.platform.archive.models
    import app.platform.audit.models
    import app.platform.billing.models
    import app.platform.permissions.models
    import app.activities.general.modules.inventory.models.collection
    import app.activities.general.modules.contacts.models.customer_payment
    import app.platform.notifications.models.device_token
    import app.platform.licensing.models
    import app.platform.notifications.models.notification
    import app.platform.auth.models.owner
    import app.activities.general.modules.hr.models.employee
    import app.activities.general.modules.accounting.models
    import app.activities.general.modules.finance.models.expense
    import app.activities.general.modules.finance.models.financial_category
    import app.activities.general.modules.hr.models.hr_advance
    import app.activities.general.modules.hr.models.hr_attendance
    import app.activities.general.modules.hr.models.hr_audit_log
    import app.activities.general.modules.hr.models.hr_payroll_legacy
    import app.activities.general.modules.hr.models.hr_settings
    import app.activities.general.modules.hr.models.hr_shift
    import app.activities.general.modules.hr.models.hr_sync_log
    import app.activities.general.modules.contacts.models.party
    import app.activities.general.modules.finance.models.payment_wallet
    import app.activities.general.modules.hr.models.payroll
    import app.activities.general.modules.hr.models.payroll_legacy
    import app.activities.general.modules.finance.models.period
    import app.activities.general.modules.inventory.models.product
    import app.activities.general.modules.purchases.models.purchase
    import app.activities.general.modules.purchases.models.purchase_price_history
    import app.activities.general.modules.purchases.models.purchase_receipt
    import app.activities.general.modules.purchases.models.purchase_return
    import app.activities.general.modules.finance.models.safe
    import app.activities.general.modules.sales.models.sale
    import app.activities.general.modules.sales.models.sale_payment
    import app.models.schema_migration
    import app.platform.settings.models
    import app.platform.community.models
    import app.platform.developers.models
    import app.platform.themes.models
    import app.platform.marketplace.listings
    import app.platform.auth.services.owner_mail
    import app.framework.fields  # workspace_fields
    import app.framework.layouts  # workspace_layouts
    import app.framework.files  # workspace_files
    import app.framework.composition  # module_retention
    import app.framework.storage  # storage_usage
    import app.framework.idempotency  # idempotency_keys
    import app.activities.general.modules.pos.models
    import app.activities.general.modules.inventory.models.stock
    import app.activities.general.modules.inventory.models.stock_balance
    import app.activities.general.modules.purchases.models.supplier_price
    import app.activities.general.modules.purchases.models.supplier_transaction
    import app.platform.tenancy.models
    import app.platform.tenancy.activity_change
    import app.platform.auth.models.user
    import app.activities.general.modules.inventory.models.warehouse
    import app.activities.general.modules.inventory.models.warehouse_product_status
    import app.activities.restaurant.modules.kitchen_display.models
    import app.activities.restaurant.modules.restaurant.models
    import app.activities.school.modules.school.models
    import app.activities.pharmacy.modules.pharmacy.models
    import app.activities.pharmacy.modules.batches.models
    import app.activities.consulting.modules.services.models
    import app.activities.wholesale.modules.wholesale.models
    import app.activities.logistics.modules.logistics.models
    import app.activities.warehousing.modules.wms.models
    import app.activities.ecommerce.modules.ecommerce.models
    import app.activities.healthcare.modules.healthcare_clinic.models
    import app.activities.healthcare.models
    import app.activities.legal.modules.law.models
    import app.activities.travel.modules.travel.models
    import app.activities.hotel.modules.hospitality.models
    import app.activities.gym.modules.gym.models
    import app.activities.salon.modules.salon.models
    import app.activities.agency.modules.agency.models
    import app.activities.maintenance.modules.field_service.models
    import app.activities.manufacturing.modules.manufacturing.models
    import app.activities.food.modules.food_manufacturing.models
    import app.activities.pharmaceuticals.modules.pharma_manufacturing.models
    import app.activities.printing.modules.printing.models
    import app.activities.construction.modules.construction.models
    import app.activities.property.modules.real_estate.models
    import app.activities.agriculture.modules.agriculture.models
    import app.activities.energy.modules.energy.models
    import app.activities.banking.modules.banking.models
    import app.activities.insurance.modules.insurance.models
    import app.activities.government.modules.government.models
    import app.activities.entertainment.modules.events.models
    import app.activities.petroleum.modules.oil_gas.models
    import app.activities.general.modules.storefront.models
    import app.integrations.pos_hardware.models
    import app.platform.automation_worker.models
    import app.platform.core.models
    import app.activities.general.modules.inventory.models
    import app.activities.general.modules.pos.models
    import app.activities.general.modules.sales.models
    import app.activities.general.modules.purchases.models
    import app.activities.general.modules.finance.models
    import app.activities.general.modules.contacts.models
    import app.activities.general.modules.hr.models
