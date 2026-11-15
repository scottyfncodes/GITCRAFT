"""The words API Discovery understands beyond the catalogue's own: synonyms, use cases, and the filter words in a
described need. Plain data (the /apis/ page ships the same tables), so search behaves the same in Python and the browser."""

STOP = set("a an the and or for of to in on with my our your i we need want find get me some any that this is are be can could would should "
           "api apis app application service data use using build building make project feature please looking help something good best "
           "which what how do does it its from by as at into about live realtime real time new simple easy".split())

# a word in the need → the words catalogue entries use for the same thing
SYNONYMS = {
    "weather": ["weather", "forecast", "meteorological", "climate", "temperature", "precipitation"],
    "forecast": ["forecast", "weather"],
    "elevation": ["elevation", "altitude", "terrain", "topographic"],
    "trail": ["trail", "trails", "hiking", "park", "parks", "outdoor", "route"],
    "map": ["map", "maps", "mapping", "tiles", "geocoding", "cartography"],
    "maps": ["map", "maps", "mapping", "tiles", "geocoding"],
    "location": ["location", "geocoding", "geolocation", "address", "places", "coordinates"],
    "geographic": ["geographic", "geocoding", "geolocation", "countries", "cities", "places", "map"],
    "geography": ["geographic", "geocoding", "countries", "cities", "places"],
    "baseball": ["baseball", "mlb"], "football": ["football", "nfl", "soccer"], "soccer": ["soccer", "football"],
    "basketball": ["basketball", "nba"], "hockey": ["hockey", "nhl"],
    "stats": ["stats", "statistics", "scores", "standings"], "statistics": ["statistics", "stats", "scores"],
    "schedule": ["schedule", "schedules", "fixtures", "games", "calendar"], "schedules": ["schedule", "schedules", "fixtures"],
    "flight": ["flight", "flights", "aircraft", "aviation", "airline", "airport"], "flights": ["flight", "flights", "aviation", "airline", "airport"],
    "aircraft": ["aircraft", "aviation", "flight", "adsb", "plane"], "plane": ["aircraft", "aviation", "flight"],
    "tracking": ["tracking", "track", "tracker", "positions"],
    "currency": ["currency", "exchange", "forex", "rates"], "crypto": ["cryptocurrency", "crypto", "bitcoin", "blockchain"],
    "stock": ["stock", "stocks", "market", "equities"], "stocks": ["stock", "stocks", "market"],
    "payment": ["payment", "payments", "billing"], "payments": ["payment", "payments", "billing"],
    "email": ["email", "mail", "smtp"], "sms": ["sms", "text", "messaging", "phone"],
    "auth": ["authentication", "authorization", "login", "identity"], "login": ["authentication", "login", "identity"],
    "image": ["image", "images", "photo", "photos", "picture"], "images": ["image", "images", "photo", "photos"],
    "photo": ["photo", "photos", "image", "images"], "video": ["video", "videos", "streaming"],
    "music": ["music", "songs", "lyrics", "audio"], "movie": ["movie", "movies", "film", "tv"], "movies": ["movie", "movies", "film", "tv"],
    "news": ["news", "headlines", "articles"], "recipe": ["recipe", "recipes", "food", "nutrition"], "recipes": ["recipe", "recipes", "food"],
    "translate": ["translation", "translate", "language"], "translation": ["translation", "translate", "language"],
    "dictionary": ["dictionary", "definitions", "words", "thesaurus"],
    "procedural": ["random", "generator", "generate", "fake", "names", "lorem"], "random": ["random", "generator", "fake"],
    "fake": ["fake", "mock", "placeholder", "random", "test"], "mock": ["mock", "fake", "placeholder", "test"],
    "book": ["book", "books", "library"], "books": ["book", "books", "library"],
    "job": ["job", "jobs", "careers"], "jobs": ["job", "jobs", "careers"],
    "air": ["air", "pollution", "aqi"], "space": ["space", "nasa", "astronomy", "satellite"],
    "holiday": ["holiday", "holidays", "calendar"], "holidays": ["holiday", "holidays", "calendar"],
    "ip": ["ip", "geolocation"], "url": ["url", "link", "shortener"], "qr": ["qr", "barcode"],
    "ai": ["machine", "learning", "ai", "nlp", "recognition"], "ml": ["machine", "learning", "ai"],
    "transit": ["transit", "transport", "bus", "train", "rail"], "train": ["train", "rail", "railway", "transit"],
    "health": ["health", "medical", "covid", "disease"], "pokemon": ["pokemon", "pokémon"],
    "dog": ["dog", "dogs"], "cat": ["cat", "cats"], "quote": ["quote", "quotes"], "quotes": ["quote", "quotes"],
    "joke": ["joke", "jokes"], "jokes": ["joke", "jokes"], "trivia": ["trivia", "quiz", "questions"],
}

# a kind of project in the need → the catalogue categories and extra words that usually serve it
USE_CASES = {
    "hiking": {"categories": ["Weather", "Geocoding", "Environment"], "terms": ["elevation", "trail", "weather", "map", "parks"], "label": "an outdoor / hiking app"},
    "outdoor": {"categories": ["Weather", "Geocoding", "Environment"], "terms": ["weather", "trail", "elevation"], "label": "an outdoor app"},
    "travel": {"categories": ["Transportation", "Geocoding", "Weather", "Currency Exchange"], "terms": ["flight", "places", "map"], "label": "a travel app"},
    "fantasy": {"categories": ["Sports & Fitness"], "terms": ["stats", "schedule", "scores"], "label": "a fantasy-sports app"},
    "sports": {"categories": ["Sports & Fitness"], "terms": ["stats", "schedule", "scores"], "label": "a sports app"},
    "fitness": {"categories": ["Sports & Fitness", "Health", "Food & Drink"], "terms": ["workout", "nutrition"], "label": "a fitness app"},
    "game": {"categories": ["Games & Comics", "Test Data", "Geocoding", "Entertainment"], "terms": ["random", "names", "trivia", "map"], "label": "a game"},
    "finance": {"categories": ["Finance", "Currency Exchange", "Cryptocurrency"], "terms": ["stock", "currency", "rates"], "label": "a finance app"},
    "ecommerce": {"categories": ["Shopping", "Finance", "Currency Exchange", "Data Validation"], "terms": ["payment", "products", "currency"], "label": "a shop"},
    "shop": {"categories": ["Shopping", "Finance", "Currency Exchange"], "terms": ["payment", "products"], "label": "a shop"},
    "blog": {"categories": ["News", "Photography", "Text Analysis"], "terms": ["images", "news"], "label": "a content site"},
    "dashboard": {"categories": ["Open Data", "Finance", "Weather", "Development"], "terms": ["statistics"], "label": "a dashboard"},
    "chat": {"categories": ["Social", "Machine Learning", "Text Analysis"], "terms": ["messaging", "translation"], "label": "a chat app"},
    "recipe": {"categories": ["Food & Drink"], "terms": ["recipes", "nutrition"], "label": "a food app"},
    "education": {"categories": ["Books", "Dictionaries", "Science & Math", "Open Data"], "terms": ["dictionary", "trivia"], "label": "a learning app"},
}

# words in the need that state a constraint rather than a topic
PREFER = {
    "no_auth": ["free", "keyless", "nokey", "anonymous", "noauth"],
    "browser": ["browser", "frontend", "clientside", "cors", "spa"],
    "https": ["https", "secure", "ssl", "tls"],
    "mobile": ["mobile", "ios", "android", "flutter", "expo"],
}
PHRASES = {"no key": "no_auth", "no api key": "no_auth", "without a key": "no_auth", "without auth": "no_auth", "no auth": "no_auth", "no signup": "no_auth",
           "no sign-up": "no_auth", "no sign up": "no_auth", "without signing up": "no_auth", "client side": "browser", "front end": "browser", "in the browser": "browser"}


def export():
    return {"stop": sorted(STOP), "synonyms": SYNONYMS, "use_cases": USE_CASES, "prefer": PREFER, "phrases": PHRASES}
