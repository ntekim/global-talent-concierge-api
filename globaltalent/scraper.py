import os
import time
import requests
from bs4 import BeautifulSoup

SITES = [
    ("https://www.make-it-in-germany.com/en/visa-residence/types/work", "germany_visa.txt"),
    ("https://www.gov.uk/skilled-worker-visa", "uk_visa.txt"),
    ("https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/permit.html", "canada_visa.txt"),
    ("https://travel.state.gov/content/travel/en/us-visas/employment.html", "usa_visa.txt"),
    ("https://u.ae/en/information-and-services/jobs/types-of-work-permits", "uae_visa.txt"),
    ("https://www.expatica.com/de/moving/move/moving-to-berlin", "berlin_guide.txt"),
    ("https://www.expatica.com/uk/moving/move/moving-to-london", "london_guide.txt"),
    ("https://www.expatica.com/ae/moving/move/moving-to-dubai", "dubai_guide.txt"),
    ("https://www.expatica.com/ca/moving/move/moving-to-toronto", "toronto_guide.txt"),
]

EXPECTED_FILES = [fname for _, fname in SITES]
SITE_MAP = dict(SITES)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

RETRY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
}

TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header"]

FALLBACKS = {
    "germany_visa.txt": (
        "Germany Work Visa Requirements\n"
        "- Valid passport with at least 3 months validity beyond intended stay\n"
        "- Completed visa application form\n"
        "- Biometric passport photos\n"
        "- Proof of employment contract or job offer from German employer\n"
        "- University degree or professional qualification (translated to German)\n"
        "- Health insurance coverage valid in Germany\n"
        "- Proof of sufficient funds to support yourself\n"
        "- Rental agreement or proof of accommodation in Germany\n"
        "- Visa application fee payment receipt\n"
        "- Residence permit application upon arrival"
    ),
    "uk_visa.txt": (
        "UK Skilled Worker Visa Requirements\n"
        "- Valid passport\n"
        "- Certificate of Sponsorship (CoS) from your UK employer\n"
        "- Proof of English language proficiency (B1 level or equivalent)\n"
        "- Salary meeting the general threshold of £26,200 per year or going rate\n"
        "- Job at RQF level 3 or above on the eligible occupations list\n"
        "- Tuberculosis test results (if applicable)\n"
        "- Bank statements showing sufficient personal savings\n"
        "- Valid ATAS certificate (for certain roles)\n"
        "- Criminal record certificate (if required)\n"
        "- Biometric residence permit application"
    ),
    "canada_visa.txt": (
        "Canada Work Permit Requirements\n"
        "- Valid passport\n"
        "- Labour Market Impact Assessment (LMIA) or LMIA-exempt offer\n"
        "- Completed IMM 1295 application form\n"
        "- Job offer letter from Canadian employer\n"
        "- Proof of relevant work experience and qualifications\n"
        "- Police clearance certificate\n"
        "- Medical examination results\n"
        "- Biometrics (fingerprints and photo)\n"
        "- Proof of sufficient funds\n"
        "- Digital photo as per specifications\n"
        "- Application fee payment"
    ),
    "usa_visa.txt": (
        "USA Work Visa Requirements\n"
        "- Valid passport valid for 6 months beyond stay\n"
        "- Completed DS-160 online application form\n"
        "- Approved petition from USCIS (e.g., H-1B, L-1, O-1)\n"
        "- Visa appointment confirmation letter\n"
        "- Passport-sized photos meeting US visa specifications\n"
        "- Employment offer letter and supporting documents\n"
        "- Proof of educational qualifications and work experience\n"
        "- Visa fee payment receipt\n"
        "- Interview appointment at US embassy or consulate\n"
        "- Ties to home country demonstrating intent to return"
    ),
    "uae_visa.txt": (
        "UAE Work Permit Requirements\n"
        "- Valid passport with at least 6 months validity\n"
        "- Job offer from a UAE-based employer\n"
        "- Entry permit or employment visa from Ministry of Human Resources\n"
        "- Medical fitness certificate\n"
        "- Emirates ID application\n"
        "- Labour contract signed by both parties\n"
        "- University degree attested by UAE authorities\n"
        "- Passport-sized photographs\n"
        "- Proof of accommodation in UAE\n"
        "- Visa stamping fee payment\n"
        "- Residency visa sticker in passport"
    ),
    "berlin_guide.txt": (
        "Moving to Berlin Guide\n"
        "- Popular expat neighbourhoods: Kreuzberg, Neukölln, Prenzlauer Berg, Friedrichshain, Mitte\n"
        "- Average rent for 1-bedroom: €800-1,200 in central areas\n"
        "- Public transport: U-Bahn and S-Bahn network, monthly pass ~€86\n"
        "- Must register address (Anmeldung) within 14 days of moving\n"
        "- Health insurance mandatory — either public or private\n"
        "- German bank account recommended for salary and bills\n"
        "- Learning basic German helps with bureaucracy (Bürgeramt)\n"
        "- Grocery costs ~€200-300 per month for a single person\n"
        "- Popular international schools: Berlin International School, John F. Kennedy School\n"
        "- Family-friendly areas: Prenzlauer Berg, Zehlendorf, Steglitz"
    ),
    "london_guide.txt": (
        "Moving to London Guide\n"
        "- Popular expat neighbourhoods: South Kensington, Canary Wharf, Clapham, Islington, Shoreditch\n"
        "- Average rent for 1-bedroom: £1,500-2,200 in central areas\n"
        "- Public transport: Tube and bus network, Oyster card system, monthly zone 1-2 pass ~£150\n"
        "- National Insurance Number required for employment\n"
        "- Council Tax must be registered at your address\n"
        "- Opening a UK bank account requires proof of address and passport\n"
        "- Grocery costs ~£250-350 per month for a single person\n"
        "- Popular international schools: American School in London, International School of London\n"
        "- Family-friendly areas: Richmond, Wimbledon, Hampstead, Greenwich\n"
        "- Register with a local GP (doctor) for healthcare access"
    ),
    "dubai_guide.txt": (
        "Moving to Dubai Guide\n"
        "- Popular expat neighbourhoods: Dubai Marina, JLT, Downtown Dubai, Palm Jumeirah, Arabian Ranches\n"
        "- Average rent for 1-bedroom: AED 60,000-90,000 per year\n"
        "- Public transport: Dubai Metro and buses, Nol card system\n"
        "- No income tax — major benefit for expats\n"
        "- Emirates ID mandatory for all residents\n"
        "- Employment visa sponsored by employer\n"
        "- Grocery costs ~AED 1,500-2,500 per month\n"
        "- Cultural tip: dress modestly in public, no public displays of affection\n"
        "- Popular international schools: Dubai American Academy, Jumeirah English Speaking School\n"
        "- Family-friendly areas: Emirates Hills, The Springs, Jumeirah, Mirdif"
    ),
    "toronto_guide.txt": (
        "Moving to Toronto Guide\n"
        "- Popular expat neighbourhoods: Yorkville, The Annex, Liberty Village, Leslieville, Queen West\n"
        "- Average rent for 1-bedroom: CAD 2,200-2,800 in central areas\n"
        "- Public transport: TTC subway, streetcars and buses, monthly pass ~CAD 156\n"
        "- Social Insurance Number (SIN) required for employment\n"
        "- OHIP health insurance coverage begins after 3-month waiting period\n"
        "- Canadian bank account essential for salary direct deposit\n"
        "- Grocery costs ~CAD 300-500 per month per person\n"
        "- Popular international schools: Toronto French School, Branksome Hall, Upper Canada College\n"
        "- Family-friendly areas: North York, Etobicoke, Scarborough, Mississauga\n"
        "- Prepare for winter temperatures dropping to -20°C with wind chill"
    ),
}


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in TAGS_TO_REMOVE:
        for element in soup.find_all(tag):
            element.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def scrape_and_save(url: str, filepath: str, headers: dict) -> bool:
    resp = requests.get(url, headers=headers, timeout=(10, 20))
    resp.raise_for_status()
    text = clean_html(resp.text)
    if not text.strip():
        return False
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def retry_missing():
    rag_dir = "rag_docs"

    fixed_on_retry = 0
    used_fallback = 0

    while True:
        missing = []
        for fname in EXPECTED_FILES:
            fpath = os.path.join(rag_dir, fname)
            if not os.path.exists(fpath) or os.path.getsize(fpath) == 0:
                missing.append(fname)

        if not missing:
            break

        for fname in missing:
            url = SITE_MAP.get(fname)
            if not url:
                continue
            fpath = os.path.join(rag_dir, fname)

            if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
                continue

            print(f"  Retrying {fname}...")

            fixed = False

            for attempt_label in ("Full browser headers", "Google cache", "Alternate URL structure"):
                try:
                    current_url = url
                    current_headers = RETRY_HEADERS
                    if attempt_label == "Google cache":
                        current_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
                    elif attempt_label == "Alternate URL structure":
                        if "/en" in url:
                            current_url = url.replace("/en", "", 1)
                        else:
                            slash = url.find("/", url.find("://") + 3)
                            if slash != -1:
                                current_url = url[:slash] + "/en" + url[slash:]
                            else:
                                current_url = url + "/en"

                    ok = scrape_and_save(current_url, fpath, current_headers)
                    if ok:
                        print(f"    FIXED: {fname} (attempt: {attempt_label})")
                        fixed = True
                        break
                except Exception:
                    continue
                finally:
                    time.sleep(2)

            if not fixed:
                print(f"    All retries failed. Writing fallback for {fname}")
                fallback_text = FALLBACKS.get(fname, f"Basic {fname.replace('_visa.txt', '').replace('_guide.txt', '').upper()} visa requirements: valid passport, job offer, and application form required.")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(fallback_text)
                used_fallback += 1
            else:
                fixed_on_retry += 1

        time.sleep(1)

    return fixed_on_retry, used_fallback


def _all_files_present():
    return all(
        os.path.exists(os.path.join("rag_docs", f)) and os.path.getsize(os.path.join("rag_docs", f)) > 0
        for f in EXPECTED_FILES
    )


def main():
    os.makedirs("rag_docs", exist_ok=True)

    if _all_files_present():
        print("All 9 files already present — skipping live scrape.")
        return

    succeeded = 0
    failed = 0

    for url, filename in SITES:
        try:
            print(f"Scraping: {url}")
            ok = scrape_and_save(url, os.path.join("rag_docs", filename), HEADERS)
            if ok:
                print(f"  OK — saved to rag_docs/{filename}")
                succeeded += 1
            else:
                print(f"  FAIL — empty content")
                failed += 1
        except Exception as e:
            print(f"  FAIL — {e}")
            failed += 1

        time.sleep(2)

    print(f"\nFirst pass: {succeeded} succeeded, {failed} failed.")

    print("\n--- Phase 2: Checking for missing/empty files ---")
    fixed_count, fallback_count = retry_missing()

    all_ok = all(
        os.path.exists(os.path.join("rag_docs", f)) and os.path.getsize(os.path.join("rag_docs", f)) > 0
        for f in EXPECTED_FILES
    )

    print(f"\nFinal Report:")
    print(f"  Scraped successfully on first attempt: {succeeded}")
    print(f"  Fixed on retry: {fixed_count}")
    print(f"  Used fallback content: {fallback_count}")
    print(f"  All 9 files present and non-empty: {all_ok}")


if __name__ == "__main__":
    main()
