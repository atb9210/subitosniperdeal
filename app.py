import streamlit as st
import pandas as pd
import time
import sqlite3
import os
import sys
import threading
from contextlib import contextmanager
import datetime

# Aggiungi la directory backend al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database_schema import init_db, Keyword, Risultato, Statistiche, SessionLocal

# Inizializza il database
init_db()

# Configura la pagina Streamlit
st.set_page_config(
    page_title="SnipeDeal - Monitoraggio Annunci",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Titolo principale
st.title("SNIPE DEAL")
st.subheader("Monitoraggio Annunci su Subito.it")

# Funzione per connessione al database
@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Crea due colonne per la form
col1, col2 = st.columns(2)

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
            with get_session() as session:
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
            
            st.success(f"Campagna '{keyword}' aggiunta con successo!")
            # Ricarica la pagina per aggiornare la tabella
            time.sleep(1)
            st.experimental_rerun()

# Funzione per eseguire lo scraper
def run_scraper_for_keyword(keyword_id):
    # Questa funzione verrà implementata per integrare lo scraper esistente
    # per ora faccio solo una simulazione
    with get_session() as session:
        keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
        if keyword and keyword.attivo:
            # Simulare l'aggiunta di risultati
            now = datetime.datetime.now()
            # Aggiungi un risultato simulato
            new_result = Risultato(
                keyword_id=keyword_id,
                titolo=f"Test annuncio per {keyword.keyword}",
                prezzo=float(keyword.limite_prezzo - 50),
                url="https://www.subito.it/annuncio-test",
                data_annuncio=now.strftime("%Y-%m-%d"),
                luogo="Milano"
            )
            session.add(new_result)
            
            # Aggiorna le statistiche
            stats = session.query(Statistiche).filter(Statistiche.keyword_id == keyword_id).first()
            if not stats:
                stats = Statistiche(
                    keyword_id=keyword_id,
                    prezzo_medio=new_result.prezzo,
                    prezzo_mediano=new_result.prezzo,
                    prezzo_minimo=new_result.prezzo,
                    prezzo_massimo=new_result.prezzo,
                    numero_annunci=1,
                    annunci_venduti=0,
                    sell_through_rate=0.0
                )
                session.add(stats)
            else:
                stats.numero_annunci += 1
                
            session.commit()
    
    # Qui andrebbe integrato il codice dal backend/scraper_test.py
    # che esegue la ricerca su Subito.it con i parametri configurati

# Funzione per avviare o mettere in pausa una keyword
def toggle_keyword_status(keyword_id):
    with get_session() as session:
        keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
        if keyword:
            keyword.attivo = not keyword.attivo
            session.commit()

# Funzione per eliminare una keyword
def delete_keyword(keyword_id):
    with get_session() as session:
        keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
        if keyword:
            session.delete(keyword)
            session.commit()

# Visualizzazione della tabella delle keywords attive
st.subheader("Lista Keyword Attive")

# Ottieni la lista delle keywords dal database
with get_session() as session:
    keywords = session.query(Keyword).all()
    
    # Crea un dataframe per la visualizzazione
    if keywords:
        data = []
        for kw in keywords:
            # Conta i risultati
            count = session.query(Risultato).filter(Risultato.keyword_id == kw.id).count()
            
            # Stato formattato
            status = "Attivo" if kw.attivo else "Pausa"
            
            data.append({
                "ID": kw.id,
                "Keyword": kw.keyword,
                "Stato": status,
                "Limite Prezzo": kw.limite_prezzo,
                "Max Pages": kw.limite_pagine,
                "Intervallo": kw.intervallo_minuti,
                "Risultati": count
            })
        
        df = pd.DataFrame(data)
        
        # Visualizza la tabella con pulsanti per le azioni
        for i, row in df.iterrows():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 1, 1, 1, 1, 2, 2])
            
            with col1:
                st.write(row["Keyword"])
            with col2:
                st.write(row["Stato"])
            with col3:
                st.write(row["Limite Prezzo"])
            with col4:
                st.write(row["Max Pages"])
            with col5:
                st.write(row["Intervallo"])
            with col6:
                st.write(row["Risultati"])
            with col7:
                # Pulsante per avviare/mettere in pausa
                if row["Stato"] == "Attivo":
                    if st.button("Pausa", key=f"pause_{row['ID']}"):
                        toggle_keyword_status(row["ID"])
                        st.experimental_rerun()
                else:
                    if st.button("Avvia", key=f"start_{row['ID']}"):
                        toggle_keyword_status(row["ID"])
                        st.experimental_rerun()
            with col8:
                # Pulsante per eliminare
                if st.button("Elimina", key=f"delete_{row['ID']}"):
                    delete_keyword(row["ID"])
                    st.experimental_rerun()
        
        # Pulsante per avviare lo scraper per tutte le keywords attive
        if st.button("Avvia Scansione Per Tutte"):
            # Avvia thread separati per ogni keyword attiva
            active_keywords = [kw for kw in keywords if kw.attivo]
            for kw in active_keywords:
                thread = threading.Thread(target=run_scraper_for_keyword, args=(kw.id,))
                thread.start()
            
            st.success(f"Avviata scansione per {len(active_keywords)} keywords attive!")
    else:
        st.info("Nessuna keyword configurata. Aggiungi una nuova campagna di ricerca.")

# Sezione per visualizzare i risultati
st.subheader("Ultimi Risultati")

# Seleziona la keyword per cui visualizzare i risultati
with get_session() as session:
    keywords = session.query(Keyword).all()
    if keywords:
        keyword_options = [kw.keyword for kw in keywords]
        selected_keyword = st.selectbox("Seleziona Keyword", options=keyword_options)
        
        # Trova l'ID della keyword selezionata
        selected_id = next((kw.id for kw in keywords if kw.keyword == selected_keyword), None)
        
        if selected_id:
            # Ottieni i risultati per la keyword selezionata
            results = session.query(Risultato).filter(Risultato.keyword_id == selected_id).order_by(Risultato.created_at.desc()).limit(10).all()
            
            if results:
                result_data = []
                for res in results:
                    result_data.append({
                        "Titolo": res.titolo,
                        "Prezzo": f"€{res.prezzo:.2f}",
                        "Data": res.data_annuncio,
                        "Luogo": res.luogo,
                        "Venduto": "Sì" if res.venduto else "No",
                        "URL": res.url
                    })
                
                result_df = pd.DataFrame(result_data)
                st.dataframe(result_df)
                
                # Link per visualizzare tutti i risultati
                if st.button("Visualizza Tutti i Risultati"):
                    st.session_state.show_all_results = True
            else:
                st.info(f"Nessun risultato trovato per '{selected_keyword}'")
    else:
        st.info("Aggiungi una keyword per visualizzare i risultati.")

# Se richiesto, mostra tutti i risultati
if st.session_state.get("show_all_results", False):
    st.subheader("Tutti i Risultati")
    with get_session() as session:
        # Trova l'ID della keyword selezionata
        selected_id = next((kw.id for kw in keywords if kw.keyword == selected_keyword), None)
        
        if selected_id:
            # Ottieni tutti i risultati per la keyword selezionata
            all_results = session.query(Risultato).filter(Risultato.keyword_id == selected_id).order_by(Risultato.created_at.desc()).all()
            
            if all_results:
                all_result_data = []
                for res in all_results:
                    all_result_data.append({
                        "Titolo": res.titolo,
                        "Prezzo": f"€{res.prezzo:.2f}",
                        "Data": res.data_annuncio,
                        "Luogo": res.luogo,
                        "Venduto": "Sì" if res.venduto else "No",
                        "URL": res.url
                    })
                
                all_result_df = pd.DataFrame(all_result_data)
                st.dataframe(all_result_df)
                
                # Pulsante per nascondere
                if st.button("Nascondi"):
                    st.session_state.show_all_results = False
                    st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("SnipeDeal - Monitoraggio Annunci su Subito.it") 