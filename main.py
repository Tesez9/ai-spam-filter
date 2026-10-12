import sqlite3
import re
from datetime import datetime
from collections import Counter

spam_rules = {
    "congratulations": 3,
    "winner": 4,
    "prize": 4,
    "reward": 3,
    "bonus": 2,
    "free": 2,
    "claim": 2,
    "urgent": 3,
    "verify": 2,
    "verification": 2,
    "guaranteed": 3,
    "zero risk": 4,
    "no credit check": 4,
    "act now": 3,
    "limited-time": 2,
    "personal details": 3,
    "bank details": 4,
    "click": 2,
    "apply now": 2
}

safe_rules = {
    "meeting": -2,
    "project": -2,
    "university": -3,
    "assignment": -2,
    "library": -3,
    "appointment": -3,
    "lecture": -2,
    "support ticket": -2,
    "vacation": -2,
    "presentation": -2,
    "customer account": -1
}

db = sqlite3.connect("spam_filter.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS emails(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    text TEXT,
    date TEXT,
    ai_classification TEXT,
    user_classification TEXT,
    confidence REAL,
    reasons TEXT,
    created_at TEXT
)
""")

db.commit()

def classify_email(sender, text):
    content = (sender + " " + text).lower()
    score = 0
    reasons = []
    for word, weight in spam_rules.items():
        if word in content:
            score += weight
            reasons.append(f'підозріла ознака: "{word}"')
    for word, weight in safe_rules.items():
        if word in content:
            score += weight
    if "http://" in content or "https://" in content:
        score += 2
        reasons.append("повідомлення містить посилання")
    if re.search(r"\$\d+", content):
        score += 2
        reasons.append("повідомлення містить грошову суму")
    suspicious_domains = [
        "lucky-mail",
        "bonus-center",
        "free-gifts",
        "fast-credit",
        "profit-zone",
        "refund-office",
        "verify-alert",
        "billing-alert"
    ]
    if any(domain in sender.lower() for domain in suspicious_domains):
        score += 3
        reasons.append("підозрілий домен відправника")
    if score >= 6:
        classification = "spam"
    else:
        classification = "not_spam"
    confidence = min(0.55 + abs(score) * 0.04, 0.99)
    if not reasons:
        reasons.append("підозрілих ознак майже не знайдено")
    return classification, confidence, reasons

def save_email(sender, text, date, result):
    classification, confidence, reasons = result
    cur.execute("""
        INSERT INTO emails(
            sender,
            text,
            date,
            ai_classification,
            confidence,
            reasons,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        sender,
        text,
        date,
        classification,
        confidence,
        "; ".join(reasons),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    db.commit()
    return cur.lastrowid

def show_result(result):
    classification, confidence, reasons = result
    print("\n================================")
    print("           AI RESULT")
    print("================================")
    print("Classification:", classification.upper())
    print("Confidence:", f"{confidence * 100:.1f}%")
    print("\nПричини:")
    for reason in reasons:
        print("-", reason)

def feedback(email_id, predicted):
    answer = input("\nПравильна класифікація? (1 - Так, 2 - Ні): ")
    if answer == "1":
        user_classification = predicted
    elif answer == "2":
        print("1. SPAM")
        print("2. NOT SPAM")
        correct = input("> ")
        if correct == "1":
            user_classification = "spam"
        else:
            user_classification = "not_spam"
    else:
        print("Feedback пропущено.")
        return
    cur.execute("""
        UPDATE emails
        SET user_classification=?
        WHERE id=?
    """, (user_classification, email_id))
    db.commit()
    print("Feedback збережено.")

def check_email():
    sender = input("From: ")
    text = input("Text: ")
    result = classify_email(sender, text)
    show_result(result)
    email_id = save_email(
        sender,
        text,
        datetime.now().strftime("%Y-%m-%d"),
        result
    )
    print("\nID:", email_id)
    feedback(email_id, result[0])

def read_file():
    emails = []
    with open("email.txt", "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            match = re.match(
                r"from:\s*(.*?):\s*text:\s*(.*):\s*date:\s*(\d{4}-\d{2}-\d{2})$",
                line
            )
            if match:
                sender = match.group(1)
                text = match.group(2)
                date = match.group(3)
                emails.append((sender, text, date))
    return emails

def analyze_file():
    emails = read_file()
    spam = 0
    not_spam = 0
    confidence_sum = 0
    for sender, text, date in emails:
        result = classify_email(sender, text)
        save_email(sender, text, date, result)
        if result[0] == "spam":
            spam += 1
        else:
            not_spam += 1
        confidence_sum += result[1]
    total = len(emails)
    print("\n================================")
    print("        ANALYSIS REPORT")
    print("================================")
    print("Processed:", total)
    print("Spam:", spam)
    print("Not spam:", not_spam)
    if total:
        print(
            "Average confidence:",
            f"{confidence_sum / total * 100:.1f}%"
        )

def history():
    rows = cur.execute("""
        SELECT id, sender, ai_classification, confidence
        FROM emails
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()
    if len(rows) == 0:
        print("Історія пуста, спочатку пункт 1 або 2")
        return
    print("\n===== HISTORY =====")
    for row in rows:
        print(
            f"ID: {row[0]} | "
            f"From: {row[1]} | "
            f"{row[2].upper()} | "
            f"{row[3] * 100:.1f}%"
        )
    email_id = input(
        "\nВведіть ID для перегляду або Enter для виходу: "
    )
    if not email_id:
        return
    row = cur.execute("""
        SELECT *
        FROM emails
        WHERE id=?
    """, (email_id,)).fetchone()
    if row:
        print("\nFrom:", row[1])
        print("Text:", row[2])
        print("Date:", row[3])
        print("AI:", row[4])
        print("User:", row[5])
        print("Confidence:", f"{row[6] * 100:.1f}%")
        print("Reasons:", row[7])

def statistics():
    total = cur.execute(
        "SELECT COUNT(*) FROM emails"
    ).fetchone()[0]
    if total == 0:
        print("База пуста")
        return
    spam = cur.execute("""
        SELECT COUNT(*)
        FROM emails
        WHERE ai_classification='spam'
    """).fetchone()[0]
    reviewed = cur.execute("""
        SELECT COUNT(*)
        FROM emails
        WHERE user_classification IS NOT NULL
    """).fetchone()[0]
    correct = cur.execute("""
        SELECT COUNT(*)
        FROM emails
        WHERE user_classification IS NOT NULL
        AND ai_classification=user_classification
    """).fetchone()[0]
    incorrect = reviewed - correct
    print("\n================================")
    print("          STATISTICS")
    print("================================")
    print("Total:", total)
    print("Spam:", spam)
    print("Not spam:", total - spam)
    print("Перевірено користувачем:", reviewed)
    if reviewed:
        print("Correct:", correct)
        print("Incorrect:", incorrect)
        print("Accuracy:", f"{correct / reviewed * 100:.1f}%")
    false_spam = cur.execute("""
        SELECT COUNT(*)
        FROM emails
        WHERE ai_classification='spam'
        AND user_classification='not_spam'
    """).fetchone()[0]
    missed_spam = cur.execute("""
        SELECT COUNT(*)
        FROM emails
        WHERE ai_classification='not_spam'
        AND user_classification='spam'
    """).fetchone()[0]
    print("\nAI -> SPAM / User -> NOT SPAM:", false_spam)
    print("AI -> NOT SPAM / User -> SPAM:", missed_spam)

def analyze_errors():
    rows = cur.execute("""
        SELECT text, reasons
        FROM emails
        WHERE user_classification IS NOT NULL
        AND ai_classification != user_classification
    """).fetchall()
    if not rows:
        print("Помилок поки немає або немає feedback.")
        return
    errors = Counter()
    for text, reasons in rows:
        text = text.lower()
        for word in list(spam_rules) + list(safe_rules):
            if word in text:
                errors[word] += 1
    print("\n===== АНАЛІЗ ПОМИЛОК =====")
    print("Кількість помилок:", len(rows))
    print("\nОзнаки, які найчастіше зустрічаються в помилках:")
    for word, count in errors.most_common(10):
        print(word, "-", count)
    if errors:
        word, count = errors.most_common(1)[0]
        print("\nРекомендація:")
        print(
            f'Перевірити вагу ознаки "{word}", '
            f"оскільки вона зустрілась у {count} помилках."
        )

while True:
    print("""
================================
        AI SPAM FILTER
================================

1. Перевірити email
2. Проаналізувати файл
3. Переглянути історію
4. Статистика
5. Перевірити помилки AI
0. Вихід
""")
    choice = input("> ")
    if choice == "1":
        check_email()
    elif choice == "2":
        analyze_file()
    elif choice == "3":
        history()
    elif choice == "4":
        statistics()
    elif choice == "5":
        analyze_errors()
    elif choice == "0":
        break
    else:
        print("Невірний пункт.")

db.close()
