import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime

# Creare una directory data se non esiste
os.makedirs('data', exist_ok=True)

# Configurazione del database
DATABASE_URL = "sqlite:///data/snipedeal.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Keyword(Base):
    """Modello per le campagne di ricerca (keywords)"""
    __tablename__ = "keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, nullable=False)
    limite_prezzo = Column(Integer, default=0)
    applica_limite_prezzo = Column(Boolean, default=False)
    limite_pagine = Column(Integer, default=1)
    intervallo_minuti = Column(Integer, default=2)
    attivo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    risultati = relationship("Risultato", back_populates="keyword", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Keyword {self.keyword}>"

class Risultato(Base):
    """Modello per i risultati degli annunci trovati"""
    __tablename__ = "risultati"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"))
    titolo = Column(String)
    prezzo = Column(Float)
    url = Column(String)
    data_annuncio = Column(String)
    luogo = Column(String)
    venduto = Column(Boolean, default=False)
    notificato = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    keyword = relationship("Keyword", back_populates="risultati")
    
    def __repr__(self):
        return f"<Risultato {self.titolo}>"

class Statistiche(Base):
    """Modello per le statistiche aggregate delle campagne"""
    __tablename__ = "statistiche"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"))
    prezzo_medio = Column(Float)
    prezzo_mediano = Column(Float)
    prezzo_minimo = Column(Float)
    prezzo_massimo = Column(Float)
    numero_annunci = Column(Integer)
    annunci_venduti = Column(Integer)
    sell_through_rate = Column(Float)  # Percentuale di annunci venduti
    data = Column(DateTime, default=datetime.datetime.utcnow)
    
    keyword = relationship("Keyword")

class SeenAds(Base):
    __tablename__ = "seen_ads"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    item_id = Column(String, nullable=False)
    date_seen = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationship con Keyword
    keyword = relationship("Keyword", backref="seen_ads")

# Creazione delle tabelle nel database
def init_db():
    Base.metadata.create_all(bind=engine)

# Funzione per ottenere una sessione del database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Database inizializzato con successo.") 