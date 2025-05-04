import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import time
import random
import datetime
import json
import traceback
from typing import List, Dict, Tuple

def run_market_research_page():
    """
    Funzione principale che gestisce la pagina Market Research
    """
    st.title("Market Research - Analisi di Mercato")
    
    # Layout della pagina
    st.write("Esegui ricerche di mercato su Subito.it per ottenere statistiche e prezzi in tempo reale.")
    
    # Form di ricerca
    with st.form("market_research_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            keyword = st.text_input("Prodotto da cercare", placeholder="Es. PS5, iPhone 14, Xbox Series S")
            max_pages = st.slider("Numero di pagine da analizzare", min_value=1, max_value=5, value=2)
            ricerca_specifica = st.checkbox("Ricerca Specifica", help="Aggiunge il parametro qso=true per una ricerca più precisa")
        
        with col2:
            apply_price_limit = st.checkbox("Applica filtro prezzo")
            min_price = st.number_input("Prezzo minimo (€)", min_value=0, value=0, disabled=not apply_price_limit)
            max_price = st.number_input("Prezzo massimo (€)", min_value=0, value=1000, disabled=not apply_price_limit)
        
        submitted = st.form_submit_button("Esegui Ricerca di Mercato")
    
    # Se il form è stato inviato, esegui la ricerca
    if submitted:
        if not keyword:
            st.error("Inserisci un prodotto da cercare")
            return
            
        with st.spinner(f"Analisi in corso per '{keyword}'..."):
            try:
                # Esegui la ricerca
                results = perform_market_search(
                    keyword, 
                    max_pages=max_pages,
                    min_price=min_price if apply_price_limit else None,
                    max_price=max_price if apply_price_limit else None,
                    ricerca_specifica=ricerca_specifica
                )
                
                # Mostra i risultati
                display_market_results(results, keyword)
            except Exception as e:
                st.error(f"Si è verificato un errore durante l'analisi: {str(e)}")
                st.error(traceback.format_exc())

def perform_market_search(keyword: str, max_pages: int = 2, min_price: float = None, max_price: float = None, ricerca_specifica: bool = False) -> Dict:
    """
    Esegue una ricerca di mercato su Subito.it
    
    Args:
        keyword: Prodotto da cercare
        max_pages: Numero massimo di pagine da analizzare
        min_price: Prezzo minimo (opzionale)
        max_price: Prezzo massimo (opzionale)
        ricerca_specifica: Se True, aggiunge "&qso=true" all'URL per una ricerca più specifica
        
    Returns:
        Dict: Risultati della ricerca con statistiche
    """
    # Parametri di ricerca
    base_url = "https://www.subito.it/annunci-italia/vendita/usato/?q="
    
    # Aggiungi il parametro di ricerca specifica se richiesto
    if ricerca_specifica:
        base_url += f"{keyword}&qso=true"
    else:
        base_url += keyword
    
    # Lista per salvare tutti i risultati
    all_results = []
    
    # Configurazione della sessione HTTP
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    })
    
    try:
        # Esegui la ricerca per ogni pagina
        for page in range(1, max_pages + 1):
            # Costruisci l'URL della pagina con il parametro o incluso nella query di base
            if ricerca_specifica:
                page_url = f"{base_url}&o={page}"
            else:
                page_url = f"{base_url}&o={page}"
            
            st.info(f"Analisi pagina {page}/{max_pages}: {page_url}")
            
            # Aggiungi un ritardo random per evitare il blocco
            time.sleep(random.uniform(1, 2))
            
            response = session.get(page_url)
            response.raise_for_status()
            
            # Estrai i dati JSON dall'HTML
            json_data = _extract_json_from_html(response.text)
            
            # Estrai i risultati dal JSON
            page_results = _get_results_from_json(json_data)
            
            # Aggiungi dati da HTML per venduto
            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.select('div.items__item')
            
            for card in cards:
                # Estrai URL per match con risultato
                link_el = card.select_one('a')
                url = link_el['href'] if link_el and 'href' in link_el.attrs else None
                
                # Estrai stato venduto (badge o testo)
                venduto = False
                badge_venduto = card.find(string=lambda t: t and 'venduto' in t.lower())
                if badge_venduto:
                    venduto = True
                
                # Trova il risultato corrispondente per URL e aggiorna
                for res in page_results:
                    if url and res.get('url') and url in res['url']:
                        res['venduto'] = venduto
                        # Aggiorna anche il prezzo se visibile
                        price_el = card.select_one('p.index-module_price__N7M2x')
                        if price_el:
                            try:
                                price_text = price_el.text.strip()
                                prezzo_html = float(''.join(c for c in price_text if c.isdigit() or c == ',').replace(',', '.'))
                                res['prezzo'] = prezzo_html
                            except Exception:
                                pass
            
            if not page_results:
                st.warning(f"Nessun risultato trovato nella pagina {page}")
                if page == 1:
                    # Nessun risultato nella prima pagina, simula risultati
                    return _simulate_market_results(keyword, min_price, max_price)
                break
            
            all_results.extend(page_results)
            
            # Se ci sono meno risultati del previsto, probabilmente è l'ultima pagina
            if len(page_results) < 20:
                break
        
        # Applica filtri di prezzo se specificati
        if min_price is not None or max_price is not None:
            min_p = min_price if min_price is not None else 0
            max_p = max_price if max_price is not None else float('inf')
            
            all_results = [r for r in all_results if r.get('prezzo', 0) >= min_p and r.get('prezzo', 0) <= max_p]
        
        # Calcola le statistiche
        stats = calculate_market_statistics(all_results)
        
        return {
            "results": all_results,
            "stats": stats,
            "keyword": keyword,
            "ricerca_specifica": ricerca_specifica
        }
            
    except Exception as e:
        st.error(f"Errore durante la ricerca: {str(e)}")
        st.error(traceback.format_exc())
        return _simulate_market_results(keyword, min_price, max_price)

def _extract_json_from_html(html):
    """
    Estrae i dati JSON dallo script nell'HTML della pagina
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Cerca lo script contenente i dati JSON
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        
        if not script_tag:
            return None
        
        json_text = script_tag.string
        json_data = json.loads(json_text)
        
        # Estrai i dati dei risultati
        if 'props' in json_data and 'pageProps' in json_data['props'] and 'initialState' in json_data['props']['pageProps']:
            return json_data['props']['pageProps']['initialState']
        
        return None
        
    except Exception as e:
        st.error(f"Errore nell'estrazione dei dati JSON: {str(e)}")
        return None

def _get_results_from_json(json_data):
    """
    Estrae i risultati dal JSON della risposta
    """
    results = []
    try:
        if not json_data or 'items' not in json_data or 'list' not in json_data['items']:
            return results
        
        items_list = json_data['items']['list']
        for decorated_item in items_list:
            if 'item' in decorated_item and 'kind' in decorated_item['item'] and decorated_item['item']['kind'] == 'AdItem':
                ad_item = decorated_item['item']
                
                # Estrai i dati dell'annuncio
                titolo = ad_item.get('subject', 'Titolo non disponibile')
                prezzo_raw = _extract_price(ad_item)
                luogo = _extract_location(ad_item)
                data = _extract_date(ad_item)
                url = _extract_url(ad_item)
                item_id = _extract_id(ad_item)
                
                # Ignora annunci con prezzo 0 (o non disponibile)
                if prezzo_raw <= 0:
                    continue
                
                result = {
                    'titolo': titolo,
                    'prezzo': prezzo_raw,
                    'luogo': luogo,
                    'data': data,
                    'url': url,
                    'id': item_id,
                    'venduto': False  # Default, sarà aggiornato con i dati visibili
                }
                
                results.append(result)
    except Exception as e:
        st.error(f"Errore nell'estrazione dei risultati: {str(e)}")
    
    return results

def _extract_price(ad_item):
    """Estrae il prezzo dall'elemento annuncio"""
    try:
        if 'features' in ad_item and '/price' in ad_item['features']:
            price_feature = ad_item['features']['/price']
            if 'values' in price_feature and len(price_feature['values']) > 0:
                return float(price_feature['values'][0]['key'].replace(',', '.'))
    except (ValueError, KeyError, IndexError):
        pass
    
    return 0

def _extract_location(ad_item):
    """Estrae solo la città dall'elemento annuncio"""
    try:
        if 'geo' in ad_item:
            geo_data = ad_item['geo']
            city = geo_data.get('city', {}).get('value', '')
            
            # Se non c'è la città, prova con il comune
            if not city:
                city = geo_data.get('town', {}).get('value', '')
            
            return city if city else "Città non specificata"
    except Exception:
        pass
    
    return "Città non specificata"

def _extract_date(ad_item):
    """Estrae la data dall'elemento annuncio"""
    try:
        if 'date' in ad_item:
            date_str = ad_item['date']
            # Converti la stringa di data in un oggetto datetime
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            return date_obj.strftime('%d/%m/%Y %H:%M')
    except Exception:
        pass
    
    return "Data non disponibile"

def _extract_url(ad_item):
    """Estrae l'URL dall'elemento annuncio"""
    try:
        if 'urls' in ad_item and 'default' in ad_item['urls']:
            return ad_item['urls']['default']
    except (KeyError, IndexError):
        pass
    
    return "#"

def _extract_id(ad_item):
    """Estrae l'ID dell'annuncio"""
    try:
        if 'urn' in ad_item:
            # urn format: "id:ad:61451886-7fac-477b-8896-a782e83a7821:list:600534176"
            urn_parts = ad_item['urn'].split(':')
            if len(urn_parts) >= 5:
                return urn_parts[4]  # Ultimo elemento
    except (KeyError, IndexError):
        pass
    
    return "unknown"

def calculate_market_statistics(results: List[Dict]) -> Dict:
    """
    Calcola statistiche di mercato sui risultati, ignorando annunci con prezzo 0
    
    Args:
        results: Lista di risultati con prezzi e stato venduto
        
    Returns:
        Dict: Statistiche di mercato
    """
    # Filtra i risultati con prezzo valido (maggiore di 0)
    valid_results = [r for r in results if r.get('prezzo', 0) > 0]
    
    # Divide i risultati in venduti e disponibili
    venduti = [r for r in valid_results if r.get('venduto', False)]
    disponibili = [r for r in valid_results if not r.get('venduto', False)]
    
    # Calcola le statistiche
    total_count = len(valid_results)
    venduti_count = len(venduti)
    disponibili_count = len(disponibili)
    
    # Sell through rate (percentuale di annunci venduti sul totale)
    sell_through_rate = (venduti_count / total_count) * 100 if total_count > 0 else 0
    
    # Prezzo medio disponibili
    avg_price_disponibili = sum(r.get('prezzo', 0) for r in disponibili) / disponibili_count if disponibili_count > 0 else 0
    
    # Prezzo medio venduti
    avg_price_venduti = sum(r.get('prezzo', 0) for r in venduti) / venduti_count if venduti_count > 0 else 0
    
    # Prezzo minimo e massimo
    all_prices = [r.get('prezzo', 0) for r in valid_results]
    min_price = min(all_prices) if all_prices else 0
    max_price = max(all_prices) if all_prices else 0
    
    # Prezzo mediano
    if all_prices:
        all_prices.sort()
        if len(all_prices) % 2 == 0:
            median_price = (all_prices[len(all_prices)//2-1] + all_prices[len(all_prices)//2]) / 2
        else:
            median_price = all_prices[len(all_prices)//2]
    else:
        median_price = 0
    
    # Analisi per località
    locations_data = {}
    for r in valid_results:
        location = r.get('luogo', 'Non specificata')
        if location not in locations_data:
            locations_data[location] = {
                'total': 0,
                'available': 0,
                'sold': 0,
                'total_price': 0,
            }
        
        locations_data[location]['total'] += 1
        locations_data[location]['total_price'] += r.get('prezzo', 0)
        
        if r.get('venduto', False):
            locations_data[location]['sold'] += 1
        else:
            locations_data[location]['available'] += 1
    
    # Calcola statistiche aggiuntive per località
    top_locations = []
    for loc, data in locations_data.items():
        sell_rate = (data['sold'] / data['total']) * 100 if data['total'] > 0 else 0
        avg_price = data['total_price'] / data['total'] if data['total'] > 0 else 0
        percent_of_total = (data['total'] / total_count) * 100 if total_count > 0 else 0
        percent_of_sold = (data['sold'] / venduti_count) * 100 if venduti_count > 0 else 0
        
        top_locations.append({
            'location': loc,
            'total': data['total'],
            'available': data['available'],
            'sold': data['sold'],
            'sell_rate': sell_rate,
            'avg_price': avg_price,
            'percent_of_total': percent_of_total,
            'percent_of_sold': percent_of_sold
        })
    
    # Ordina località dando priorità a:
    # 1. Numero di annunci venduti (decrescente)
    # 2. Numero totale di annunci (decrescente)
    top_locations.sort(key=lambda x: (-x['sold'], -x['total']))
    
    return {
        "total_count": total_count,
        "disponibili_count": disponibili_count,
        "venduti_count": venduti_count,
        "sell_through_rate": sell_through_rate,
        "avg_price_disponibili": avg_price_disponibili,
        "avg_price_venduti": avg_price_venduti,
        "min_price": min_price,
        "max_price": max_price,
        "median_price": median_price,
        "locations": top_locations
    }

def _simulate_market_results(keyword: str, min_price: float = None, max_price: float = None) -> Dict:
    """
    Genera risultati simulati quando non è possibile ottenere dati reali
    
    Args:
        keyword: Prodotto cercato
        min_price: Prezzo minimo (opzionale)
        max_price: Prezzo massimo (opzionale)
        
    Returns:
        Dict: Risultati simulati con statistiche
    """
    st.warning("Non è stato possibile ottenere dati reali. Verranno generati dati simulati per la dimostrazione.")
    
    # Genera un numero casuale di risultati tra 20 e 50
    num_results = random.randint(20, 50)
    
    # Definisci un prezzo medio di base in base alla keyword
    base_price = _get_base_price(keyword)
    
    # Genera risultati casuali
    results = []
    
    # Genera varianti per titoli
    variants = _get_product_variants(keyword)
    
    # Genera URL di ricerca per gli annunci simulati
    base_url = f"https://www.subito.it/annunci-italia/vendita/usato/?q={keyword}"
    
    for i in range(num_results):
        # Crea un titolo mescolando la keyword con alcune varianti casuali
        product = random.choice(variants)
        titolo = f"{product} - {random.choice(['come nuovo', 'poco usato', 'perfette condizioni', 'in garanzia'])}"
        
        # Prezzo casuale con variazione fino a ±40% dal prezzo base
        variation = random.uniform(-0.4, 0.4)
        prezzo = round(base_price * (1 + variation), 2)
        
        # Applica eventuali filtri di prezzo
        if min_price is not None and prezzo < min_price:
            prezzo = min_price + random.uniform(0, 50)
        if max_price is not None and prezzo > max_price:
            prezzo = max_price - random.uniform(0, 50)
        
        # Località casuale
        province = ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze", "Palermo", "Genova"]
        luogo = random.choice(province)
        
        # Data casuale negli ultimi 30 giorni
        days_ago = random.randint(0, 30)
        date_obj = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        data = date_obj.strftime("%d/%m/%Y %H:%M")
        
        # ID e URL
        item_id = f"sim_{int(time.time())}_{i}"
        url = f"{base_url}&sim_id={item_id}"
        
        # Circa il 20% degli annunci è venduto
        venduto = random.random() < 0.2
        
        result = {
            'titolo': titolo,
            'prezzo': prezzo,
            'luogo': luogo,
            'data': data,
            'url': url,
            'id': item_id,
            'venduto': venduto
        }
        
        results.append(result)
    
    # Calcola statistiche sui risultati simulati
    stats = calculate_market_statistics(results)
    
    return {
        "results": results,
        "stats": stats,
        "keyword": keyword,
        "simulated": True
    }

def _get_product_variants(keyword: str) -> List[str]:
    """
    Restituisce varianti di prodotti in base alla keyword
    """
    # Prodotti predefiniti in base alle possibili keyword
    variants = {
        "ps5": ["PlayStation 5", "PS5 Digital Edition", "PS5 Slim", "PlayStation 5 Pro", "PS5 con giochi", "PS5 bundle", "Console PS5"],
        "ps4": ["PlayStation 4", "PS4 Pro", "PS4 Slim", "PS4 500GB", "PlayStation 4 Pro", "PS4 con giochi", "Console PS4"],
        "iphone": ["iPhone 15", "iPhone 14 Pro", "iPhone 13", "iPhone 15 Pro Max", "iPhone 12", "iPhone SE"],
        "macbook": ["MacBook Pro", "MacBook Air M2", "MacBook Pro 16", "MacBook M1", "Apple MacBook"],
        "nintendo": ["Nintendo Switch", "Nintendo Switch OLED", "Switch Lite", "Nintendo Switch bundle"],
        "xbox": ["Xbox Series X", "Xbox Series S", "Xbox One", "Xbox Elite"]
    }
    
    # Trova la categoria più vicina
    for key, values in variants.items():
        if key in keyword.lower():
            return values
    
    # Se non trova corrispondenze, usa un set generico
    return [f"{keyword.upper()}", f"{keyword.capitalize()} nuovo", f"{keyword} come nuovo", f"{keyword} usato poco"]

def _get_base_price(keyword: str) -> float:
    """
    Restituisce un prezzo base in base alla keyword
    """
    keyword_lower = keyword.lower()
    
    if "ps5" in keyword_lower:
        return 450
    elif "ps4" in keyword_lower:
        return 250
    elif "iphone" in keyword_lower:
        if "15" in keyword_lower and "pro" in keyword_lower:
            return 1200
        elif "14" in keyword_lower:
            return 800
        else:
            return 600
    elif "macbook" in keyword_lower:
        return 1300
    elif "nintendo" in keyword_lower or "switch" in keyword_lower:
        return 280
    elif "xbox" in keyword_lower:
        if "series x" in keyword_lower:
            return 450
        elif "series s" in keyword_lower:
            return 300
        else:
            return 250
    else:
        return 300  # Prezzo generico per altre keyword

def display_market_results(results: Dict, keyword: str):
    """
    Visualizza i risultati dell'analisi di mercato in modo grafico e tabellare
    
    Args:
        results: Risultati dell'analisi di mercato
        keyword: Keyword cercata
    """
    stats = results.get("stats", {})
    all_results = results.get("results", [])
    is_simulated = results.get("simulated", False)
    
    # Mostra avviso se i dati sono simulati
    if is_simulated:
        st.warning("I dati mostrati sono simulati per scopi dimostrativi.")
    
    # Dashboard principale con KPI
    st.subheader("📊 Dashboard di Mercato")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Annunci Totali", f"{stats.get('total_count', 0)}")
        st.metric("Annunci Disponibili", f"{stats.get('disponibili_count', 0)}")
        st.metric("Annunci Venduti", f"{stats.get('venduti_count', 0)}")
    
    with col2:
        st.metric("Prezzo Medio Disponibili", f"€{stats.get('avg_price_disponibili', 0):.2f}")
        st.metric("Prezzo Medio Venduti", f"€{stats.get('avg_price_venduti', 0):.2f}")
        st.metric("Prezzo Mediano", f"€{stats.get('median_price', 0):.2f}")
    
    with col3:
        st.metric("Sell Through Rate", f"{stats.get('sell_through_rate', 0):.1f}%")
        st.metric("Prezzo Minimo", f"€{stats.get('min_price', 0):.2f}")
        st.metric("Prezzo Massimo", f"€{stats.get('max_price', 0):.2f}")
    
    # Grafico distribuzione prezzi e vendita
    st.subheader("📈 Analisi Grafica")
    
    if all_results:
        # Prepara i dati per i grafici
        disponibili = [r for r in all_results if not r.get('venduto', False)]
        venduti = [r for r in all_results if r.get('venduto', False)]
        
        disponibili_prices = [r.get('prezzo', 0) for r in disponibili if r.get('prezzo', 0) > 0]
        venduti_prices = [r.get('prezzo', 0) for r in venduti if r.get('prezzo', 0) > 0]
        
        # Crea una figura con due grafici affiancati
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Grafico 1: Istogramma dei prezzi
        ax1.hist(disponibili_prices, bins=10, alpha=0.7, label='Disponibili', color='blue')
        ax1.hist(venduti_prices, bins=10, alpha=0.7, label='Venduti', color='green')
        ax1.set_title('Distribuzione dei Prezzi')
        ax1.set_xlabel('Prezzo (€)')
        ax1.set_ylabel('Numero Annunci')
        ax1.legend()
        
        # Grafico 2: Confronto prezzi medi tra disponibili e venduti
        labels = ['Disponibili', 'Venduti']
        values = [stats.get('avg_price_disponibili', 0), stats.get('avg_price_venduti', 0)]
        
        ax2.bar(labels, values, color=['blue', 'green'])
        ax2.set_title('Confronto Prezzi Medi')
        ax2.set_ylabel('Prezzo Medio (€)')
        
        # Aggiungi valori sopra le barre
        for i, v in enumerate(values):
            ax2.text(i, v + 5, f"€{v:.2f}", ha='center')
        
        # Mostra il grafico
        plt.tight_layout()
        st.pyplot(fig)
        
        # Sezione di analisi per località
        st.subheader("📍 Analisi per Località")
        
        # Ottieni le località dai risultati
        locations = stats.get('locations', [])
        
        if locations:
            # Mostra solo le prime 10 località più frequenti per leggibilità
            top_n = min(10, len(locations))
            top_locs = locations[:top_n]
            
            # Crea una tabella per le statistiche delle località
            loc_data = []
            for loc in top_locs:
                loc_data.append({
                    'Località': loc['location'],
                    'Totale Annunci': loc['total'],
                    'Disponibili': loc['available'],
                    'Venduti': loc['sold'],
                    'Sell-Through Rate': f"{loc['sell_rate']:.1f}%",
                    '% sul Totale': f"{loc['percent_of_total']:.1f}%",
                    '% sui Venduti': f"{loc['percent_of_sold']:.1f}%",
                    'Prezzo Medio': f"€{loc['avg_price']:.2f}"
                })
            
            # Crea DataFrame e mostra tabella
            loc_df = pd.DataFrame(loc_data)
            st.dataframe(loc_df)
            
            # Visualizzazione grafica delle località
            col1, col2 = st.columns(2)
            
            with col1:
                # Grafico a torta per distribuzione annunci per località
                fig, ax = plt.subplots(figsize=(8, 8))
                labels = [f"{loc['location']} ({loc['total']})" for loc in top_locs]
                sizes = [loc['total'] for loc in top_locs]
                
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                plt.title('Distribuzione Annunci per Località')
                st.pyplot(fig)
            
            with col2:
                # Grafico a barre per Sell-Through Rate per località
                fig, ax = plt.subplots(figsize=(8, 8))
                locations_names = [loc['location'] for loc in top_locs]
                sell_rates = [loc['sell_rate'] for loc in top_locs]
                
                ax.barh(locations_names, sell_rates, color='orange')
                ax.set_xlabel('Sell-Through Rate (%)')
                ax.set_title('Percentuale di Vendita per Località')
                
                # Aggiungi etichette ai valori
                for i, v in enumerate(sell_rates):
                    ax.text(v + 1, i, f"{v:.1f}%", va='center')
                
                st.pyplot(fig)
        else:
            st.info("Dati per località non disponibili.")
        
        # Tabella con tutti gli annunci
        st.subheader("📋 Dettaglio Annunci")
        
        # Crea un DataFrame con i risultati, escludendo quelli con prezzo 0
        df = pd.DataFrame([r for r in all_results if r.get('prezzo', 0) > 0])
        
        if not df.empty:
            # Formatta le colonne
            df = df[['titolo', 'prezzo', 'luogo', 'data', 'venduto', 'url']]
            df.columns = ['Titolo', 'Prezzo (€)', 'Località', 'Data', 'Venduto', 'URL']
            
            # Formatta la colonna venduto come Sì/No
            df['Venduto'] = df['Venduto'].apply(lambda x: "✅ Sì" if x else "❌ No")
            
            # Mostra la tabella con la possibilità di ordinarla
            st.dataframe(df)
            
            # Opzione per scaricare i dati come CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Scarica Dati CSV",
                data=csv,
                file_name=f"market_research_{keyword}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("Nessun risultato disponibile per la visualizzazione tabellare.")
    else:
        st.info("Nessun risultato disponibile per l'analisi grafica.")

if __name__ == "__main__":
    run_market_research_page() 