import requests
from bs4 import BeautifulSoup
import hashlib
import json
import os
import argparse
from datetime import datetime
import fitz  # PyMuPDF
import re
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import urllib.request
import openai

DATA_FILE = 'rbi_data.json'
NOTIFICATIONS_URL = 'https://www.rbi.org.in/Scripts/NotificationUser.aspx'
PRESS_RELEASES_URL = 'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx'
FULL_DATA_FILE = 'rbi_notifications_full.json'
DOWNLOAD_DIR = 'downloads'
PRESS_RELEASES_FULL_DATA_FILE = 'rbi_press_releases_full.json'

load_dotenv()

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)


def hash_entry(title, date, url):
    h = hashlib.sha256()
    h.update((title + date + url).encode('utf-8'))
    return h.hexdigest()


def fetch_pdf_from_detail(url):
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        pdf_links = []
        for a in soup.find_all('a', href=True):
            if a['href'].lower().endswith('.pdf'):
                pdf_url = a['href']
                if not pdf_url.startswith('http'):
                    pdf_url = 'https://www.rbi.org.in' + pdf_url
                pdf_links.append(pdf_url)
        return pdf_links
    except Exception as e:
        print(f"Error fetching PDF from {url}: {e}")
        return []


def fetch_notifications():
    print('Fetching notifications...')
    resp = requests.get(NOTIFICATIONS_URL, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', class_='tablebg')
    if not table:
        print('Could not find notifications table.')
        return []
    entries = []
    current_date = None
    for row in table.find_all('tr'):
        # Date header row
        header_td = row.find('td', class_='tableheader')
        if header_td:
            b_tag = header_td.find('b')
            if b_tag:
                current_date = b_tag.get_text(strip=True)
            continue
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        # Title and detail link in first column
        title_tag = cols[0].find('a', class_='link2')
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        detail_url = title_tag['href']
        if not detail_url.startswith('http'):
            detail_url = 'https://www.rbi.org.in/' + detail_url.lstrip('/')
        # PDF link in second column
        pdf_urls = []
        pdf_a = cols[1].find('a', href=True)
        if pdf_a and pdf_a['href'].lower().endswith('.pdf'):
            pdf_url = pdf_a['href']
            if not pdf_url.startswith('http'):
                pdf_url = 'https://www.rbi.org.in/' + pdf_url.lstrip('/')
            pdf_urls.append(pdf_url)
        entry = {
            'title': title,
            'date': current_date,
            'detail_url': detail_url,
            'pdf_urls': pdf_urls,
            'source': 'Notification',
            'hash': hash_entry(title, current_date, detail_url)
        }
        entries.append(entry)
    return entries


def fetch_press_releases():
    print('Fetching press releases...')
    resp = requests.get(PRESS_RELEASES_URL, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', class_='tablebg')
    if not table:
        print('Could not find press releases table.')
        return []
    entries = []
    current_date = None
    for row in table.find_all('tr'):
        header_td = row.find('td', class_='tableheader')
        if header_td:
            b_tag = header_td.find('b')
            if b_tag:
                current_date = b_tag.get_text(strip=True)
            continue
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        # Title and detail link in first column
        title_tag = cols[0].find('a', class_='link2')
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        detail_url = title_tag['href']
        if not detail_url.startswith('http'):
            detail_url = 'https://www.rbi.org.in/' + detail_url.lstrip('/')
        # PDF link in second column
        pdf_urls = []
        pdf_a = cols[1].find('a', href=True)
        if pdf_a and pdf_a['href'].lower().endswith('.pdf'):
            pdf_url = pdf_a['href']
            if not pdf_url.startswith('http'):
                pdf_url = 'https://www.rbi.org.in/' + pdf_url.lstrip('/')
            pdf_urls.append(pdf_url)
        entry = {
            'title': title,
            'date': current_date,
            'detail_url': detail_url,
            'pdf_urls': pdf_urls,
            'source': 'PressRelease',
            'hash': hash_entry(title, current_date, detail_url)
        }
        entries.append(entry)
    return entries


def load_existing_entries():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        try:
            data = json.load(f)
            return {entry['hash']: entry for entry in data}
        except Exception:
            return {}


def send_entry_email(entry, to_email):
    subject = f"New RBI {entry['source']}: {entry['title']}"
    body = f"Title: {entry['title']}\nDate: {entry['date']}\nLink: {entry['detail_url']}"
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg.set_content(body)
    # Attach PDF if available
    if entry.get('pdf_urls') and len(entry['pdf_urls']) > 0:
        pdf_url = entry['pdf_urls'][0]
        file_name = os.path.basename(pdf_url.split('?')[0])
        pdf_path = os.path.join(DOWNLOAD_DIR, file_name)
        if not os.path.exists(pdf_path):
            pdf_path = download_pdf(pdf_url, file_name)
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                file_data = f.read()
                msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"Email sent to {to_email} for {entry['title']}")
    except Exception as e:
        print(f"Failed to send email for {entry['title']}: {e}")


def save_new_entries(new_entries):
    existing = load_existing_entries()
    added = 0
    for entry in new_entries:
        if entry['hash'] not in existing:
            existing[entry['hash']] = entry
            print(f"[NEW] {entry['source']} | {entry['date']} | {entry['title']}")
            send_entry_email(entry, EMAIL_TO)
            added += 1
    with open(DATA_FILE, 'w') as f:
        json.dump(list(existing.values()), f, indent=2)
    print(f"Added {added} new entries.")


def download_pdf(pdf_url, file_name):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if os.path.exists(file_path):
        return file_path
    try:
        resp = requests.get(pdf_url, timeout=20)
        if resp.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(resp.content)
            return file_path
        else:
            print(f"Failed to download {pdf_url}: {resp.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading {pdf_url}: {e}")
        return None


def extract_text_and_links(pdf_path):
    text = ''
    links = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += page.get_text()
            for link in page.get_links():
                if link.get("uri"):
                    rect = fitz.Rect(link["from"])
                    words = page.get_text("words")
                    context = ""
                    for w in words:
                        word_rect = fitz.Rect(w[:4])
                        if rect.intersects(word_rect):
                            context += w[4] + " "
                    links.append({
                        "url": link["uri"],
                        "context": context.strip(),
                        "page": page_num + 1
                    })
    except Exception as e:
        print(f"Error extracting from {pdf_path}: {e}")
    return text, links


def extract_dates(text):
    # Simple regex for dates like 'January 1, 2020', '1 Jan 2020', '01/01/2020', etc.
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) ?\d{1,2},? ?\d{4}\b',
        r'\b\d{1,2} (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) ?\d{4}\b',
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b'
    ]
    found = set()
    for pat in date_patterns:
        for m in re.findall(pat, text):
            found.add(m)
    return list(found)


def extract_dates_with_context(text, window=40):
    # Same date patterns as before
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) ?\d{1,2},? ?\d{4}\b',
        r'\b\d{1,2} (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) ?\d{4}\b',
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b'
    ]
    results = []
    for pat in date_patterns:
        for m in re.finditer(pat, text):
            date = m.group(0)
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            context = text[start:end].replace('\n', ' ').strip()
            results.append({"date": date, "context": context})
    return results


def process_notifications_full():
    notifications = fetch_notifications()
    results = []
    for entry in notifications:
        if not entry['pdf_urls']:
            continue
        for pdf_url in entry['pdf_urls']:
            file_name = os.path.basename(pdf_url.split('?')[0])
            pdf_path = download_pdf(pdf_url, file_name)
            if not pdf_path:
                continue
            text, links = extract_text_and_links(pdf_path)
            dates_with_context = extract_dates_with_context(text)
            results.append({
                "title": entry['title'],
                "file_pdf_link": pdf_url,
                "file_extracted_text": text,
                "extracted_links": [{"url": l["url"], "context": l["context"]} for l in links],
                "important_dates": dates_with_context
            })
            print(f"Processed {entry['title']}")
    with open(FULL_DATA_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} notification PDFs to {FULL_DATA_FILE}")


def process_press_releases_full():
    press_releases = fetch_press_releases()
    results = []
    for entry in press_releases:
        if not entry['pdf_urls']:
            continue
        for pdf_url in entry['pdf_urls']:
            file_name = os.path.basename(pdf_url.split('?')[0])
            pdf_path = download_pdf(pdf_url, file_name)
            if not pdf_path:
                continue
            text, links = extract_text_and_links(pdf_path)
            dates_with_context = extract_dates_with_context(text)
            results.append({
                "title": entry['title'],
                "file_pdf_link": pdf_url,
                "file_extracted_text": text,
                "extracted_links": [{"url": l["url"], "context": l["context"]} for l in links],
                "important_dates": dates_with_context
            })
            print(f"Processed {entry['title']}")
    with open(PRESS_RELEASES_FULL_DATA_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} press release PDFs to {PRESS_RELEASES_FULL_DATA_FILE}")


def process_all_full():
    print("\n--- Scraping Notifications (full) ---")
    process_notifications_full()
    print("\n--- Scraping Press Releases (full) ---")
    process_press_releases_full()
    print("\nAll full scraping complete. See rbi_notifications_full.json and rbi_press_releases_full.json.")


def main():
    notifications = fetch_notifications()
    press_releases = fetch_press_releases()
    all_entries = notifications + press_releases
    save_new_entries(all_entries)


def generate_pdf_from_notification(item, pdf_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=16)
    pdf.multi_cell(0, 10, item['title'])
    if 'date' in item and item['date']:
        pdf.set_font("helvetica", size=12)
        pdf.cell(0, 10, f"Date: {item['date']}", ln=True)
    pdf.ln(5)
    pdf.set_font("helvetica", size=11)
    text = item['file_extracted_text']
    for line in text.splitlines():
        pdf.multi_cell(0, 8, line)
    pdf.output(pdf_path)

def send_email_with_attachment(subject, body, to_email, attachment_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg.set_content(body)
    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)
    msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)


def email_first_notification_pdf():
    # Load the first item from rbi_notifications_full.json
    with open(FULL_DATA_FILE, 'r') as f:
        data = json.load(f)
    if not data:
        print('No notifications found in rbi_notifications_full.json')
        return
    item = data[0]
    pdf_path = 'first_notification.pdf'
    generate_pdf_from_notification(item, pdf_path)
    subject = f"RBI Notification: {item['title']}"
    body = f"Please find attached the PDF generated from the first notification.\n\nTitle: {item['title']}"
    send_email_with_attachment(subject, body, 'tusharbijalwan12@gmail.com', pdf_path)
    print(f"Email sent to tusharbijalwan12@gmail.com with {pdf_path}")
    os.remove(pdf_path)
    print(f"Temporary PDF {pdf_path} deleted.")


def summarize_first_press_release():
    # Load OpenAI API key from .env or use a hardcoded key (not recommended)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print('No OpenAI API key found in environment variable OPENAI_API_KEY.')
        return
    with open(PRESS_RELEASES_FULL_DATA_FILE, 'r') as f:
        data = json.load(f)
    if not data:
        print('No press releases found in rbi_press_releases_full.json')
        return
    item = data[0]
    text = item['file_extracted_text'][:12000]  # Truncate to fit GPT-4 context if needed
    prompt = f"Summarize the following RBI press release in a concise, clear report for a business audience.\n\n{text}"
    print('Sending content to OpenAI for summary...')
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content
    print("\n--- Press Release Summary ---\n")
    print(summary)
    print("\n--- End of Summary ---\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape RBI Notifications and Press Releases')
    parser.add_argument('--scrape', action='store_true', help='Trigger scraping now')
    parser.add_argument('--scrape-notifications-full', action='store_true', help='Scrape notifications and extract PDF content/links/dates')
    parser.add_argument('--scrape-press-releases-full', action='store_true', help='Scrape press releases and extract PDF content/links/dates')
    parser.add_argument('--scrape-all-full', action='store_true', help='Scrape both notifications and press releases (full)')
    parser.add_argument('--email-first-notification-pdf', action='store_true', help='Email the first notification as a generated PDF')
    parser.add_argument('--summarize-first-press-release', action='store_true', help='Summarize the first press release using OpenAI GPT')
    args = parser.parse_args()
    if args.scrape:
        main()
    elif args.scrape_notifications_full:
        process_notifications_full()
    elif args.scrape_press_releases_full:
        process_press_releases_full()
    elif args.scrape_all_full:
        process_all_full()
    elif args.email_first_notification_pdf:
        email_first_notification_pdf()
    elif args.summarize_first_press_release:
        summarize_first_press_release()
    else:
        print('Use --scrape to trigger scraping or --scrape-notifications-full or --scrape-press-releases-full or --scrape-all-full or --email-first-notification-pdf or --summarize-first-press-release for full extraction, email, or summary automation.') 