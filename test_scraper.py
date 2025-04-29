from app.scraper import SubitoScraper

def main():
    scraper = SubitoScraper()
    print("\n🔍 Inizio ricerca annunci...")
    print("=" * 50)
    
    ads = scraper.search_ads()
    
    if ads:
        print(f"\n✅ Trovati {len(ads)} annunci corrispondenti:")
        print("=" * 50)
        for ad in ads:
            print(f"\n📌 Titolo: {ad['title']}")
            print(f"💰 Prezzo: €{ad['price']}")
            print(f"🔗 Link: {ad['link']}")
            print("-" * 50)
    else:
        print("\n❌ Nessun annuncio trovato")

if __name__ == "__main__":
    main() 