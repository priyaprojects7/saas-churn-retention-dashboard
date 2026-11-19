# Power BI row-level security design

1. Add a `user_customer_access` bridge with `user_principal_name` and `customer_key`.
2. Filter the bridge using `user_customer_access[user_principal_name] = USERPRINCIPALNAME()`.
3. Configure relationships so the bridge filters `dim_customer`, then the fact table.
4. Test at least two users with Power BI's **View as** feature.
5. Keep workspace and dataset build permissions separate from row-level security.
6. Validate exports, drill-through pages, and related reports preserve the same boundary.

This is a documented deployment pattern, not an active security control in this local demo.
