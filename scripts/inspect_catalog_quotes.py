import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.catalog.generator import generate_catalog

quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
allowed = [q for q in quotes if q.get("isAllowedVendor", True)]
for cat in ["API_CALLS", "AI_CREDITS", "STORAGE"]:
    cat_quotes = [q for q in allowed if q.get("categoryName") == cat]
    print(f"=== {cat} (count={len(cat_quotes)}) ===")
    for q in sorted(cat_quotes, key=lambda x: (x["units"], x["price"])):
        print(f"  quoteId={q['quoteId'][:14]}.. sku={q['skuId'][:14]}.. vendor={q['vendorId'][:10]}.. units={q['units']} price={q['price']} (${q['price']/1e6:.2f})")

