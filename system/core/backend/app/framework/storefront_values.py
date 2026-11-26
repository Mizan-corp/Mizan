"""Reviewed product value types. No provider reads, network fetches or publication effects."""
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit
from app.framework.storefront_runtime import ProjectionInvalid

MONEY_SCHEMA = 'mizan.money.experimental.v0'
MEDIA_SCHEMA = 'mizan.media.experimental.v0'
# Website currency must be chosen explicitly. Finite supported set is not FX support.
CURRENCIES = frozenset({'EGP', 'USD', 'EUR', 'GBP', 'SAR', 'AED'})


def money_value(amount, currency):
    if not isinstance(currency, str) or currency not in CURRENCIES or not isinstance(amount, (str, Decimal)):
        raise ProjectionInvalid('Explicit supported currency and exact decimal amount required.')
    try:
        value = Decimal(amount)
    except InvalidOperation:
        raise ProjectionInvalid('Invalid display amount.') from None
    if not value.is_finite() or value < 0 or value > Decimal('9999999999.99') or value.as_tuple().exponent < -2:
        raise ProjectionInvalid('Display amount is outside the reviewed bound.')
    return {'schema': MONEY_SCHEMA, 'amount': format(value.quantize(Decimal('0.01')), 'f'), 'currency': currency}


def check_money(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'amount', 'currency'} or value['schema'] != MONEY_SCHEMA:
        raise ProjectionInvalid('Exact typed money required.')
    result = money_value(value['amount'], value['currency'])
    if result != value:
        raise ProjectionInvalid('Money must use canonical two-place decimal text.')
    return result


def money_text(value):
    value = check_money(value)
    # A display value, no tax, discount, exchange-rate or checkout calculation.
    return value['amount'] + ' ' + value['currency']


def checked_media_url(url, tenant_id):
    if not isinstance(url, str) or len(url) > 1024 or any(ord(c) < 33 or ord(c) == 127 for c in url) or '\\' in url:
        raise ProjectionInvalid('Invalid product media address.')
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ProjectionInvalid('Invalid product media host.') from None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProjectionInvalid('Media credentials and parameters are refused.')
    # Ownership is checked separately against a tenant product_image file record.
    # URLs here are not fetched by the provider, so they cannot become server-side requests.
    prefix = '/t/' + str(tenant_id) + '/product_image/'
    if parsed.scheme == 'https' and parsed.hostname and parsed.hostname.endswith('.public.blob.vercel-storage.com'):
        if port is not None or not parsed.path.startswith(prefix):
            raise ProjectionInvalid('Product media must be tenant-scoped public storage.')
    elif not parsed.scheme and not parsed.netloc and parsed.path.startswith('/uploads' + prefix):
        pass
    else:
        raise ProjectionInvalid('Only reviewed tenant product-image storage is supported.')
    if '..' in parsed.path or '%' in parsed.path or not re.fullmatch(r'.+\.(?:png|jpg|jpeg|gif|webp)', parsed.path, re.IGNORECASE):
        raise ProjectionInvalid('Unsupported product image path.')
    return url


def media_value(url, alt, tenant_id):
    if not isinstance(alt, str) or len(alt) > 200:
        raise ProjectionInvalid('Bounded image description required.')
    return {'schema': MEDIA_SCHEMA, 'src': checked_media_url(url, tenant_id), 'alt': alt}


def check_media(value, tenant_id):
    if not isinstance(value, dict) or set(value) != {'schema', 'src', 'alt'} or value['schema'] != MEDIA_SCHEMA:
        raise ProjectionInvalid('Exact typed media required.')
    return media_value(value['src'], value['alt'], tenant_id)
