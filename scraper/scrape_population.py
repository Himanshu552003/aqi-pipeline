# scrape_population.py - scrape Indian city populations from Wikipedia (HTML scraping with BeautifulSoup)
#
# Page: https://en.wikipedia.org/wiki/List_of_cities_in_India_by_population
# robots.txt allows /wiki/ pages. Content is CC BY-SA 4.0 (attribution in README).
# Population changes slowly, so this runs ONCE (not hourly) and writes a dbt seed file:
#   python -m scraper.scrape_population
import logging
import os

import pandas as pd
import requests
from bs4 import BeautifulSoup

from scraper.scrape import HEADERS

URL = "https://en.wikipedia.org/wiki/List_of_cities_in_India_by_population"
SEED_PATH = os.path.join("dbt_project", "seeds", "city_population.csv")

logger = logging.getLogger(__name__)


def to_int(text: str) -> int | None:
    """'12,442,373' -> 12442373; anything non-numeric -> None."""
    digits = text.replace(",", "").strip()
    return int(digits) if digits.isdigit() else None


def parse_table(html: str) -> pd.DataFrame:
    """Parse the population table (one row per city) out of the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.wikitable")
    if table is None:
        raise RuntimeError("Population table not found - the page layout may have changed")

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 6:            # header rows and the 'India' total row have fewer <td>s
            continue

        # The city name is the link text; the cell also holds markers like '‡' that we skip
        city_link = cells[0].find("a")
        city = (city_link or cells[0]).get_text(strip=True)
        state = cells[1].get_text(" ", strip=True)

        # Coordinates live in a hidden <span class="geo">19.0760; 72.8777</span>
        lat = lon = None
        geo = cells[5].select_one("span.geo")
        if geo:
            lat_text, lon_text = geo.get_text().split(";")
            lat, lon = float(lat_text), float(lon_text)

        rows.append({
            "city": city,
            "state": state,
            "population_2011": to_int(cells[2].get_text()),
            "population_2001": to_int(cells[3].get_text()),
            "latitude": lat,
            "longitude": lon,
        })

    df = pd.DataFrame(rows).dropna(subset=["population_2011"])
    df["population_2011"] = df["population_2011"].astype(int)
    df["population_2001"] = df["population_2001"].astype("Int64")
    return df


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    df = parse_table(response.text)
    os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)
    df.to_csv(SEED_PATH, index=False)
    logger.info("Saved %d cities to %s", len(df), SEED_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    main()
