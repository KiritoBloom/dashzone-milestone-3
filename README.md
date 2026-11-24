# DashZone — Milestone 3

Data Base I, Winter 2026, **Team 117**.

**Deadline: Thursday 3 December 2026, 11:59 PM.**
**Submission: one zip named `Team_117.zip`** — source code + `Team_117.sql` (only if we add our own helper SQL).

## What we are building

A web app on top of our Milestone 2 SQL Server database. The database is already given to us (database script + `seed_data.sql` on CMS). **We do not rewrite the Milestone 2 business logic.** Every action on the website calls the matching Milestone 2 procedure, function or view.

## Stack (agreed)

- **Backend:** FastAPI (Python)
- **Frontend:** Next.js
- **Database:** SQL Server

## How to run it

1. In SQL Server, run the Milestone 2 database script, then `seed_data.sql`.
2. Backend: `cd backend`, `pip install -r requirements.txt`, `uvicorn main:app --reload`
3. Frontend: `cd frontend`, `npm install`, `npm run dev`
4. Test login: Super Admin, username `mona.hassan`, password `Pass@001`

## Who does what

Each person owns their part end to end: the API calls and the pages for it. If your part needs data the given helpers do not provide, add your own helper SQL and put it in `sql/Team_117.sql`.

### Mohamed Ahmed (leader) — Backend and infrastructure + UI polish

**Backend — the foundation everything else plugs into:**
- SQL Server connection layer (pyodbc) and config
- Login and session for all 4 user types: `AdminLoginValidation`, `PartnerLoginValidation`, `RiderLoginValidation`, `CustomerLoginValidation`, plus `h_GetUserId` after login
- Return-code messages (Table 3.1 in the milestone doc): every return code (0 to -9) becomes a clear message in the user's words, never a raw SQL error or a bare error code
- Shared validation: required fields, numbers, dates, 11-digit phone, 16-digit card, hide passwords
- Shared helpers: dropdowns and lists that show names, not only IDs; confirm dialogs before anything that cannot be undone
- General requirements (3.1, applies to every page): start page with Login and Register for each user type (admins only log in), home page per user type, Log out button on every page, pages open only for a signed-in user of that type, users only see and change their own records, navigation by links, buttons and menus (not by changing the URL)
- The final `Team_117.zip` and the run instructions in this README

**UI polish (bonus role):**
- One shared layout and CSS for the whole app, so all pages look consistent
- Polish every page: spacing, typography, buttons, forms, tables, success and error messages
- There is a bonus for exceptional UI design, this is the extra credit

### Adham Ahmed Oriby — Admin component (3.2 + 3.3)

**3.2 Accounts and governance:**
- a) Admin login + home page (name, role, zone for a Zone Admin; hide Super Admin-only features from Zone Admins). Uses: `AdminLoginValidation`
- b) Businesses awaiting approval, approve or reject each one from the same page. Uses: `PendingBusinessApprovals`, `Approve_Business`, `Reject_Business`
- c) Suspend an Active business with a reason, reinstate a Suspended one (Super Admin only). Browse all business profiles filtered by status and type. Uses: `allBusinessProfiles`, `Suspend_Business`, `Reinstate_Business`
- d) Create a new admin, assign or move a Zone Admin to a zone (Super Admin only). Uses: `Create_Admin`, `Assign_Admin_Zone`
- e) Issue a voucher to a customer, view all active vouchers. Uses: `Issue_Voucher`, `ActiveVouchers`
- f) Blacklist a customer with a reason, lift a blacklist I set. Uses: `Blacklist_Customer`, `Lift_Customer_Blacklist`

**3.3 Zones and platform insights:**
- a) Platform dashboard on the admin home page: is the platform healthy today, and is anything wrong? Orders whose totals do not match are a warning the admin must not miss. Uses: `Platform_Health_Snapshot`, `Reconcile_Order_Totals`
- b) View all zones with delivery fees, create a zone, change a zone's fee (Super Admin only). Uses: `Create_Zone`, `Update_Zone_Fee`
- c) Zone comparison: which zone is strongest and which needs help? Compare by businesses, orders, delivery speed and commission, for a date range I choose. Uses: `BusinessesPerZone`, `ZoneDeliveryPerformance`, `ZoneOrderReport`
- d) Revenue of a day: where did the money come from, and how much did the platform earn? Uses: `Daily_Revenue_Report`
- e) Riders: who are the best riders of a period, and who is falling behind? Uses: `TopRiders`, `RiderPerformanceSummary`
- f) Market: what sells most, and which businesses do customers love or avoid? Uses: `TopSellingProducts`, `BusinessRatingsSummary`

### Karim Ahmed Elbehery — Partner component (3.4a–d)

- a) Register as a partner and log in. Uses: `Partner_Register`, `PartnerLoginValidation`
- b) Register my business (again if it was Rejected) and always see where it stands: Pending, Active, Suspended with its reason, or Rejected. Update my hours and website, add a phone number. Uses: `Register_Business`, `Update_Business_Info`, `h_MyBusiness`, `h_BusinessPhones`
- c) Manage my products: add or edit a product, deactivate or reactivate it, set or remove its discount. Uses: `Upsert_Product`, `Toggle_Product_Status`, `Set_Product_Promotion`
- d) My business performance: which products bring my revenue in a period, and what do customers think of me? Uses: `BusinessSalesReport`, `BusinessFeedbackOverview`

### Adam Haitham Alreedy — Rider component (3.4e–g)

- e) Register as a rider, log in, switch my availability. Uses: `Rider_Register`, `RiderLoginValidation`, `Set_Rider_Availability`
- f) My active deliveries: each delivery shows where it is in its journey, and I mark it as Picked Up or Delivered from there. Uses: `My_Active_Deliveries`, `Mark_Picked_Up`, `Mark_Delivered`
- g) My performance: how much did I earn in a period, how fast am I, and how do customers rate me? Uses: `My_Earnings`, `My_Rating_Summary`, `My_Delivery_History`

### Eyad Zein Elabdein — Customer component (3.5 + 3.6)

**3.5 Account, cart and checkout:**
- a) Register as a customer and log in. Home page shows my name, my active address and my wallet balance. Uses: `Customer_Register`, `CustomerLoginValidation`
- b) Manage my addresses: add, edit or delete an address, choose my active address. Uses: `Add_Customer_Address`, `Update_Delete_Customer_Address`, `Change_Active_Address`
- c) Save a card. Only the last 4 digits of a card number are ever shown. Uses: `Add_Card`
- d) Create a cart for my active address, add products with a quantity and an optional note, remove products. Uses: `Create_Cart`, `Add_To_Cart`, `Remove_From_Cart`
- e) Check out my cart with a payment method and an optional voucher. Before I confirm, I see how my total is built from each business, the delivery fees and the voucher discount. Uses: `Calculate_Voucher_Discount`, `Checkout_Cart`, `h_CartItems`, `h_MyCards`, `h_MyVouchers`

**3.6 Browsing, orders and feedback:**
- a) Search for businesses by name or browse them by product category. Open a business page with its details, whether it is open now, its rating and its available products. Uses: `Search_Platform`, `Nearby_Businesses_By_Category`, `BusinessRatingsSummary`
- b) Add a business or product to my favorites or remove it, view my favorite products and the products recommended for me. Uses: `Toggle_Favorite`, `My_Favorites`, `Recommended_Products`
- c) My orders: where is my order now, and when will it arrive? Each part of an order shows its progress, and orders on the way show an estimated arrival predicted from the data the database already has (the business's expected delivery time and the zone's real delivery times). Uses: `My_Order_History`, `ZoneDeliveryPerformance`, `h_OrderSubOrders`
- d) Cancel an order (showing the amount that will be refunded) and reorder a past order to one of my addresses. Uses: `Cancel_Order`, `Reorder`
- e) Leave feedback for a delivered part of an order and rate its rider. Uses: `Submit_Feedback`, `Rate_Rider`

## Rules for everyone

1. Every action calls the matching Milestone 2 procedure, function or view (named under "Uses" above). Do not rewrite the business logic in the website code.
2. Show whether every action was successful or not. Use the return code to pick the message. Never show a raw SQL error or a bare error code.
3. Users only see and change their own records. Never ask a user to type their own ID.
4. When a value must be an existing record (zone, business, product, address, card, voucher), the user picks it from a list that shows names, not only IDs.
5. Check inputs before calling the database: required fields, numbers, dates, 11-digit phone, 16-digit card. Hide passwords.
6. Confirm before anything that cannot be undone (blacklisting, suspending, cancelling an order, deleting an address) and say what will happen.
7. Navigate with links, buttons and menus, not by changing the URL.
8. If a page needs data the given helpers do not provide, add your own helper and put it in `sql/Team_117.sql`. It must run without errors after the given database script and `seed_data.sql`.

## Folder structure

- `backend/` — FastAPI app (Mohamed)
- `frontend/` — Next.js app (everyone builds their pages here, inside the shared layout)
- `sql/` — `Team_117.sql`, our own helper views and functions, only if we add any
