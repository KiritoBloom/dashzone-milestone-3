# DashZone Milestone 3 — API Contract

Agreed contract for Team 117. This is the agreement between the FastAPI backend (Mohamed) and the Next.js frontend (Adham, Karim, Adam, Eyad). If anything here is wrong, change this file, not the code.

Stack: FastAPI backend, Next.js frontend, SQL Server database. Base URL for the backend: `http://localhost:8000/api`.

## Conventions

### Sessions and IDs

- On login the backend creates a session (signed cookie) holding `user_id`, `user_type` and `username`. Every endpoint reads the signed-in user's ID from the session.
- **The frontend never sends a user ID.** No `customer_id`, `partner_id`, `rider_id` or `admin_id` in any request body, except where the admin is acting on someone else's record (those IDs are in the URL, see the Admin section).
- The backend fills in the signed-in user's ID when it calls the procedure.

### Response shape

Every endpoint returns the same shape:

```json
{
  "ok": true,
  "code": 0,
  "message": "The voucher SUMMER10 was issued to Mona Ali.",
  "data": { "...": "..." }
}
```

- `ok` is true when `code` is 0.
- `code` is the Milestone 2 procedure's return code (0 to -9). Reads (views and table functions) return 0.
- `message` is the user-facing message for that code, in the user's words. Never a raw SQL error, never a bare error code.
- `data` holds the rows or the created record, or null when there is nothing to return.

### HTTP methods

- `GET` for reads (views and table-valued functions).
- `POST` for everything that changes something (procedures). No PATCH or DELETE, to keep it simple.
- A failed validation in the frontend is shown before the request is sent. The backend still relies on the procedure's return code.
- Report endpoints that take `?from=` and `?to=` default to the last 30 days up to today when either is omitted.
- Pages link to each other through links, buttons and menus, not by changing the URL. Actions that cannot be undone (blacklisting, suspending, cancelling an order, deleting an address) ask the user to confirm first and say what will happen.

### Validation (frontend, before calling the backend)

Required fields, numbers, dates, 11-digit phone, 16-digit card. Hide passwords. Lists that pick an existing record (zone, business, product, address, card, voucher) show names, not only IDs.

### Return codes and messages (Table 3.1)

| Code | Meaning | Example message |
|------|---------|-----------------|
| 0 | Success | The voucher SUMMER10 was issued to Mona Ali. |
| -1 | Invalid input | The discount must be between 0 and 50% of the price. Enter a smaller amount. |
| -2 | Duplicate | This promo code already exists. Choose another code. |
| -3 | Not allowed | Your account is blacklisted, so you cannot check out. Contact support. |
| -4 | Wrong status | This order cannot be cancelled because a part of it was already picked up. |
| -5 | Zone mismatch | This business does not deliver to your active address. Change your active address or choose another business. |
| -6 | Limit exceeded | You can order at most 10 of one product. Lower the quantity. |
| -7 | Payment cannot be made | Your wallet balance is not enough. Choose Cash or Card. |
| -8 | No available rider | No rider is available in your zone right now. Try again in a few minutes. |
| -9 | Nothing to process | Your cart is empty. Add products before checking out. |

A login function returning 0 means "Wrong username or password". The messages above are examples: name the problem in the user's words and say how to fix it.

## Auth (Mohamed)

Login flow for all four types: call the validation function with username and password. If it returns 1, call `h_GetUserId(username)` for the ID and create the session. If it returns 0, show "Wrong username or password".

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `POST /auth/customer/register` | `Customer_Register` | first_name, middle_name (optional), last_name, username, password, email, phone (11 digits), dob (optional) | new customer |
| `POST /auth/partner/register` | `Partner_Register` | first_name, middle_name (optional), last_name, username, password, email, phone (11 digits), dob (optional) | new partner |
| `POST /auth/rider/register` | `Rider_Register` | first_name, middle_name (optional), last_name, username, password, email, phone (11 digits), dob (optional), vehicle_type, plate_no, license_no, zone_id | new rider |
| `POST /auth/customer/login` | `CustomerLoginValidation` + `h_GetUserId` | username, password | session started, customer profile |
| `POST /auth/partner/login` | `PartnerLoginValidation` + `h_GetUserId` | username, password | session started, partner profile |
| `POST /auth/rider/login` | `RiderLoginValidation` + `h_GetUserId` | username, password | session started, rider profile |
| `POST /auth/admin/login` | `AdminLoginValidation` + `h_GetUserId` | username, password | session started, admin profile |
| `POST /auth/logout` | (clear session) | — | — |
| `GET /auth/me` | helper for the signed-in type | — | user_id, user_type, username, name, profile |

Admins only log in, there is no admin self-register. `Change_Password` exists in Milestone 2 but no Milestone 3 page requires it, so it is not in this contract.

## Shared (Mohamed)

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `GET /zones` | `h_ZoneList` | — | all zones with delivery fees |
| `GET /health` | (database ping) | — | status, database ok/down |

Note: `GET /health` is at the server root (`http://localhost:8000/health`), not under `/api`. It answers HTTP 503 with `"database": "down"` when SQL Server is unreachable.

## Admin (Adham)

Admin pages read the signed-in admin's ID from the session. The IDs in the URLs below are the record being acted on, not the signed-in user.

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `GET /admin/me` | `h_AdminProfile` | — | name, role, zone (for Zone Admin) |
| `GET /admin/pending-businesses` | `PendingBusinessApprovals` | — | businesses awaiting approval |
| `POST /admin/businesses/{business_id}/approve` | `Approve_Business` | — | code 0 on success |
| `POST /admin/businesses/{business_id}/reject` | `Reject_Business` | — | code 0 on success |
| `GET /admin/businesses?status=&type=` | `allBusinessProfiles` | status, type (optional filters) | business profiles |
| `POST /admin/businesses/{business_id}/suspend` | `Suspend_Business` | reason | code 0 on success |
| `POST /admin/businesses/{business_id}/reinstate` | `Reinstate_Business` | — | code 0 on success |
| `GET /admin/suspended-businesses` | `h_SuspendedBusinesses` | — | suspended businesses with reasons |
| `POST /admin/admins` | `Create_Admin` | first_name, middle_name (optional), last_name, username, password, email, phone (11 digits), dob (optional), role ("Super Admin" or "Zone Admin"), zone_id (required for Zone Admin, not allowed for Super Admin) | new admin (admin_id, username, role) |
| `POST /admin/admins/{admin_id}/assign-zone` | `Assign_Admin_Zone` | zone_id | code 0 on success |
| `GET /admin/admins` | `h_AdminList` | — | all admins |
| `POST /admin/vouchers` | `Issue_Voucher` | customer_id, promo_code, is_percentage, amount, expiry_date | code 0 on success (no voucher data returned; re-read GET /admin/vouchers) |
| `GET /admin/vouchers` | `ActiveVouchers` | — | active vouchers |
| `GET /admin/customers` | `h_CustomerList` | — | customers (for voucher and blacklist pickers) |
| `POST /admin/customers/{customer_id}/blacklist` | `Blacklist_Customer` | reason | code 0 on success |
| `POST /admin/customers/{customer_id}/lift-blacklist` | `Lift_Customer_Blacklist` | — | code 0 on success |
| `GET /admin/blacklisted` | `h_BlacklistedCustomers` | — | blacklisted customers, reason, who can lift it |
| `GET /admin/dashboard` | `Platform_Health_Snapshot`, `Reconcile_Order_Totals` | — | health snapshot, orders whose totals do not match (warning) |
| `POST /admin/zones` | `Create_Zone` | zone_name, delivery_fee | code 0 on success (no zone data returned) |
| `POST /admin/zones/{zone_id}/fee` | `Update_Zone_Fee` | new_fee | code 0 on success |
| `GET /admin/zones/compare?zone_id=&from=&to=` | `BusinessesPerZone`, `ZoneDeliveryPerformance`, `ZoneOrderReport` | zone_id (optional; when omitted the zone report is null), from, to (optional, default last 30 days) | businesses, orders, delivery speed, commission |
| `GET /admin/revenue?date=` | `Daily_Revenue_Report` | date (optional, defaults to today) | revenue of the day |
| `GET /admin/riders/top?from=&to=` | `TopRiders`, `RiderPerformanceSummary` | from, to (optional, default last 30 days) | best riders, who is falling behind |
| `GET /admin/market` | `TopSellingProducts`, `BusinessRatingsSummary` | — | what sells most, loved and avoided businesses |

Super Admin only: create admin, assign or move a Zone Admin, suspend and reinstate a business, create a zone, change a zone fee. The frontend hides those actions for a Zone Admin. (The SQL itself would let a Zone Admin suspend a business in their own zone; the backend enforces Super Admin only, per the milestone doc.)

## Partner (Karim)

The business and products are the signed-in partner's own. No business ID in the request, it comes from the session.

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `GET /partner/business` | `h_MyBusiness`, `h_BusinessPhones` | — | my business, status, suspension reason, phones |
| `POST /partner/business` | `Register_Business` | name, description (optional), link_website (optional), zone_id, opening_hour, closing_hour, expected_delivery_time, phone (optional, 11 digits), business_type ("Restaurant" or "Pharmacy"), cuisine_type and food_category (Restaurant only), pharmacy_type (Pharmacy only) | new business |
| `POST /partner/business/update` | `Update_Business_Info` | opening_hour, closing_hour, phone, link_website (all optional; only the fields sent are changed) | updated business |
| `GET /partner/products` | `h_MyProducts` | — | my products, available or not |
| `POST /partner/products` | `Upsert_Product` | name, description (optional), category, price, is_available (optional, defaults to true) | new product |
| `POST /partner/products/{product_id}` | `Upsert_Product` | name, description (optional), category, price, is_available (optional, defaults to true) | updated product |
| `POST /partner/products/{product_id}/toggle` | `Toggle_Product_Status` | is_available | code 0 on success |
| `POST /partner/products/{product_id}/promotion` | `Set_Product_Promotion` | discount_amount (0 removes it) | code 0 on success |
| `GET /partner/performance?from=&to=` | `BusinessSalesReport`, `BusinessFeedbackOverview` | from, to (optional, default last 30 days) | revenue by product, customer feedback |

For `Upsert_Product`, a new product is created when `product_id` is null, otherwise the existing product is updated.

## Rider (Adam)

The rider is the signed-in rider. No rider ID in the request, it comes from the session.

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `GET /rider/me` | `h_RiderProfile` | — | rider profile, current availability |
| `POST /rider/availability` | `Set_Rider_Availability` | is_available | code 0 on success |
| `GET /rider/deliveries` | `My_Active_Deliveries` | — | active deliveries with their journey stage |
| `POST /rider/deliveries/{delivery_id}/pickup` | `Mark_Picked_Up` | — | code 0 on success |
| `POST /rider/deliveries/{delivery_id}/deliver` | `Mark_Delivered` | — | code 0 on success |
| `GET /rider/earnings?from=&to=` | `My_Earnings` | from, to (optional, default last 30 days) | earnings in the period |
| `GET /rider/rating` | `My_Rating_Summary` | — | customer rating summary |
| `GET /rider/history?from=&to=` | `My_Delivery_History` | from, to (optional, default last 30 days) | delivery history |

## Customer (Eyad)

The customer is the signed-in customer. No customer ID in the request, it comes from the session. The cart is the active cart of the active address.

| Endpoint | Calls | Request | Response data |
|----------|-------|---------|---------------|
| `GET /customer/me` | `h_CustomerProfile` | — | name, wallet balance, active address |
| `GET /customer/addresses` | `h_MyAddresses` | — | my addresses |
| `POST /customer/addresses` | `Add_Customer_Address` | description, zone_id | new address |
| `POST /customer/addresses/{address_id}` | `Update_Delete_Customer_Address` | action ("Update", "Delete" or "Remove"); description and zone_id are required only for "Update" | updated or deleted address |
| `POST /customer/addresses/{address_id}/activate` | `Change_Active_Address` | — | new active address |
| `GET /customer/cards` | `h_MyCards` | — | my cards, last 4 digits only |
| `POST /customer/cards` | `Add_Card` | card_no (16 digits), card_holder_name, expiration_date | new card |
| `GET /customer/cart` | `h_MyActiveCart`, `h_CartItems` | — | active cart and its items with prices |
| `POST /customer/cart` | `Create_Cart` | — | new cart for the active address |
| `POST /customer/cart/items` | `Add_To_Cart` | product_id, quantity, notes (optional) | added item |
| `POST /customer/cart/items/{product_id}/remove` | `Remove_From_Cart` | — | code 0 on success |
| `GET /customer/vouchers` | `h_MyVouchers` | — | my usable vouchers |
| `POST /customer/checkout/preview` | `Calculate_Voucher_Discount` | voucher_id (optional) | cart_id, subtotal, delivery fees, discount, total, per-business breakdown |
| `POST /customer/checkout` | `Checkout_Cart` | voucher_id (optional, null when none), payment_method ("Cash", "Card" or "Wallet"), card_id (only when paying by Card, must be null otherwise) | new order |
| `GET /customer/businesses/search?keyword=` | `Search_Platform` | keyword | matching businesses |
| `GET /customer/businesses/category?category=&address_id=` | `Nearby_Businesses_By_Category` | category, address_id | businesses in the category near that address |
| `GET /customer/businesses/{business_id}` | `h_BusinessDetails`, `h_BusinessProducts`, `BusinessRatingsSummary` | — | details, open now, rating, available products |
| `POST /customer/favorites/toggle` | `Toggle_Favorite` | item_id, item_type ("Business" or "Product") | item_id, item_type, favorited (true/false for products, null for businesses) |
| `GET /customer/favorites` | `My_Favorites` | — | favorite products |
| `GET /customer/recommended` | `Recommended_Products` | — | recommended products |
| `GET /customer/orders` | `My_Order_History`, `h_OrderSubOrders`, `ZoneDeliveryPerformance` | — | orders with each part's progress and an estimated arrival for orders on the way |
| `POST /customer/orders/{order_id}/cancel` | `Cancel_Order` | — | refund amount |
| `POST /customer/orders/{order_id}/reorder` | `Reorder` | address_id | new cart with the reordered items (cart_id, items), not a new order |
| `POST /customer/orders/suborders/{suborder_id}/feedback` | `Submit_Feedback` | headline, description (optional), rating (1-5) | code 0 on success |
| `POST /customer/orders/suborders/{suborder_id}/rate-rider` | `Rate_Rider` | rider_rating (1-5) | code 0 on success |

The estimated arrival for an order on the way is predicted from data the database already has: the business's expected delivery time and the zone's real delivery times (`ZoneDeliveryPerformance`). The backend computes it and returns it in the order data.

Checkout and cancel return no IDs from the SQL, so the backend reads the new order and the refund amount back from `My_Order_History` before replying. Checkout preview: the backend computes the order subtotal from the cart and passes it to `Calculate_Voucher_Discount`; the frontend only sends `voucher_id`.

Only the last 4 digits of a card number are ever shown. Checkout asks the user to confirm the total breakdown before it runs.

## Decisions

1. Session tech: signed cookie sessions in FastAPI. Decided and implemented: the backend uses Starlette `SessionMiddleware` with a signed cookie holding `user_id`, `user_type` and `username`.
2. The estimated arrival formula: decided and implemented. Per suborder on the way: ETA = `order_date` + (`expected_delivery_time` + zone average tracking time from `ZoneDeliveryPerformance`) minutes. The order ETA is the latest of its suborders; it is null when nothing is on the way.
3. This contract covers every requirement in Milestone 3 sections 3.1 to 3.6. If a page needs data no helper provides, add your own helper SQL to `sql/Team_117.sql` and add the endpoint here.
