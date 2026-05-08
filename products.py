PRODUCTS = [
    {"id": 1,  "name": "Classic Leather Jacket",      "category": "clothing",    "tags": ["leather", "outerwear", "edgy", "fashion", "jacket"],  "price": 189.99, "image": "🧥"},
    {"id": 2,  "name": "Organic Cotton T-Shirt",      "category": "clothing",    "tags": ["organic", "casual", "sustainable", "basics"],     "price": 29.99,  "image": "👕"},
    {"id": 3,  "name": "Running Shoes Pro",            "category": "footwear",    "tags": ["running", "athletic", "fitness", "sport", "shoe"],  "price": 129.99, "image": "👟"},
    {"id": 4,  "name": "Wireless Noise-Cancel Headphones", "category": "electronics", "tags": ["audio", "music", "tech", "wireless"],        "price": 249.99, "image": "🎧"},
    {"id": 5,  "name": "Espresso Machine Deluxe",      "category": "kitchen",     "tags": ["coffee", "espresso", "kitchen", "morning"],      "price": 349.99, "image": "☕"},
    {"id": 6,  "name": "Yoga Mat Premium",             "category": "fitness",     "tags": ["yoga", "fitness", "wellness", "exercise"],        "price": 59.99,  "image": "🧘"},
    {"id": 7,  "name": "Vintage Vinyl Record Player",  "category": "electronics", "tags": ["music", "retro", "vinyl", "audio"],              "price": 199.99, "image": "🎵"},
    {"id": 8,  "name": "Stainless Steel Water Bottle",  "category": "accessories", "tags": ["eco", "sustainable", "hydration", "fitness"],    "price": 24.99,  "image": "💧"},
    {"id": 9,  "name": "Bestseller Mystery Novel",     "category": "books",       "tags": ["reading", "mystery", "thriller", "fiction"],      "price": 14.99,  "image": "📚"},
    {"id": 10, "name": "Smart Watch Fitness Tracker",   "category": "electronics", "tags": ["fitness", "tech", "health", "wearable"],         "price": 199.99, "image": "⌚"},
    {"id": 11, "name": "Cast Iron Skillet",             "category": "kitchen",     "tags": ["cooking", "kitchen", "durable", "classic"],       "price": 44.99,  "image": "🍳"},
    {"id": 12, "name": "Scented Candle Set",            "category": "home",        "tags": ["relaxation", "home", "aromatherapy", "gift"],     "price": 34.99,  "image": "🕯️"},
    {"id": 13, "name": "Trail Hiking Boots",            "category": "footwear",    "tags": ["hiking", "outdoor", "adventure", "nature", "boot"], "price": 159.99, "image": "🥾"},
    {"id": 14, "name": "Plant-Based Protein Powder",    "category": "health",      "tags": ["fitness", "nutrition", "vegan", "health"],        "price": 39.99,  "image": "💪"},
    {"id": 15, "name": "Wireless Charging Pad",         "category": "electronics", "tags": ["tech", "charging", "wireless", "gadget"],        "price": 29.99,  "image": "🔋"},
    {"id": 16, "name": "Silk Pillowcase Set",           "category": "home",        "tags": ["luxury", "sleep", "skincare", "home"],            "price": 49.99,  "image": "🛏️"},
    {"id": 17, "name": "Gardening Tool Kit",            "category": "outdoor",     "tags": ["gardening", "outdoor", "nature", "hobby"],        "price": 54.99,  "image": "🌱"},
    {"id": 18, "name": "Artisan Chocolate Box",         "category": "food",        "tags": ["chocolate", "gift", "gourmet", "treat"],          "price": 27.99,  "image": "🍫"},
]

# Keyword synonyms that map user language to product tags/categories/names
KEYWORD_MAP = {
    "jacket": ["jacket", "outerwear", "leather", "clothing"],
    "jackets": ["jacket", "outerwear", "leather", "clothing"],
    "leather": ["leather", "jacket", "edgy"],
    "shoe": ["shoe", "footwear", "running", "boot"],
    "shoes": ["shoe", "footwear", "running", "boot"],
    "boots": ["boot", "hiking", "footwear"],
    "music": ["music", "audio", "vinyl", "retro"],
    "coffee": ["coffee", "espresso", "morning", "kitchen"],
    "fitness": ["fitness", "athletic", "sport", "exercise", "yoga", "health"],
    "yoga": ["yoga", "fitness", "wellness"],
    "running": ["running", "athletic", "fitness", "sport", "shoe"],
    "cooking": ["cooking", "kitchen", "durable"],
    "tech": ["tech", "electronics", "wireless", "gadget", "wearable"],
    "reading": ["reading", "mystery", "fiction", "thriller"],
    "books": ["reading", "mystery", "fiction"],
    "outdoor": ["outdoor", "hiking", "nature", "adventure", "gardening"],
    "fashion": ["fashion", "edgy", "clothing", "leather", "luxury"],
    "clothes": ["clothing", "fashion", "casual", "basics"],
    "clothing": ["clothing", "fashion", "casual", "basics"],
    "eco": ["eco", "sustainable", "organic", "vegan"],
    "sustainable": ["sustainable", "eco", "organic", "vegan"],
    "relax": ["relaxation", "aromatherapy", "sleep", "home"],
    "home": ["home", "relaxation", "sleep", "gift"],
    "chocolate": ["chocolate", "gourmet", "treat", "gift"],
    "gift": ["gift", "chocolate", "treat", "aromatherapy"],
}

# Negative signal phrases — patterns like "not X", "don't like X", "hate X"
NEGATIVE_PATTERNS = [
    "not ", "don't like", "dont like", "no ", "hate ", "dislike ",
    "not into ", "don't want", "dont want", "not a fan of",
]


def get_all_products() -> list[dict]:
    return PRODUCTS


def get_product_catalog_text() -> str:
    lines = []
    for p in PRODUCTS:
        lines.append(f"- ID:{p['id']} {p['name']} (${p['price']}) [{', '.join(p['tags'])}] category:{p['category']}")
    return "\n".join(lines)


def score_products(history: list[dict]) -> list[dict]:
    """Score and rank products based on chat history likes/dislikes."""
    likes: set[str] = set()
    dislikes: set[str] = set()

    # Extract user messages only
    user_messages = [m["content"].lower() for m in history if m["role"] == "user"]

    for text in user_messages:
        words = set(text.split())
        for keyword, expansions in KEYWORD_MAP.items():
            if keyword in words or keyword in text:
                # Check if this keyword appears in a negative context
                is_negative = False
                for neg in NEGATIVE_PATTERNS:
                    idx = text.find(neg)
                    if idx != -1:
                        # Check if the keyword follows the negative phrase
                        after = text[idx + len(neg):]
                        if keyword in after.split()[:5]:  # within next 5 words
                            is_negative = True
                            break

                if is_negative:
                    dislikes.update(expansions)
                else:
                    likes.update(expansions)

    # Remove anything that's in both (dislike wins)
    likes -= dislikes

    # Score each product
    scored = []
    for product in PRODUCTS:
        searchable = set(product["tags"] + [product["category"]] + product["name"].lower().split())

        # Skip products that match dislikes
        dislike_hits = len(searchable & dislikes)
        if dislike_hits > 0:
            continue

        # Score by number of matching liked terms
        like_hits = len(searchable & likes)
        if like_hits > 0:
            scored.append((like_hits, product))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        return [p for _, p in scored[:6]]

    # Fallback: return popular items excluding disliked ones
    fallback = []
    for product in PRODUCTS:
        searchable = set(product["tags"] + [product["category"]] + product["name"].lower().split())
        if not (searchable & dislikes):
            fallback.append(product)
        if len(fallback) >= 6:
            break
    return fallback
