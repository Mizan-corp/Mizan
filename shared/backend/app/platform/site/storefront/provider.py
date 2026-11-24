"""Reviewed site-owned provider. The caller owns site.manage authorization.

Tenant verification is explicit even though the existing DB listener also scopes rows.
Never return tenant/legal name as an implicit fallback or expose the full settings blob.
"""
from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.framework.storefront_runtime import Provider, SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from app.platform.site.service import get_settings

CONTRACT = json.loads((Path(__file__).parent / 'contract.json').read_text())


def site_provider(db: AsyncSession) -> Provider:
    async def read(context: SourceContext, source_id: str) -> dict | None:
        if current_tenant_id.get() != context.tenant_id or source_id != 'appearance':
            raise SourceUnavailable('Source unavailable.')
        value = await get_settings(db)
        header = value.get('header')
        brand = header.get('brand') if isinstance(header, dict) else None
        if brand is not None and (not isinstance(brand, str) or len(brand) > 80):
            raise SourceUnavailable('Saved website brand is invalid.')
        return {'brand': brand}
    return Provider('site', CONTRACT, read, platform_core=True)
