import os
import random
from datetime import datetime, timedelta

import psycopg2
import pymysql
import pymongo
from faker import Faker

fake = Faker("es")

BATCH = 500
USERS_COUNT = 20_000
BOOKS_COUNT = 20_000
TRANSACTIONS_COUNT = 8_000
SOLICITUDES_COUNT = 20_000
REVIEWS_COUNT = 8_000

FAKE_PASSWORD_HASH = "$2b$12$abcdefghijklmnopqrstuvuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu"


def pg_connect():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=5432,
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname="ms1_users",
    )


def mysql_connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=3306,
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database="ms2_books",
        autocommit=False,
    )


def mongo_client():
    return pymongo.MongoClient(os.environ["MONGO_URL"])


def batches(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def rand_date(days_back=730):
    return datetime.utcnow() - timedelta(days=random.randint(0, days_back))


def seed_users(conn):
    print("Insertando users...")
    cur = conn.cursor()
    total = 0
    for batch in batches(range(USERS_COUNT), BATCH):
        rows = []
        for _ in batch:
            zone_id = None if random.random() < 0.15 else random.randint(1, 27)
            rows.append((
                fake.name(),
                fake.unique.email(),
                FAKE_PASSWORD_HASH,
                zone_id,
                None,
                rand_date(),
            ))
        cur.executemany(
            """
            INSERT INTO users (name, email, password_hash, zone_id, photo_url, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            rows,
        )
        conn.commit()
        total += len(rows)
    cur.close()
    return total


def seed_books(conn):
    print("Insertando books...")
    cur = conn.cursor()
    publisher_pool = random.sample(range(1, USERS_COUNT + 1), int(USERS_COUNT * 0.30))
    total = 0
    for batch in batches(range(BOOKS_COUNT), BATCH):
        rows = []
        for _ in batch:
            user_id = random.choice(publisher_pool)
            price = round(random.uniform(10, 150), 2) if random.random() < 0.60 else None
            rows.append((
                user_id,
                fake.sentence(nb_words=4).rstrip("."),
                fake.name(),
                random.randint(1, 10),
                fake.paragraph(nb_sentences=3),
                None,
                price,
                True,
                True,
                rand_date(),
            ))
        cur.executemany(
            """
            INSERT IGNORE INTO books
              (user_id, title, author, category_id, description, photo_url,
               price, available, active, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            rows,
        )
        conn.commit()
        total += cur.rowcount
    cur.close()
    return total


def seed_transactions(conn):
    print("Insertando transactions...")
    cur = conn.cursor()

    cur.execute("SELECT id, user_id FROM books LIMIT %s", (BOOKS_COUNT,))
    book_map = {r[0]: r[1] for r in cur.fetchall()}
    book_ids = list(book_map.keys())

    chosen_books = random.sample(book_ids, min(TRANSACTIONS_COUNT, len(book_ids)))
    sold_book_ids = set()
    total = 0

    for batch in batches(chosen_books, BATCH):
        rows = []
        for book_id in batch:
            seller_id = book_map[book_id]
            buyer_id = random.randint(1, USERS_COUNT)
            while buyer_id == seller_id:
                buyer_id = random.randint(1, USERS_COUNT)
            rows.append((book_id, buyer_id, seller_id, rand_date()))
            sold_book_ids.add(book_id)
        cur.executemany(
            """
            INSERT IGNORE INTO transactions (book_id, buyer_id, seller_id, created_at)
            VALUES (%s,%s,%s,%s)
            """,
            rows,
        )
        conn.commit()
        total += cur.rowcount

    print("Marcando books vendidos como available=false...")
    for batch in batches(list(sold_book_ids), BATCH):
        fmt = ",".join(["%s"] * len(batch))
        cur.execute(f"UPDATE books SET available=false WHERE id IN ({fmt})", batch)
        conn.commit()

    cur.close()
    return total


STATUS_DIST = (
    ["pendiente"] * 50
    + ["aceptada"] * 20
    + ["rechazada"] * 20
    + ["cancelada"] * 10
)


def seed_solicitudes(db):
    print("Insertando solicitudes...")
    col = db["solicitudes"]
    docs = []
    for _ in range(SOLICITUDES_COUNT):
        book_id = random.randint(1, BOOKS_COUNT)
        seller_id = random.randint(1, USERS_COUNT)
        buyer_id = random.randint(1, USERS_COUNT)
        while buyer_id == seller_id:
            buyer_id = random.randint(1, USERS_COUNT)
        msgs = []
        for i in range(random.randint(0, 5)):
            sender = buyer_id if i % 2 == 0 else seller_id
            msgs.append({"from": sender, "text": fake.sentence(), "date": rand_date(365)})
        docs.append({
            "book_id": book_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "status": random.choice(STATUS_DIST),
            "messages": msgs,
            "created_at": rand_date(),
        })

    total = 0
    for batch in batches(docs, BATCH):
        col.insert_many(batch)
        total += len(batch)
    return total


def seed_reviews(db):
    print("Insertando reviews...")
    col = db["reviews"]
    rating_pool = [1, 2, 3, 4, 4, 4, 5, 5, 5, 5]
    docs = []
    for _ in range(REVIEWS_COUNT):
        user_id = random.randint(1, USERS_COUNT)
        target_user_id = random.randint(1, USERS_COUNT)
        while target_user_id == user_id:
            target_user_id = random.randint(1, USERS_COUNT)
        docs.append({
            "user_id": user_id,
            "target_user_id": target_user_id,
            "transaction_id": str(random.randint(1, TRANSACTIONS_COUNT)),
            "rating": float(random.choice(rating_pool)),
            "comment": fake.paragraph(nb_sentences=2),
            "created_at": rand_date(),
        })

    total = 0
    for batch in batches(docs, BATCH):
        col.insert_many(batch)
        total += len(batch)
    return total


def main():
    pg = pg_connect()
    my = mysql_connect()
    mongo = mongo_client()
    db_name = os.environ["MONGO_URL"].rstrip("/").split("/")[-1]
    mdb = mongo[db_name]

    summary = {
        "users (PostgreSQL)": seed_users(pg),
        "books (MySQL)": seed_books(my),
        "transactions (MySQL)": seed_transactions(my),
        "solicitudes (MongoDB)": seed_solicitudes(mdb),
        "reviews (MongoDB)": seed_reviews(mdb),
    }

    pg.close()
    my.close()
    mongo.close()

    print("\nResumen:")
    for table, count in summary.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
