# Screens

Full pages of `inventory`, one file each (`<Name>Page.tsx`). A variant can replace or add screens.

- `CategoriesPage` (`/inventory/categories`): categories and their subcategories.
- `AdjustmentsPage` (`/inventory/adjustments`): adjustments, damage, opening stock, transfers.
- `CollectionsPage` (`/inventory/collections`): collections and what a branch can assemble.
- `WarehousesPage` (`/inventory/warehouses`, `settings`): warehouses and branches.

The balances screen is still `../InventoryPage.tsx` and the products screen
`src/features/products/ProductsPage.tsx`; both use this module's header and components.
