import streamlit as st
import pandas as pd
import time
import os
import sys
import threading
import datetime
import json
import matplotlib.pyplot as plt
import numpy as np
import logging
import glob
from sqlalchemy import func

# Configura il logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data/snipedeal.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SnipeDeal")

# Aggiungi la directory backend al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database_schema import init_db, Keyword, Risultato, Statistiche, SessionLocal, SeenAds
from scraper_adapter import scraper_adapter

try:
    # Inizializza il database
    init_db()
    logger.info("Database inizializzato con successo")
except Exception as e:
    logger.error(f"Errore durante l'inizializzazione del database: {str(e)}")

# Configura la pagina Streamlit
st.set_page_config(
    page_title="SnipeDeal - Monitoraggio Annunci",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Funzione per connessione al database
def get_session():
    session = SessionLocal()
    try:
        return session
    finally:
        session.close()

# Funzione per mostrare le statistiche
def show_statistics(keyword_id):
    try:
        stats = scraper_adapter.get_statistics(keyword_id)
        if not stats:
            st.info("Nessuna statistica disponibile per questa keyword")
            return
        
        # Crea due colonne per le statistiche
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Statistiche di Prezzo")
            # Crea un grafico a barre per le statistiche di prezzo
            fig, ax = plt.subplots(figsize=(10, 6))
            prices = [
                stats["prezzo_minimo"],
                stats["prezzo_medio"],
                stats["prezzo_mediano"],
                stats["prezzo_massimo"]
            ]
            labels = ["Min", "Media", "Mediana", "Max"]
            ax.bar(labels, prices, color=['green', 'blue', 'orange', 'red'])
            ax.set_ylabel('Prezzo (€)')
            ax.set_title('Statistiche di Prezzo')
            
            # Aggiungi valori sopra le barre
            for i, v in enumerate(prices):
                ax.text(i, v + 5, f"€{v:.2f}", ha='center')
            
            st.pyplot(fig)
        
        with col2:
            st.subheader("Altre Statistiche")
            
            # Mostra altre statistiche in formato tabella
            data = {
                "Metrica": ["Numero Annunci", "Annunci Venduti", "Sell Through Rate"],
                "Valore": [
                    stats["numero_annunci"],
                    stats["annunci_venduti"],
                    f"{stats['sell_through_rate']*100:.1f}%"
                ]
            }
            st.table(pd.DataFrame(data))
            
            # Aggiungi data di aggiornamento
            st.write(f"Ultimo aggiornamento: {stats['data_aggiornamento']}")
            
            # Crea un grafico a torta per la percentuale di venduti/non venduti
            if stats["numero_annunci"] > 0:
                fig, ax = plt.subplots(figsize=(6, 6))
                sizes = [stats["annunci_venduti"], stats["numero_annunci"] - stats["annunci_venduti"]]
                labels = ['Venduti', 'Non Venduti']
                explode = (0.1, 0)  # esplodi la prima fetta
                ax.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%',
                      shadow=True, startangle=90)
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                st.pyplot(fig)
    except Exception as e:
        logger.error(f"Errore durante la visualizzazione delle statistiche: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")

# Funzione per leggere le configurazioni Telegram salvate
def get_telegram_config():
    try:
        # Prima controlla .env nella directory principale
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        
        # Se non esiste, controlla nella cartella backend (percorso precedente)
        if not os.path.exists(env_path):
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', '.env')
        
        if os.path.exists(env_path):
            config = {}
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config[key] = value
            
            token = config.get('TELEGRAM_BOT_TOKEN', '')
            chat_id = config.get('TELEGRAM_CHAT_ID', '')
            
            logger.info(f"Configurazione Telegram letta: token presente: {bool(token)}, chat_id presente: {bool(chat_id)}")
            return token, chat_id
        else:
            logger.warning(f"File di configurazione non trovato in: {env_path}")
            return '', ''
    except Exception as e:
        logger.error(f"Errore durante la lettura della configurazione Telegram: {str(e)}")
        return '', ''

# Funzione per visualizzare i log dello scraper
def show_scraper_logs():
    """Visualizza i log dello scraper con formattazione colorata"""
    logs = scraper_adapter.get_logs()
    
    if not logs:
        st.info("Nessun log dello scraper disponibile.")
        return
    
    # Crea un formato più leggibile
    st.subheader(f"Log del Core Scraper ({len(logs)} eventi)")
    
    # Opzioni di filtro
    log_levels = ["Tutti", "ERROR", "WARNING", "INFO"]
    selected_level = st.selectbox("Filtra per livello", log_levels)
    
    if selected_level != "Tutti":
        filtered_logs = [log for log in logs if log["level"] == selected_level]
    else:
        filtered_logs = logs
    
    # Mostra numero di log per tipo
    error_count = len([log for log in logs if log["level"] == "ERROR"])
    warning_count = len([log for log in logs if log["level"] == "WARNING"])
    info_count = len([log for log in logs if log["level"] == "INFO"])
    
    counts_col1, counts_col2, counts_col3 = st.columns(3)
    counts_col1.metric("Errori", error_count, delta=None, delta_color="inverse")
    counts_col2.metric("Avvisi", warning_count, delta=None, delta_color="inverse")
    counts_col3.metric("Info", info_count, delta=None, delta_color="normal")
    
    # Crea una tabella con i log
    if filtered_logs:
        log_data = []
        for log in filtered_logs:
            log_data.append({
                "Timestamp": log["timestamp"],
                "Livello": log["level"],
                "Messaggio": log["message"]
            })
        
        df = pd.DataFrame(log_data)
        
        # Applica stili per evidenziare i livelli di log
        def highlight_level(val):
            color = ""
            if val == "ERROR":
                color = "background-color: rgba(255, 0, 0, 0.2)"
            elif val == "WARNING":
                color = "background-color: rgba(255, 165, 0, 0.2)"
            elif val == "INFO":
                color = "background-color: rgba(0, 128, 0, 0.1)"
            return color
        
        styled_df = df.style.applymap(highlight_level, subset=["Livello"])
        st.dataframe(styled_df, height=400)
        
        # Pulsante per cancellare i log dello scraper
        if st.button("Cancella Log dello Scraper"):
            scraper_adapter.scraper_logs = []
            st.success("Log dello scraper cancellati con successo.")
            st.experimental_rerun()
    else:
        st.info(f"Nessun log di livello {selected_level} disponibile.")

# Barra laterale
st.sidebar.title("SnipeDeal")
st.sidebar.image("https://img.icons8.com/color/96/000000/price-tag--v1.png", width=100)

# Menu nella barra laterale
menu = st.sidebar.radio(
    "Menu",
    ["Dashboard", "Risultati", "Gestione Campagne", "Log Scraper", "Ricerche Programmate", "Impostazioni", "Log Sistema", "Seen Ads"]
)

# Ottieni tutti i risultati nel database
def get_all_results():
    session = get_session()
    try:
        results = session.query(Risultato).order_by(Risultato.created_at.desc()).limit(100).all()
        return results
    finally:
        session.close()

# Gestione della pagina selezionata
if menu == "Dashboard":
    st.title("Dashboard SnipeDeal")
    
    try:
        # Statistiche generali
        session = get_session()
        try:
            num_keywords = session.query(Keyword).count()
            num_active = session.query(Keyword).filter(Keyword.attivo == True).count()
            num_results = session.query(Risultato).count()
            num_sold = session.query(Risultato).filter(Risultato.venduto == True).count()
            
            # Visualizza statistiche in 4 colonne
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Campagne Totali", num_keywords)
            col2.metric("Campagne Attive", num_active)
            col3.metric("Annunci Totali", num_results)
            col4.metric("Annunci Venduti", num_sold)
            
            # Risultati più recenti
            st.subheader("Ultimi Annunci Trovati")
            latest_results = session.query(Risultato).order_by(Risultato.created_at.desc()).limit(10).all()
            
            if latest_results:
                result_data = []
                for res in latest_results:
                    keyword = session.query(Keyword).filter(Keyword.id == res.keyword_id).first()
                    keyword_name = keyword.keyword if keyword else "N/A"
                    
                    result_data.append({
                        "Keyword": keyword_name,
                        "Titolo": res.titolo,
                        "Prezzo": f"€{res.prezzo:.2f}",
                        "Data": res.data_annuncio,
                        "Luogo": res.luogo,
                        "Venduto": "Sì" if res.venduto else "No"
                    })
                
                st.dataframe(pd.DataFrame(result_data))
            else:
                st.info("Nessun risultato disponibile")
            
            # Lista delle campagne con grafici
            st.subheader("Statistiche Campagne")
            keywords = session.query(Keyword).all()
            
            if keywords:
                tabs = st.tabs([kw.keyword for kw in keywords])
                
                for i, tab in enumerate(tabs):
                    with tab:
                        show_statistics(keywords[i].id)
            else:
                st.info("Nessuna campagna configurata")
            
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Errore nella dashboard: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")
    
elif menu == "Risultati":
    st.title("Risultati delle Ricerche")
    
    try:
        session = get_session()
        
        # Ottieni tutte le campagne per il filtro
        keywords = session.query(Keyword).all()
        keyword_options = [(0, "Tutte le campagne")] + [(kw.id, kw.keyword) for kw in keywords]
        
        # Filtro per campagna
        selected_keyword_id = st.selectbox(
            "Filtra per campagna:", 
            options=[id for id, _ in keyword_options],
            format_func=lambda x: next((name for id, name in keyword_options if id == x), "")
        )
        
        # Filtro per stato venduto
        sold_filter = st.radio("Stato:", ["Tutti", "Venduti", "Non venduti"], horizontal=True)
        
        # Ordinamento
        sort_by = st.selectbox("Ordina per:", ["Data (più recenti)", "Data (più vecchi)", "Prezzo (crescente)", "Prezzo (decrescente)"])
        
        # Costruisci la query in base ai filtri
        query = session.query(Risultato)
        
        # Applica filtro per keyword
        if selected_keyword_id != 0:
            query = query.filter(Risultato.keyword_id == selected_keyword_id)
        
        # Applica filtro per stato venduto
        if sold_filter == "Venduti":
            query = query.filter(Risultato.venduto == True)
        elif sold_filter == "Non venduti":
            query = query.filter(Risultato.venduto == False)
        
        # Applica ordinamento
        if sort_by == "Data (più recenti)":
            query = query.order_by(Risultato.created_at.desc())
        elif sort_by == "Data (più vecchi)":
            query = query.order_by(Risultato.created_at.asc())
        elif sort_by == "Prezzo (crescente)":
            query = query.order_by(Risultato.prezzo.asc())
        elif sort_by == "Prezzo (decrescente)":
            query = query.order_by(Risultato.prezzo.desc())
        
        # Paginazione
        page_size = 20
        total_results = query.count()
        total_pages = (total_results + page_size - 1) // page_size if total_results > 0 else 1
        
        # Controllo pagina
        page = st.number_input("Pagina", min_value=1, max_value=total_pages, value=1, step=1)
        
        # Calcola l'offset per la paginazione
        offset = (page - 1) * page_size
        
        # Ottieni i risultati per la pagina corrente
        results = query.offset(offset).limit(page_size).all()
        
        # Mostra i risultati
        if results:
            # Crea una tabella per visualizzare i risultati
            data = []
            for res in results:
                # Ottieni il nome della keyword
                keyword = session.query(Keyword).filter(Keyword.id == res.keyword_id).first()
                keyword_name = keyword.keyword if keyword else "N/A"
                
                # Converte l'URL in un link cliccabile
                link = f'<a href="{res.url}" target="_blank">Apri annuncio</a>'
                
                # Crea il record per la tabella
                data.append({
                    "ID": res.id,
                    "Campagna": keyword_name,
                    "Titolo": res.titolo,
                    "Prezzo": f"€{res.prezzo:.2f}",
                    "Luogo": res.luogo,
                    "Data": res.data_annuncio,
                    "Venduto": "✅" if res.venduto else "❌",
                    "Notificato": "✅" if res.notificato else "❌",
                    "Link": link,
                    "Data Creazione": res.created_at
                })
            
            # Converti in DataFrame
            df = pd.DataFrame(data)
            
            # Informazioni sulla paginazione
            st.info(f"Visualizzazione risultati {offset+1}-{min(offset+page_size, total_results)} di {total_results}")
            
            # Visualizza i dati con HTML per i link cliccabili
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # Pulsanti di navigazione per la paginazione
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if page > 1:
                    if st.button("⬅️ Precedente"):
                        st.experimental_set_query_params(page=page-1)
                        st.experimental_rerun()
            with col3:
                if page < total_pages:
                    if st.button("Successiva ➡️"):
                        st.experimental_set_query_params(page=page+1)
                        st.experimental_rerun()
            
        else:
            st.info("Nessun risultato trovato con i filtri selezionati.")
        
    except Exception as e:
        logger.error(f"Errore nella visualizzazione dei risultati: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")
    finally:
        session.close()

elif menu == "Gestione Campagne":
    st.title("Gestione Campagne")
    
    try:
        # Crea due colonne per la form e la lista
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Form per aggiungere una nuova keyword
            with st.form(key="add_keyword_form"):
                st.subheader("Aggiungi Nuova Campagna")
                
                # Campi per i parametri
                keyword = st.text_input("KEYWORD", placeholder="es PS4")
                limite_prezzo = st.number_input("LIMITE PREZZO", min_value=0, max_value=10000, value=200, step=50)
                applica_limite_prezzo = st.checkbox("APPLICA LIMITE PREZZO", value=False)
                limite_pagine = st.number_input("LIMITE PAGINE", min_value=1, max_value=10, value=2, step=1)
                intervallo_minuti = st.number_input("INTERVALLO MINUTI", min_value=1, max_value=60, value=2, step=1)
                
                # Pulsante di submit
                submit_button = st.form_submit_button(label="AGGIUNGI KEYWORD")
                
                if submit_button and keyword:
                    # Salva nel database
                    session = get_session()
                    try:
                        new_keyword = Keyword(
                            keyword=keyword,
                            limite_prezzo=limite_prezzo,
                            applica_limite_prezzo=applica_limite_prezzo,
                            limite_pagine=limite_pagine,
                            intervallo_minuti=intervallo_minuti,
                            attivo=True
                        )
                        session.add(new_keyword)
                        session.commit()
                        logger.info(f"Aggiunta nuova campagna: {keyword}")
                        
                        st.success(f"Campagna '{keyword}' aggiunta con successo!")
                        # Ricarica la pagina per aggiornare la tabella
                        time.sleep(1)
                        st.experimental_rerun()
                    finally:
                        session.close()
        
        with col2:
            # Visualizzazione della tabella delle keywords attive
            st.subheader("Lista Campagne")
            
            # Ottieni la lista delle keywords dal database
            session = get_session()
            try:
                keywords = session.query(Keyword).all()
                
                # Crea un dataframe per la visualizzazione
                if keywords:
                    data = []
                    for kw in keywords:
                        # Conta i risultati
                        count = session.query(Risultato).filter(Risultato.keyword_id == kw.id).count()
                        
                        # Stato formattato
                        status = "✅ Attivo" if kw.attivo else "⏸️ Pausa"
                        
                        # Indica se il limite di prezzo è applicato
                        prezzo_txt = f"{kw.limite_prezzo} {'✓' if kw.applica_limite_prezzo else '✗'}"
                        
                        data.append({
                            "ID": kw.id,
                            "Keyword": kw.keyword,
                            "Stato": status,
                            "Limite Prezzo": prezzo_txt,
                            "Max Pages": kw.limite_pagine,
                            "Intervallo": kw.intervallo_minuti,
                            "Risultati": count
                        })
                    
                    df = pd.DataFrame(data)
                    st.dataframe(df)
                    
                    # Seleziona una campagna per gestirla
                    st.subheader("Gestione Campagna")
                    selected_id = st.selectbox("Seleziona una campagna", 
                                            options=[kw.id for kw in keywords],
                                            format_func=lambda x: next((k.keyword for k in keywords if k.id == x), ""))
                    
                    if selected_id:
                        selected_kw = next((k for k in keywords if k.id == selected_id), None)
                        
                        if selected_kw:
                            # Modifica dei parametri della campagna
                            with st.expander("Modifica parametri"):
                                # Creo un form per la modifica
                                with st.form(key=f"edit_campaign_{selected_id}"):
                                    st.subheader(f"Modifica campagna: {selected_kw.keyword}")
                                    
                                    # Campi per i parametri
                                    edit_keyword = st.text_input("Keyword", value=selected_kw.keyword)
                                    edit_limite_prezzo = st.number_input("Limite Prezzo", 
                                                                min_value=0, 
                                                                max_value=10000, 
                                                                value=selected_kw.limite_prezzo, 
                                                                step=50)
                                    edit_applica_limite = st.checkbox("Applica Limite Prezzo", 
                                                               value=selected_kw.applica_limite_prezzo)
                                    edit_limite_pagine = st.number_input("Limite Pagine", 
                                                                 min_value=1, 
                                                                 max_value=10, 
                                                                 value=selected_kw.limite_pagine, 
                                                                 step=1)
                                    edit_intervallo = st.number_input("Intervallo Minuti", 
                                                             min_value=1, 
                                                             max_value=60, 
                                                             value=selected_kw.intervallo_minuti, 
                                                             step=1)
                                    
                                    # Pulsante di salvataggio
                                    save_button = st.form_submit_button("Salva Modifiche")
                                    
                                    if save_button:
                                        # Aggiorna i dati nel database
                                        selected_kw.keyword = edit_keyword
                                        selected_kw.limite_prezzo = edit_limite_prezzo
                                        selected_kw.applica_limite_prezzo = edit_applica_limite
                                        selected_kw.limite_pagine = edit_limite_pagine
                                        selected_kw.intervallo_minuti = edit_intervallo
                                        session.commit()
                                        
                                        logger.info(f"Modificata campagna ID {selected_id}: {edit_keyword}")
                                        st.success("Modifiche salvate con successo!")
                                        time.sleep(1)
                                        st.experimental_rerun()
                            
                            # Crea tre colonne per i pulsanti di azione
                            button_col1, button_col2, button_col3 = st.columns(3)
                            
                            with button_col1:
                                # Pulsante per avviare/mettere in pausa
                                if selected_kw.attivo:
                                    if st.button("Metti in Pausa"):
                                        result = scraper_adapter.stop_background_job(selected_id)
                                        logger.info(f"Messa in pausa la campagna: {selected_kw.keyword}")
                                        st.info(result["message"])
                                        time.sleep(1)
                                        st.experimental_rerun()
                                else:
                                    if st.button("Avvia"):
                                        selected_kw.attivo = True
                                        session.commit()
                                        result = scraper_adapter.start_background_job(selected_id)
                                        logger.info(f"Avviata la campagna: {selected_kw.keyword}")
                                        st.info(result["message"])
                                        time.sleep(1)
                                        st.experimental_rerun()
                            
                            with button_col2:
                                # Pulsante per eseguire una ricerca immediata
                                if st.button("Esegui Ricerca"):
                                    # Mostra un messaggio di caricamento
                                    with st.spinner("Ricerca in corso..."):
                                        result = scraper_adapter.search_for_keyword(selected_id)
                                        logger.info(f"Eseguita ricerca manuale per: {selected_kw.keyword}, risultati: {result.get('results_count', 0)}")
                                        
                                    # Mostra il risultato
                                    if result["status"] == "success":
                                        st.success(f"Ricerca completata: {result['message']}")
                                    else:
                                        st.error(f"Errore nella ricerca: {result['message']}")
                                        st.info("Controlla i log dello scraper per maggiori dettagli.")
                                
                                # Aggiungo un separatore
                                st.markdown("---")
                                
                                # Pulsante per cancellare la cache degli annunci già visti
                                if st.button("Cancella Cache", help="Cancella la cache degli annunci già visti per questa campagna"):
                                    # Prova a importare la classe SeenAds (se esiste)
                                    try:
                                        from database_schema import SeenAds
                                        
                                        # Elimina tutti i record per questa campagna
                                        deleted_count = session.query(SeenAds).filter(
                                            SeenAds.keyword_id == selected_id
                                        ).delete()
                                        
                                        # Commit delle modifiche
                                        session.commit()
                                        
                                        logger.info(f"Cancellati {deleted_count} elementi dalla cache per la campagna {selected_kw.keyword}")
                                        st.success(f"Cache cancellata: {deleted_count} annunci rimossi dalla memoria. La prossima ricerca mostrerà tutti gli annunci disponibili.")
                                    except ImportError:
                                        # Se non esiste la tabella SeenAds, cancella il file cache
                                        try:
                                            cache_file = os.path.join("data", "seen_items_cache.txt")
                                            
                                            with open(cache_file, "w") as f:
                                                f.write("")
                                            
                                            logger.info(f"Cache file cancellata per la campagna {selected_kw.keyword}")
                                            st.success("Cache file cancellata. La prossima ricerca mostrerà tutti gli annunci disponibili.")
                                        except Exception as e:
                                            logger.error(f"Errore nella cancellazione della cache file: {str(e)}")
                                            st.error(f"Errore nella cancellazione della cache: {str(e)}")
                            
                            with button_col3:
                                # Pulsante per eliminare la campagna
                                # Creo una conferma per l'eliminazione
                                confirm = st.checkbox("Conferma eliminazione", key=f"confirm_delete_{selected_id}", help="Seleziona questa casella per abilitare l'eliminazione")
                                
                                if confirm:
                                    # Mostro quanti risultati verranno eliminati
                                    risultati_count = session.query(Risultato).filter(Risultato.keyword_id == selected_id).count()
                                    st.warning(f"Verranno eliminati {risultati_count} risultati associati a questa campagna.")
                                    
                                    if st.button("Elimina Campagna", help="Elimina la campagna e tutti i suoi risultati"):
                                        # Ferma eventuali job in background
                                        scraper_adapter.stop_background_job(selected_id)
                                        
                                        # Elimina prima gli annunci visti associati
                                        seen_deleted = 0
                                        try:
                                            from database_schema import SeenAds
                                            seen_deleted = session.query(SeenAds).filter(SeenAds.keyword_id == selected_id).delete()
                                            logger.info(f"Eliminati {seen_deleted} annunci visti associati alla campagna ID {selected_id}")
                                        except Exception as e:
                                            logger.error(f"Errore durante l'eliminazione degli annunci visti: {str(e)}")
                                        
                                        # Elimina tutti i risultati associati
                                        results_deleted = session.query(Risultato).filter(Risultato.keyword_id == selected_id).delete()
                                        
                                        # Elimina le statistiche associate
                                        stats_deleted = session.query(Statistiche).filter(Statistiche.keyword_id == selected_id).delete()
                                        
                                        # Elimina la keyword dal database
                                        deleted_keyword = selected_kw.keyword
                                        session.delete(selected_kw)
                                        session.commit()
                                        
                                        logger.info(f"Eliminata la campagna: {deleted_keyword} con {results_deleted} risultati, {seen_deleted} annunci visti e {stats_deleted} statistiche")
                                        st.success(f"Campagna '{deleted_keyword}' eliminata con successo! Rimossi anche {results_deleted} risultati, {seen_deleted} annunci visti e {stats_deleted} statistiche.")
                                        time.sleep(1)
                                        st.experimental_rerun()
                                else:
                                    st.info("Per eliminare la campagna, seleziona prima la casella di conferma qui sopra.")
                else:
                    st.info("Nessuna campagna configurata. Aggiungi una nuova campagna di ricerca.")
            
            finally:
                session.close()
    except Exception as e:
        logger.error(f"Errore nella gestione campagne: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")

elif menu == "Log Scraper":
    st.title("Log del Core Scraper")
    
    try:
        st.write("Questa pagina mostra i log interni del core dello scraper, utili per diagnosticare problemi di importazione o funzionamento.")
        
        # Visualizza i log dello scraper
        show_scraper_logs()
        
        # Verifica dello stato di importazione dello scraper
        st.subheader("Stato del Core Scraper")
        
        # Controlla se è stata usata la classe di fallback o quella reale
        if hasattr(scraper_adapter.scraper, "search_ads") and callable(scraper_adapter.scraper.search_ads):
            # Verifica se è la classe reale o quella di fallback
            if scraper_adapter.scraper.__class__.__name__ == "SubitoScraper":
                if hasattr(scraper_adapter.scraper, "BASE_URL"):
                    st.success("✅ Il core dello scraper è stato importato correttamente.")
                    
                    # Mostra le informazioni sul modulo importato
                    import inspect
                    try:
                        module_path = inspect.getmodule(scraper_adapter.scraper.__class__).__file__
                        st.info(f"Modulo importato da: {module_path}")
                    except:
                        st.info("Non è stato possibile determinare il percorso del modulo.")
                    
                    # Verifica delle configurazioni Telegram
                    token, chat_id = get_telegram_config()
                    if token and chat_id:
                        st.success("✅ Le credenziali Telegram sono configurate.")
                    else:
                        st.warning("⚠️ Le credenziali Telegram non sono configurate. Le notifiche non funzioneranno.")
                else:
                    st.warning("⚠️ Il core dello scraper sembra essere stato importato, ma potrebbero esserci problemi di compatibilità.")
        else:
            st.error("❌ Il core dello scraper non è stato importato correttamente. Viene utilizzata una versione di fallback che simula i risultati.")
            
            # Suggerimenti per la risoluzione dei problemi
            st.subheader("Suggerimenti per la risoluzione")
            st.markdown("""
            Se stai riscontrando problemi con l'importazione dello scraper, prova a:
            
            1. **Verificare il percorso del file**: Assicurati che il file `scraper_test.py` sia presente nella directory `backend/`
            2. **Controllare le dipendenze**: Assicurati che tutte le dipendenze richieste siano installate
            3. **Riavviare l'applicazione**: Esegui nuovamente lo script `run.sh`
            4. **Controllare i log di sistema**: Controlla la sezione "Log Sistema" per errori più dettagliati
            """)
            
            # Mostra i percorsi di ricerca Python
            st.subheader("Percorsi di ricerca Python")
            st.code("\n".join(sys.path))
            
            # Verifica la presenza del file scraper_test.py
            backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
            scraper_file = os.path.join(backend_path, 'scraper_test.py')
            
            if os.path.exists(scraper_file):
                st.success(f"✅ Il file {scraper_file} esiste.")
            else:
                st.error(f"❌ Il file {scraper_file} non esiste.")
                
                # Cerca il file nel sistema
                st.subheader("Ricerca del file scraper_test.py")
                with st.spinner("Ricerca in corso..."):
                    # Cerca nella directory del progetto
                    project_dir = os.path.dirname(os.path.abspath(__file__))
                    found_files = []
                    
                    for root, dirs, files in os.walk(project_dir):
                        if 'scraper_test.py' in files:
                            found_files.append(os.path.join(root, 'scraper_test.py'))
                    
                    if found_files:
                        st.success(f"Trovati {len(found_files)} file 'scraper_test.py':")
                        for file_path in found_files:
                            st.code(file_path)
                    else:
                        st.error("Nessun file 'scraper_test.py' trovato nel progetto.")
            
            # Elenco dei file nella directory backend
            if os.path.exists(backend_path):
                st.subheader("Contenuto della directory backend")
                backend_files = os.listdir(backend_path)
                st.code("\n".join(backend_files))
            else:
                st.error(f"La directory {backend_path} non esiste.")
    
    except Exception as e:
        logger.error(f"Errore nella pagina Log Scraper: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")
    
elif menu == "Ricerche Programmate":
    st.title("Log delle Ricerche Programmate")
    
    try:
        # Ottieni i log dei cronjob
        cronjob_logs = scraper_adapter.get_cronjob_logs()
        
        if not cronjob_logs:
            st.info("Nessun log delle ricerche programmate disponibile.")
        else:
            # Crea un formato più leggibile
            st.subheader(f"Log delle Ricerche Programmate ({len(cronjob_logs)} eventi)")
            
            # Opzioni di filtro
            log_levels = ["Tutti", "ERROR", "WARNING", "INFO"]
            selected_level = st.selectbox("Filtra per livello", log_levels)
            
            # Filtro per campagna
            session = get_session()
            try:
                keywords = session.query(Keyword).all()
                keyword_options = [(0, "Tutte le campagne")] + [(kw.id, kw.keyword) for kw in keywords]
                
                selected_keyword_id = st.selectbox(
                    "Filtra per campagna:", 
                    options=[id for id, _ in keyword_options],
                    format_func=lambda x: next((name for id, name in keyword_options if id == x), ""),
                    key="cronjob_keyword_filter"
                )
            finally:
                session.close()
            
            # Filtra per parole chiave rilevanti che indicano ricerche programmate
            show_only_executions = st.checkbox("Mostra solo le esecuzioni programmate", value=True, 
                                              help="Mostra solo i messaggi relativi all'avvio e completamento delle ricerche programmate")
            
            # Filtra i log
            if selected_level != "Tutti":
                filtered_logs = [log for log in cronjob_logs if log["level"] == selected_level]
            else:
                filtered_logs = cronjob_logs
                
            # Applica filtro per keyword
            if selected_keyword_id != 0:
                filtered_logs = [log for log in filtered_logs if log.get("keyword_id") == selected_keyword_id]
            
            # Applica filtro per ricerche programmate
            if show_only_executions:
                execution_keywords = ["Esecuzione ricerca", "Avviato job", "Terminato job", "Prossima ricerca programmata"]
                filtered_logs = [log for log in filtered_logs if any(keyword in log["message"] for keyword in execution_keywords)]
            
            # Mostra numero di log per tipo
            error_count = len([log for log in filtered_logs if log["level"] == "ERROR"])
            warning_count = len([log for log in filtered_logs if log["level"] == "WARNING"])
            info_count = len([log for log in filtered_logs if log["level"] == "INFO"])
            
            counts_col1, counts_col2, counts_col3 = st.columns(3)
            counts_col1.metric("Errori", error_count, delta=None, delta_color="inverse")
            counts_col2.metric("Avvisi", warning_count, delta=None, delta_color="inverse")
            counts_col3.metric("Info", info_count, delta=None, delta_color="normal")
            
            # Crea una tabella con i log
            if filtered_logs:
                log_data = []
                for log in filtered_logs:
                    # Ottieni il nome della keyword
                    keyword_id = log.get("keyword_id")
                    keyword_name = next((name for id, name in keyword_options if id == keyword_id), "N/A")
                    
                    log_data.append({
                        "Timestamp": log["timestamp"],
                        "Livello": log["level"],
                        "Campagna": keyword_name,
                        "Messaggio": log["message"]
                    })
                
                df = pd.DataFrame(log_data)
                
                # Applica stili per evidenziare i livelli di log
                def highlight_level(val):
                    color = ""
                    if val == "ERROR":
                        color = "background-color: rgba(255, 0, 0, 0.2)"
                    elif val == "WARNING":
                        color = "background-color: rgba(255, 165, 0, 0.2)"
                    elif val == "INFO":
                        if any(keyword in val for keyword in ["Esecuzione ricerca", "Avviato job"]):
                            color = "background-color: rgba(0, 128, 0, 0.3)"
                        else:
                            color = "background-color: rgba(0, 128, 0, 0.1)"
                    return color
                
                # Converti messaggi specifici per maggiore chiarezza
                def format_message(row):
                    message = row["Messaggio"]
                    
                    # Ricerca iniziale
                    if "Esecuzione ricerca iniziale" in message:
                        return "🚀 Ricerca iniziale avviata"
                    
                    # Ricerca programmata
                    elif "Esecuzione ricerca programmata" in message:
                        return "⏰ Ricerca programmata avviata"
                    
                    # Prossima ricerca
                    elif "Prossima ricerca programmata" in message:
                        minutes = message.split("tra")[1].strip().split(" ")[0]
                        return f"⏳ Prossima ricerca tra {minutes} minuti"
                    
                    # Avvio job
                    elif "Avviato job in background" in message:
                        return "▶️ Avviato monitoraggio automatico"
                    
                    # Termine job
                    elif "Terminato job in background" in message:
                        return "⏹️ Terminato monitoraggio automatico"
                    
                    return message
                
                # Applica la formattazione dei messaggi
                df["Messaggio"] = df.apply(format_message, axis=1)
                
                # Applica stili per evidenziare i livelli di log
                styled_df = df.style.applymap(highlight_level, subset=["Livello"])
                st.dataframe(styled_df, height=400)
                
                # Pulsante per cancellare i log
                if st.button("Cancella Log delle Ricerche Programmate"):
                    scraper_adapter.cronjob_logs = []
                    st.success("Log cancellati con successo.")
                    st.experimental_rerun()
            else:
                st.info(f"Nessun log disponibile con i filtri selezionati.")
            
    except Exception as e:
        logger.error(f"Errore nella visualizzazione dei log delle ricerche programmate: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")

elif menu == "Impostazioni":
    st.title("Impostazioni")
    
    try:
        st.subheader("Configurazione Telegram")
        
        # Leggi le configurazioni correnti
        current_token, current_chat_id = get_telegram_config()
        
        # Form per la configurazione Telegram
        with st.form(key="telegram_config"):
            telegram_token = st.text_input("Token Bot Telegram", value=current_token, placeholder="Enter your Telegram bot token")
            telegram_chat_id = st.text_input("Chat ID Telegram", value=current_chat_id, placeholder="Enter your Telegram chat ID")
            
            submit_button = st.form_submit_button(label="Salva Configurazione")
            
            if submit_button:
                # Verifica che almeno uno dei due campi sia compilato
                if telegram_token or telegram_chat_id:
                    try:
                        # Crea o modifica il file .env nella directory principale
                        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
                        
                        # Se uno dei due campi è vuoto, usa il valore corrente se disponibile
                        if not telegram_token and current_token:
                            telegram_token = current_token
                        if not telegram_chat_id and current_chat_id:
                            telegram_chat_id = current_chat_id
                        
                        # Crea il contenuto del file .env
                        env_content = f"TELEGRAM_BOT_TOKEN={telegram_token}\nTELEGRAM_CHAT_ID={telegram_chat_id}\n"
                        
                        # Scrivi il file
                        with open(env_path, 'w') as f:
                            f.write(env_content)
                        
                        logger.info(f"Configurazione Telegram aggiornata - token: {telegram_token[:4]}***{telegram_token[-4:] if len(telegram_token) > 8 else ''}, chat_id: {telegram_chat_id}")
                        st.success("Configurazione Telegram salvata con successo!")
                        
                        # Pulsante per testare la configurazione
                        if st.button("Testa Configurazione"):
                            import requests
                            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                            data = {
                                "chat_id": telegram_chat_id,
                                "text": "✅ Test di configurazione SnipeDeal completato con successo!",
                                "parse_mode": "Markdown"
                            }
                            
                            try:
                                response = requests.post(url, data=data)
                                if response.status_code == 200:
                                    st.success("Messaggio di test inviato con successo!")
                                else:
                                    st.error(f"Errore nell'invio del messaggio: {response.text}")
                            except Exception as e:
                                st.error(f"Errore nell'invio del messaggio: {str(e)}")
                    except Exception as e:
                        logger.error(f"Errore durante il salvataggio della configurazione Telegram: {str(e)}")
                        st.error(f"Errore durante il salvataggio: {str(e)}")
                else:
                    st.warning("Compila almeno uno dei campi per aggiornare la configurazione.")
        
        # Mostra lo stato attuale delle configurazioni
        if current_token or current_chat_id:
            st.info("**Configurazione Telegram attuale:**")
            if current_token:
                masked_token = current_token[:4] + '*' * (len(current_token) - 8) + current_token[-4:] if len(current_token) > 8 else '****'
                st.write(f"Token: {masked_token}")
            if current_chat_id:
                st.write(f"Chat ID: {current_chat_id}")
        
        st.subheader("Manutenzione Database")
        
        # Pulsanti per le operazioni di manutenzione
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Esporta Database"):
                session = get_session()
                try:
                    # Esporta le keywords
                    keywords = session.query(Keyword).all()
                    keywords_data = []
                    
                    for kw in keywords:
                        keywords_data.append({
                            "id": kw.id,
                            "keyword": kw.keyword,
                            "limite_prezzo": kw.limite_prezzo,
                            "applica_limite_prezzo": kw.applica_limite_prezzo,
                            "limite_pagine": kw.limite_pagine,
                            "intervallo_minuti": kw.intervallo_minuti,
                            "attivo": kw.attivo,
                            "created_at": kw.created_at.isoformat() if kw.created_at else None,
                            "updated_at": kw.updated_at.isoformat() if kw.updated_at else None
                        })
                    
                    # Crea il dizionario di export
                    export_data = {
                        "keywords": keywords_data,
                        "export_date": datetime.datetime.now().isoformat()
                    }
                    
                    # Converti in JSON
                    json_data = json.dumps(export_data, indent=2)
                    
                    # Nome del file di backup
                    backup_filename = f"snipedeal_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    
                    # Crea un file di download
                    st.download_button(
                        label="Download Backup",
                        data=json_data,
                        file_name=backup_filename,
                        mime="application/json"
                    )
                    
                    logger.info(f"Esportato backup del database: {backup_filename}")
                finally:
                    session.close()
        
        with col2:
            if st.button("Pulisci Risultati Vecchi"):
                session = get_session()
                try:
                    # Elimina i risultati più vecchi di 30 giorni
                    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
                    num_deleted = session.query(Risultato).filter(Risultato.created_at < thirty_days_ago).delete()
                    session.commit()
                    
                    logger.info(f"Eliminati {num_deleted} risultati vecchi dal database")
                    st.success(f"Eliminati {num_deleted} risultati vecchi dal database.")
                finally:
                    session.close()
    except Exception as e:
        logger.error(f"Errore nelle impostazioni: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")

elif menu == "Log Sistema":
    st.title("Log di Sistema")
    
    try:
        # File di log
        log_file = "data/snipedeal.log"
        
        # Verifica se il file di log esiste
        if os.path.exists(log_file):
            # Leggi le ultime righe del file di log
            with open(log_file, 'r') as f:
                # Leggi tutte le righe e prendi le ultime 100
                lines = f.readlines()
                last_lines = lines[-100:] if len(lines) > 100 else lines
                
                # Visualizza il log con formattazione
                st.subheader("Ultimi eventi di log")
                
                # Crea un formato più leggibile
                formatted_log = ""
                for line in last_lines:
                    # Colora le righe in base al livello di log
                    if "ERROR" in line:
                        formatted_log += f"<span style='color:red'>{line}</span>\n"
                    elif "WARNING" in line:
                        formatted_log += f"<span style='color:orange'>{line}</span>\n"
                    elif "INFO" in line:
                        formatted_log += f"<span style='color:green'>{line}</span>\n"
                    else:
                        formatted_log += f"{line}\n"
                
                # Visualizza il log formattato
                st.markdown(f"<pre>{formatted_log}</pre>", unsafe_allow_html=True)
                
                # Pulsante per scaricare il file di log completo
                with open(log_file, 'r') as log_file_handle:
                    st.download_button(
                        label="Scarica File di Log Completo",
                        data=log_file_handle,
                        file_name="snipedeal_log.txt",
                        mime="text/plain"
                    )
        else:
            st.info("Nessun file di log trovato. Il file verrà creato automaticamente quando si verificheranno eventi da registrare.")
            
        # Pulsante per cancellare i log
        if st.button("Cancella Log"):
            try:
                # Crea un backup del log corrente
                if os.path.exists(log_file):
                    backup_dir = "data/log_backups"
                    os.makedirs(backup_dir, exist_ok=True)
                    backup_file = f"{backup_dir}/snipedeal_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(log_file, 'r') as src, open(backup_file, 'w') as dst:
                        dst.write(src.read())
                    
                    # Cancella il file di log
                    with open(log_file, 'w') as f:
                        f.write("")
                    
                    logger.info("File di log cancellato e salvato come backup")
                    st.success("File di log cancellato con successo. Un backup è stato salvato.")
                else:
                    st.info("Nessun file di log da cancellare.")
            except Exception as e:
                logger.error(f"Errore durante la cancellazione del log: {str(e)}")
                st.error(f"Si è verificato un errore durante la cancellazione del log: {str(e)}")
                
        # Mostra i backup disponibili
        backup_dir = "data/log_backups"
        if os.path.exists(backup_dir):
            backup_files = sorted(glob.glob(f"{backup_dir}/snipedeal_log_*.txt"), reverse=True)
            if backup_files:
                st.subheader("Backup dei Log Disponibili")
                for bf in backup_files:
                    file_name = os.path.basename(bf)
                    file_size = os.path.getsize(bf) / 1024  # KB
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"{file_name} ({file_size:.1f} KB)")
                    with open(bf, 'r') as f:
                        col2.download_button(
                            label="Scarica",
                            data=f,
                            file_name=file_name,
                            mime="text/plain",
                            key=f"download_{file_name}"
                        )
    except Exception as e:
        st.error(f"Si è verificato un errore nella pagina di log: {str(e)}")

elif menu == "Seen Ads":
    st.title("Annunci Già Visti (Seen Ads)")
    
    try:
        # Importa la classe SeenAds
        from database_schema import SeenAds
        
        session = get_session()
        try:
            # Ottieni tutte le campagne per il filtro
            keywords = session.query(Keyword).all()
            keyword_options = [(0, "Tutte le campagne")] + [(kw.id, kw.keyword) for kw in keywords]
            
            # Filtro per campagna
            selected_keyword_id = st.selectbox(
                "Filtra per campagna:", 
                options=[id for id, _ in keyword_options],
                format_func=lambda x: next((name for id, name in keyword_options if id == x), ""),
                key="seen_ads_keyword_filter"
            )
            
            # Costruisci la query in base ai filtri
            query = session.query(SeenAds)
            
            # Applica filtro per keyword
            if selected_keyword_id != 0:
                query = query.filter(SeenAds.keyword_id == selected_keyword_id)
            
            # Ordinamento per data (più recenti prima)
            query = query.order_by(SeenAds.date_seen.desc())
            
            # Conta il totale
            total_seen_ads = query.count()
            
            # Mostra statistiche
            st.subheader("Statistiche")
            
            # Conta per campagna
            if selected_keyword_id == 0:
                seen_by_campaign = session.query(
                    Keyword.keyword, 
                    Keyword.id,
                    func.count(SeenAds.id).label('count')
                ).join(
                    SeenAds, 
                    Keyword.id == SeenAds.keyword_id
                ).group_by(
                    Keyword.id
                ).all()
                
                # Crea dataframe per la visualizzazione
                if seen_by_campaign:
                    campaign_data = []
                    for name, id, count in seen_by_campaign:
                        campaign_data.append({
                            "Campagna": name,
                            "ID Campagna": id,
                            "Numero Annunci Visti": count
                        })
                    
                    st.write("Annunci visti per campagna:")
                    st.dataframe(pd.DataFrame(campaign_data))
            
            # Mostra il totale
            st.info(f"Totale annunci visti: {total_seen_ads}")
            
            # Pulsante per eliminare tutti gli annunci visti
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Cancella Tutti", help="Elimina tutti gli annunci visti"):
                    if selected_keyword_id != 0:
                        # Elimina solo per la campagna selezionata
                        deleted = session.query(SeenAds).filter(
                            SeenAds.keyword_id == selected_keyword_id
                        ).delete()
                        
                        keyword_name = next((name for id, name in keyword_options if id == selected_keyword_id), "")
                        success_msg = f"Eliminati {deleted} annunci visti per la campagna: {keyword_name}"
                    else:
                        # Elimina tutti
                        deleted = session.query(SeenAds).delete()
                        success_msg = f"Eliminati {deleted} annunci visti da tutte le campagne"
                    
                    session.commit()
                    st.success(success_msg)
                    time.sleep(1)
                    st.experimental_rerun()
            
            with col2:
                if st.button("Aggiorna", help="Aggiorna la visualizzazione"):
                    st.experimental_rerun()
            
            # Paginazione
            page_size = 50
            total_pages = (total_seen_ads + page_size - 1) // page_size if total_seen_ads > 0 else 1
            
            # Controllo pagina
            page = st.number_input("Pagina", min_value=1, max_value=total_pages, value=1, step=1)
            
            # Calcola l'offset per la paginazione
            offset = (page - 1) * page_size
            
            # Ottieni i risultati per la pagina corrente
            seen_ads = query.offset(offset).limit(page_size).all()
            
            # Mostra i risultati
            if seen_ads:
                # Crea una tabella per visualizzare i risultati
                data = []
                for seen in seen_ads:
                    # Ottieni il nome della keyword
                    keyword = session.query(Keyword).filter(Keyword.id == seen.keyword_id).first()
                    keyword_name = keyword.keyword if keyword else "N/A"
                    
                    # Formatta la data
                    date_str = seen.date_seen.strftime("%d/%m/%Y %H:%M:%S") if seen.date_seen else "N/A"
                    
                    # Crea il record per la tabella
                    data.append({
                        "ID": seen.id,
                        "Campagna": keyword_name,
                        "Item ID": seen.item_id,
                        "Data": date_str
                    })
                
                # Converti in DataFrame
                df = pd.DataFrame(data)
                
                # Informazioni sulla paginazione
                st.info(f"Visualizzazione annunci {offset+1}-{min(offset+page_size, total_seen_ads)} di {total_seen_ads}")
                
                # Visualizza i dati
                st.dataframe(df)
                
                # Pulsanti di navigazione per la paginazione
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    if page > 1:
                        if st.button("⬅️ Precedente"):
                            st.experimental_rerun()
                with col3:
                    if page < total_pages:
                        if st.button("Successiva ➡️"):
                            st.experimental_rerun()
            else:
                st.info("Nessun annuncio visto trovato con i filtri selezionati.")
        
        except Exception as e:
            logger.error(f"Errore nella visualizzazione degli annunci visti: {str(e)}")
            st.error(f"Si è verificato un errore: {str(e)}")
        finally:
            session.close()
    except ImportError:
        st.error("Impossibile importare la classe SeenAds. Assicurati che il database_schema.py contenga questa classe.")
        st.info("Se hai appena aggiunto la classe SeenAds al database, potrebbe essere necessario riavviare l'applicazione.")
    except Exception as e:
        logger.error(f"Errore nella pagina Seen Ads: {str(e)}")
        st.error(f"Si è verificato un errore: {str(e)}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("© 2023 SnipeDeal")
st.sidebar.markdown("Versione 1.0") 