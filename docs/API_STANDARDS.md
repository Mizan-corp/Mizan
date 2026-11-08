# Mizan ERP — API Standards

## 1. Protocol & Format
- **RESTful JSON:** All endpoints follow standard HTTP methods (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
- **Base URL:** `/api/v1` (with serverless fallback `/api` on Vercel).
- **Encoding:** `UTF-8` with explicit support for Arabic script in headers, query strings, and payloads.

## 2. Standard Response Envelope
Successful responses return JSON data directly or wrapped in standard schemas:
```json
{
  "success": true,
  "data": { ... },
  "message": "تم حفظ البيانات بنجاح"
}
```

For paginated collections:
```json
{
  "items": [ ... ],
  "total": 142,
  "page": 1,
  "limit": 25,
  "has_more": true
}
```

## 3. Error Responses
All errors must return consistent RFC 7807-style error structures:
```json
{
  "detail": "رقم الهوية الوطنية مسجل بالفعل لمريض آخر في نفس المنشأة",
  "code": "DUPLICATE_NATIONAL_ID",
  "field": "national_id"
}
```

## 4. Authentication & Headers
- **Bearer Token:** `Authorization: Bearer <jwt_access_token>`.
- **Tenant Scope:** Inferred from user membership, or explicitly passed via `X-Tenant-Slug` or `X-Facility-ID`.
- **CSRF Token:** `X-CSRF-Token` header on state-modifying requests (`POST`, `PUT`, `DELETE`) when using cookie sessions.
