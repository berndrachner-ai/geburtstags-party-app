# -*- coding: utf-8 -*-
"""
Created on Fri Dec  5 21:37:05 2025

@author: bernd
"""
import streamlit as st
import pandas as pd
import os
import time
from collections import Counter
import json

# Versuche Bibliotheken zu laden
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# --- KONFIGURATION ---
APP_TITLE = "🎂 Der Große Geburtstags-O-Mat"
CSV_FILE = "geburtstags_daten.csv"
ADMIN_PASSWORD = "party"

# --- LAYOUT SETUP ---
st.set_page_config(page_title="Geburtstags-O-Mat", page_icon="🎂", layout="centered")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    .big-header { font-size: 2.5rem !important; color: #FF4B4B; text-align: center; }
    /* Verstecke Streamlit Menü für cleanen Look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- DATENBANK MANAGEMENT (FIRESTORE) ---

@st.cache_resource
def get_db():
    """Verbindet sich mit Firestore und gibt Fehlermeldungen aus."""
    if not FIREBASE_AVAILABLE:
        return None
    
    try:
        # Prüfen, ob wir schon verbunden sind
        if not firebase_admin._apps:
            if "textkey" not in st.secrets:
                return None
                
            key_content = st.secrets["textkey"]
            key_dict = None

            # JSON Parsing Logik (String oder Dict)
            if isinstance(key_content, str):
                try:
                    key_dict = json.loads(key_content, strict=False)
                except json.JSONDecodeError:
                    return None
            elif isinstance(key_content, dict) or hasattr(key_content, "type"):
                key_dict = dict(key_content)
            
            if key_dict:
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)
                
        return firestore.client()

    except Exception:
        return None

def save_vote_to_db(name, properties, wishes, insider):
    db = get_db()
    data = {
        "name": name,
        "properties": properties,
        "wishes": wishes,
        "insider": insider,
        "timestamp": firestore.SERVER_TIMESTAMP if db else time.time()
    }
    
    if db:
        try:
            db.collection("votes").add(data)
            return True
        except Exception:
            return False
    else:
        if 'local_votes' not in st.session_state:
            st.session_state['local_votes'] = []
        st.session_state['local_votes'].append(data)
        return False

def get_all_votes_from_db():
    db = get_db()
    all_props = []
    all_wishes = []
    all_insider = []
    raw_data = [] 
    
    if db:
        try:
            docs = db.collection("votes").stream()
            for doc in docs:
                d = doc.to_dict()
                raw_data.append(d)
                all_props.extend(d.get("properties", []))
                all_wishes.extend(d.get("wishes", []))
                if d.get("insider"):
                    all_insider.append(d.get("insider"))
        except Exception:
            pass
    else:
        if 'local_votes' in st.session_state:
            for d in st.session_state['local_votes']:
                raw_data.append(d)
                all_props.extend(d.get("properties", []))
                all_wishes.extend(d.get("wishes", []))
                if d.get("insider"):
                    all_insider.append(d.get("insider"))
                    
    return all_props, all_wishes, all_insider, raw_data

# --- FUNKTIONEN ---

@st.cache_data
def load_data():
    """Lädt die Auswahl-Optionen (CSV)."""
    if os.path.exists(CSV_FILE):
        try:
            return pd.read_csv(CSV_FILE, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                return pd.read_csv(CSV_FILE, encoding='latin1', sep=None, engine='python')
            except Exception:
                return pd.DataFrame()
    return pd.DataFrame({'Typ': [], 'Kategorie': [], 'Text': []})

def check_password():
    def password_entered():
        if st.session_state["password_input"] == ADMIN_PASSWORD:
            st.session_state["is_admin_logged_in"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["is_admin_logged_in"] = False
            st.error("😕 Falsches Passwort")

    if "is_admin_logged_in" not in st.session_state or not st.session_state["is_admin_logged_in"]:
        st.markdown("### 🔒 Geschützter Bereich")
        st.text_input("Admin-Passwort:", type="password", on_change=password_entered, key="password_input")
        return False
    return True

def generate_poem_with_openai(api_key, prompt):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Du bist ein herzlicher Dichter."}, {"role": "user", "content": prompt}],
        temperature=0.8
    )
    return response.choices[0].message.content

# --- HAUPTPROGRAMM ---

def main():
    df = load_data()
    db = get_db()
    
    st.sidebar.title("Navigation")
    nav = st.sidebar.radio("Gehe zu:", ["🎉 Für Gäste", "🔐 Host / Admin"])

    # --- ANZEIGELOGIK ---

    if nav == "🎉 Für Gäste":
        # Gäste sehen keine Diagnose, nur die App
        render_guest_view(df, db_connected=(db is not None))
    
    else:
        # --- NUR ADMIN SIEHT DIAGNOSE ---
        st.sidebar.divider()
        st.sidebar.header("System-Status")
        if db:
            st.sidebar.success("✅ Datenbank Verbunden")
        else:
            st.sidebar.error("❌ Keine Datenbank")
            if os.path.exists(".streamlit/secrets.toml"):
                 st.sidebar.info("Lokal (secrets.toml)")
            else:
                 st.sidebar.info("Cloud Modus (Secrets prüfen!)")
        
        # --- ADMIN LOGIN & VIEW ---
        if check_password():
            if st.sidebar.button("Log out"):
                st.session_state["is_admin_logged_in"] = False
                st.rerun()
            render_host_view()

def render_guest_view(df, db_connected):
    st.markdown(f"<h1 class='big-header'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    
    # Dezenter Hinweis für Gäste, falls Cloud ausfällt (wichtig für UX)
    if not db_connected:
        st.warning("⚠️ Hinweis: Offline-Modus. Bitte Seite nicht neu laden.")

    with st.form("guest_form", clear_on_submit=True):
        st.write("Dein Name (Optional):")
        name = st.text_input("Name")
        
        st.subheader("1. Eigenschaften")
        eigenschaften_df = df[df['Typ'] == 'Eigenschaft']
        selected_eigenschaften = []
        for cat in eigenschaften_df['Kategorie'].unique():
            items = eigenschaften_df[eigenschaften_df['Kategorie'] == cat]['Text'].tolist()
            with st.expander(cat):
                sel = st.multiselect(f"Wähle aus {cat}", items)
                selected_eigenschaften.extend(sel)

        st.subheader("2. Wünsche")
        wuensche_df = df[df['Typ'] == 'Wunsch']
        selected_wuensche = []
        for cat in wuensche_df['Kategorie'].unique():
            items = wuensche_df[wuensche_df['Kategorie'] == cat]['Text'].tolist()
            with st.expander(cat):
                sel = st.multiselect(f"Wähle aus {cat}", items)
                selected_wuensche.extend(sel)
            
        insider = st.text_input("3. Ein Insider / Hobby:")
        submitted = st.form_submit_button("Absenden 🚀")
        
        if submitted:
            if not selected_eigenschaften and not selected_wuensche:
                st.error("Bitte wähle etwas aus.")
            else:
                saved = save_vote_to_db(name, selected_eigenschaften, selected_wuensche, insider)
                if saved:
                    st.success("Gespeichert! Vielen Dank ☁️")
                    st.balloons()
                else:
                    st.warning("Lokal gespeichert.")
                time.sleep(2)
                st.rerun()

def render_host_view():
    st.title("🔐 Admin Dashboard")
    
    props, wishes, insiders, raw_data = get_all_votes_from_db()
    count = len(raw_data)
    st.metric("Eingegangene Stimmzettel", count)

    tab1, tab2, tab3 = st.tabs(["Statistik", "KI Generator", "🕵️ Debug"])
    
    with tab1:
        c1, c2 = st.columns(2)
        top_props = []
        top_wishes = []
        if props:
            c = Counter(props)
            top_props = [k for k, v in c.most_common(5)]
            c1.subheader("Top Eigenschaften")
            c1.bar_chart(pd.DataFrame.from_dict(c, orient='index', columns=['Anzahl']))
        if wishes:
            c = Counter(wishes)
            top_wishes = [k for k, v in c.most_common(5)]
            c2.subheader("Top Wünsche")
            c2.bar_chart(pd.DataFrame.from_dict(c, orient='index', columns=['Anzahl']))
        with st.expander("Insider Infos"):
            st.write(insiders)

    with tab2:
        name = st.text_input("Name", "Das Geburtstagskind")
        alter = st.number_input("Alter", 1, 120, 40)
        insider_text = ""
        if insiders:
            import random
            s = random.sample(insiders, min(3, len(insiders)))
            insider_text = f"Details: {', '.join(s)}."

        prompt = f"Gedicht für {name} ({alter}). Eigenschaften: {', '.join(top_props)}. Wünsche: {', '.join(top_wishes)}. {insider_text}. Reimschema AABB."
        st.text_area("Prompt:", prompt)

        if "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        else:
            api_key = st.text_input("OpenAI Key", type="password")
            
        if st.button("Generieren"):
            if api_key and OPENAI_AVAILABLE:
                with st.spinner("Dichte..."):
                    res = generate_poem_with_openai(api_key, prompt)
                st.markdown(f"### Gedicht für {name}")
                st.write(res)
            else:
                st.error("Key fehlt oder OpenAI Modul nicht da.")
    
    with tab3:
        st.info("Datenbank-Inhalt (Live):")
        st.write(raw_data)

if __name__ == "__main__":
    main()