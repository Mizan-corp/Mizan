# Experimental module storefront contract foundation

Status: OFFLINE VALIDATOR ONLY. Not discovered by the module loader, not exposed by an API, not accepted by the page-tree runtime, and not an authorization policy. The schema identifier is explicitly experimental. Do not publish a module as storefront-capable based on this file passing validation.

## Ownership and evidence

The owner's 23 November 2026 direction separates platform-owned generic Explorer/binding tools from optional module-local storefront declarations. Each module should describe its available data, required/optional pages and useful element examples. Static content remains editable; Dynamic should select compatible module data. Compatibility must respect meaning and context, not merely primitive type. The agreed architecture does not authorize exposing raw ERP tables or choosing a commerce module's ownership on its behalf.

Current source: the official module loader validates v2 manifest metadata and reads installed/enabled module state through existing workflows. SDK/platform manifest copies validate current page trees. Neither source contains a module storefront data/provider contract. The frontend built-in asset relationship catalog is not a package format. This foundation deliberately does not alter those existing contracts.

## What this code supplies

`mizan_sdk.storefront` and `app.framework.storefront` are byte-identical, standard-library-only pure validators. `storefront_contract_problems` validates a finite bounded JSON declaration with a schema identifier, owning module identity, explicitly public-projection source descriptions, public fields and optional/required page needs. Exact field type plus finite semantic pairs limit suggested presentation elements. Unknown properties fail closed, including provider URLs, code, SQL, permissions, commands and effect-bearing installation defaults.

`storefront_binding_problems` checks a proposed dynamic reference against that declaration and a target supplied by a trusted block registry. Module/source/field, semantic type, cardinality and target presentation must agree. Empty/hide behavior is explicit. A collection cannot fill a scalar field without a future scoped item contract. The validator never executes or imports a module, resolves a provider, queries tenant data, grants access, installs dependencies or writes a page.

The fixture under the test harness is synthetic, with title/image/sale-price metadata only. It is not a new Products module or an endorsement that such a source exists. Module-owned real declarations will live inside their own folders when their providers and discovery rules exist. The current example file is kept in test fixtures so it cannot be accidentally discovered or activated.

## Deliberately unresolved

- Provider registry and trusted module discovery, installation/enabled checks, activity features/variants and version negotiation.
- Server-enforced public/published projection, tenant and shopper context, authorization, rate limits, pagination, filtering and caching.
- Money's runtime value/currency representation and image/media security. These validators validate metadata, not values.
- Collection repetition and current-item context. Scalar content cannot masquerade as a collection renderer.
- Real native block property schemas and presentation components. The names here do not add Price/Link/collection blocks to the renderer.
- Dynamic page-tree serialization, server rendering, studio preview and safe persisted fallback behavior.
- Commands, mutation permission, checkout/auth and effects. No module or network command is executable from this declaration.
- Site kit installation, replacement/merge policy, signed packages and shared revision lifecycle.
- Actual visual example media and recommendations. The current `elements` list is metadata only, not the requested picture library.

A module can lie about public exposure. Successful validation cannot prove a provider is safe; runtime review and policy checks remain mandatory. No self-declared metadata may grant access.

## Verification

`python sdk/python/tests/test_storefront.py` runs offline tests for exact platform/SDK parity, owner identity, denied unknown fields/code/provider/commands, explicit public field exposure, semantic restrictions, wrong element types, duplicate identities, missing page source, refused replacement settings, finite bounded JSON and malformed shapes, compatible binding, incompatible module/type/meaning/cardinality/element and nonmutation. These are contract unit tests, not service or full-application acceptance.
