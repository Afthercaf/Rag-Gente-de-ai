import sqlite3
import requests
import time

# ==========================================
# CONFIG
# ==========================================
DB_PATH = "tcg_cards2.db"

POKEMON_PAGE_SIZE = 100
REQUEST_TIMEOUT = 30
RETRY_WAIT = 15

# ==========================================
# USD -> MXN
# ==========================================
def get_usd_to_mxn() -> float:

    FALLBACK_RATE = 17.50

    try:
        url = "https://open.er-api.com/v6/latest/USD"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        rate = data["rates"]["MXN"]

        print(f"✅ Tipo de cambio: 1 USD = {rate:.4f} MXN\n")

        return float(rate)

    except Exception as e:

        print(f"⚠️ Error tipo de cambio: {e}")
        print(f"Usando fallback: {FALLBACK_RATE}\n")

        return FALLBACK_RATE


USD_TO_MXN = get_usd_to_mxn()

# ==========================================
# SQLITE
# ==========================================
conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

# ==========================================
# TABLA
# ==========================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS cards (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    game TEXT NOT NULL,

    name TEXT NOT NULL,

    set_code TEXT,

    set_name TEXT,

    rarity TEXT,

    card_type TEXT,

    subtype TEXT,

    atk TEXT,

    defense TEXT,

    attribute TEXT,

    hp TEXT,

    price_usd REAL DEFAULT 0.0,

    price_mxn REAL DEFAULT 0.0,

    description TEXT
)
""")

# ==========================================
# INDICES
# ==========================================
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_name
ON cards(name)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_set_code
ON cards(game, set_code)
""")

conn.commit()

print("✅ Tabla creada/verificada\n")

# ==========================================
# INSERT
# ==========================================
def insert_card(
    game,
    name,
    set_code,
    set_name,
    rarity,
    card_type,
    subtype,
    atk,
    defense,
    attribute,
    hp,
    price_usd,
    description
):

    if set_code:

        cursor.execute(
            """
            SELECT id
            FROM cards
            WHERE game=? AND set_code=?
            """,
            (game, set_code)
        )

    else:

        cursor.execute(
            """
            SELECT id
            FROM cards
            WHERE game=?
            AND name=?
            AND set_name=?
            AND rarity=?
            """,
            (
                game,
                name,
                set_name,
                rarity
            )
        )

    if cursor.fetchone():
        return

    price_mxn = round(price_usd * USD_TO_MXN, 2)

    cursor.execute(
        """
        INSERT INTO cards (

            game,
            name,
            set_code,
            set_name,
            rarity,

            card_type,
            subtype,

            atk,
            defense,
            attribute,
            hp,

            price_usd,
            price_mxn,

            description

        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            game,
            name,
            set_code,
            set_name,
            rarity,

            card_type,
            subtype,

            atk,
            defense,
            attribute,
            hp,

            price_usd,
            price_mxn,

            description
        )
    )

    conn.commit()

# ==========================================
# YU-GI-OH
# ==========================================
def download_yugioh():

    print("=================================")
    print("DESCARGANDO YU-GI-OH")
    print("=================================\n")

    url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        cards = response.json().get("data", [])

    except Exception as e:

        print(f"❌ Error Yu-Gi-Oh: {e}")

        return

    total_cards = len(cards)

    total_prints = 0

    print(f"Cartas únicas encontradas: {total_cards}\n")

    for i, card in enumerate(cards):

        try:

            name = card.get("name", "")

            card_type = card.get("type", "")

            # ==========================================
            # RACE = Spellcaster, Dragon, Warrior, etc.
            # ==========================================
            subtype = card.get("race", "")

            atk = str(card.get("atk", ""))

            defense = str(card.get("def", ""))

            attribute = card.get("attribute", "")

            description = card.get("desc", "")

            # ==========================================
            # PRECIO BASE
            # ==========================================
            base_price = 0.0

            if card.get("card_prices"):

                try:

                    base_price = float(
                        card["card_prices"][0].get(
                            "tcgplayer_price",
                            "0"
                        ) or "0"
                    )

                except:
                    base_price = 0.0

            sets = card.get("card_sets", [])

            # ==========================================
            # UNA FILA POR PRINT
            # ==========================================
            if sets:

                for card_set in sets:

                    set_code = card_set.get(
                        "set_code",
                        ""
                    )

                    set_name = card_set.get(
                        "set_name",
                        "Unknown"
                    )

                    rarity = card_set.get(
                        "set_rarity",
                        "Unknown"
                    )

                    try:

                        set_price = float(
                            card_set.get(
                                "set_price",
                                "0"
                            ) or "0"
                        )

                    except:
                        set_price = 0.0

                    price = (
                        set_price
                        if set_price > 0
                        else base_price
                    )

                    insert_card(
                        game="Yu-Gi-Oh",

                        name=name,

                        set_code=set_code,

                        set_name=set_name,

                        rarity=rarity,

                        card_type=card_type,

                        subtype=subtype,

                        atk=atk,

                        defense=defense,

                        attribute=attribute,

                        hp="",

                        price_usd=price,

                        description=description
                    )

                    total_prints += 1

            else:

                insert_card(
                    game="Yu-Gi-Oh",

                    name=name,

                    set_code=None,

                    set_name="Unknown",

                    rarity="Unknown",

                    card_type=card_type,

                    subtype=subtype,

                    atk=atk,

                    defense=defense,

                    attribute=attribute,

                    hp="",

                    price_usd=base_price,

                    description=description
                )

                total_prints += 1

            if i % 500 == 0:

                print(
                    f"Yu-Gi-Oh: "
                    f"{i}/{total_cards} "
                    f"| prints: {total_prints}"
                )

        except Exception as e:

            print(
                f"⚠️ Error YGO "
                f"'{card.get('name', '?')}': {e}"
            )

    print(
        f"\n✅ Yu-Gi-Oh completado: "
        f"{total_prints} prints\n"
    )

# ==========================================
# POKEMON
# ==========================================
def download_pokemon():

    print("=================================")
    print("DESCARGANDO POKEMON")
    print("=================================\n")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    page = 1

    total_saved = 0

    while True:

        try:

            url = (
                f"https://api.pokemontcg.io/v2/cards"
                f"?page={page}"
                f"&pageSize={POKEMON_PAGE_SIZE}"
            )

            print(f"Página Pokémon: {page}")

            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            cards = data.get("data", [])

            if not cards:

                print("No hay más cartas.")
                break

            for card in cards:

                try:

                    card_id = card.get("id", "")

                    name = card.get("name", "")

                    rarity = card.get(
                        "rarity",
                        "Unknown"
                    )

                    set_name = card.get(
                        "set",
                        {}
                    ).get(
                        "name",
                        "Unknown"
                    )

                    full_set_code = card_id

                    # ==========================================
                    # TYPES
                    # ==========================================
                    pokemon_types = ",".join(
                        card.get("types", [])
                    )

                    supertype = card.get(
                        "supertype",
                        ""
                    )

                    hp = card.get("hp", "")

                    # ==========================================
                    # PRECIOS
                    # ==========================================
                    price = 0.0

                    prices = card.get(
                        "tcgplayer",
                        {}
                    ).get(
                        "prices",
                        {}
                    )

                    possible_keys = [

                        "normal",

                        "reverseHolofoil",

                        "holofoil",

                        "1stEditionHolofoil",

                        "1stEditionNormal",

                        "unlimitedHolofoil",

                        "unlimitedNormal"

                    ]

                    for key in possible_keys:

                        if key not in prices:
                            continue

                        data_price = prices.get(
                            key,
                            {}
                        )

                        values = [

                            data_price.get("market"),

                            data_price.get("mid"),

                            data_price.get("high")

                        ]

                        for value in values:

                            if value:

                                try:

                                    value = float(value)

                                    if value > price:
                                        price = value

                                except:
                                    pass

                    # ==========================================
                    # FALLBACK CARDMARKET
                    # ==========================================
                    if price == 0.0:

                        cm_prices = card.get(
                            "cardmarket",
                            {}
                        ).get(
                            "prices",
                            {}
                        )

                        avg = (

                            cm_prices.get(
                                "averageSellPrice"
                            )

                            or cm_prices.get(
                                "trendPrice"
                            )

                            or cm_prices.get(
                                "avg1"
                            )

                            or cm_prices.get(
                                "avg7"
                            )

                            or cm_prices.get(
                                "avg30"
                            )

                        )

                        if avg:

                            try:
                                price = float(avg)

                            except:
                                price = 0.0

                    insert_card(

                        game="Pokemon",

                        name=name,

                        set_code=full_set_code,

                        set_name=set_name,

                        rarity=rarity,

                        card_type=supertype,

                        subtype=pokemon_types,

                        atk="",

                        defense="",

                        attribute="",

                        hp=hp,

                        price_usd=price,

                        description=""

                    )

                    total_saved += 1

                except Exception as e:

                    print(f"⚠️ Error Pokémon: {e}")

            print(
                f"Total guardadas: {total_saved}"
            )

            page += 1

            time.sleep(1.5)

        except requests.exceptions.RequestException as e:

            print(f"\n❌ Error conexión Pokémon: {e}")

            print(
                f"Reintentando "
                f"en {RETRY_WAIT}s...\n"
            )

            time.sleep(RETRY_WAIT)

        except Exception as e:

            print(f"\n❌ Error general Pokémon: {e}")

            time.sleep(RETRY_WAIT)

    print(
        f"\n✅ Pokémon completado: "
        f"{total_saved} cartas\n"
    )

# ==========================================
# EJECUTAR
# ==========================================
download_yugioh()

download_pokemon()

# ==========================================
# RESUMEN
# ==========================================
cursor.execute(
    "SELECT COUNT(*) FROM cards"
)

total = cursor.fetchone()[0]

cursor.execute(
    """
    SELECT COUNT(*)
    FROM cards
    WHERE game='Yu-Gi-Oh'
    """
)

total_ygo = cursor.fetchone()[0]

cursor.execute(
    """
    SELECT COUNT(*)
    FROM cards
    WHERE game='Pokemon'
    """
)

total_pokemon = cursor.fetchone()[0]

cursor.execute(
    """
    SELECT COUNT(DISTINCT name)
    FROM cards
    WHERE game='Yu-Gi-Oh'
    """
)

unique_ygo = cursor.fetchone()[0]

cursor.execute(
    """
    SELECT COUNT(DISTINCT name)
    FROM cards
    WHERE game='Pokemon'
    """
)

unique_pokemon = cursor.fetchone()[0]

print("\n=================================")
print("RESUMEN BASE DE DATOS")
print("=================================")

print(
    f"Tipo cambio: "
    f"1 USD = {USD_TO_MXN:.4f} MXN"
)

print(
    f"Yu-Gi-Oh: "
    f"{total_ygo:,} prints "
    f"({unique_ygo:,} únicas)"
)

print(
    f"Pokémon: "
    f"{total_pokemon:,} prints "
    f"({unique_pokemon:,} únicas)"
)

print(
    f"TOTAL: {total:,} registros"
)

print("=================================\n")

conn.close()

print("✅ Base de datos creada correctamente")
print(f"Archivo: {DB_PATH}")