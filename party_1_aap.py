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

# Versuche OpenAI zu importieren
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# --- KONFIGURATION ---
APP_TITLE = "🎂 Der Große Geburtstags-O-Mat"
CSV_FILE = "geburtstags_daten.csv"

# HIER DAS PASSWORT FESTLEGEN
# (Noch sicherer wäre es über st.secrets, aber so ist es für den Anfang am einfachsten)
ADMIN_PASSWORD = "party" 

# --- LAYOUT SETUP ---
st.set_page_config(page_title="Geburtstags-O-Mat", page_icon="🎂", layout="centered")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
    }
    .big-header {
        font-size: 2.5rem !important;
        color: #FF4B4B;
        text-align: center;
    }
    /* Verstecke das Standard-Menü oben rechts für saubereren Look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- FUNKTIONEN ---

@st.cache_data
def load_data():
    """Lädt die Daten robust."""
    if os.path.exists(CSV_FILE):
        try:
            return pd.read_csv(CSV_FILE, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                return pd.read_csv(CSV_FILE, encoding='latin1', sep=None, engine='python')
            except Exception as e:
                st.error(f"Fehler: {e}")
                return pd.DataFrame()
    else:
        # Fallback
        data = {
            'Typ': ['Eigenschaft']*3 + ['Wunsch']*3,
            'Kategorie': ['Allgemein']*6,
            'Text': ['Herzlich', 'Klug', 'Lustig', 'Gesundheit', 'Geld', 'Liebe']
        }
        return pd.DataFrame(data)

def init_session_state():
    if 'votes_eigenschaften' not in st.session_state:
        st.session_state['votes_eigenschaften'] = []
    if 'votes_wuensche' not in st.session_state:
        st.session_state['votes_wuensche'] = []
    if 'insider_infos' not in st.session_state:
        st.session_state['insider_infos'] = []
    # Status für Admin-Login merken
    if 'is_admin_logged_in' not in st.session_state:
        st.session_state['is_admin_logged_in'] = False

def check_password():
    """Prüft das Passwort und setzt den Login-Status."""
    def password_entered():
        if st.session_state["password_input"] == ADMIN_PASSWORD:
            st.session_state["is_admin_logged_in"] = True
            del st.session_state["password_input"]  # Passwort aus Speicher löschen
        else:
            st.session_state["is_admin_logged_in"] = False
            st.error("😕 Falsches Passwort")

    if not st.session_state["is_admin_logged_in"]:
        st.markdown("### 🔒 Geschützter Bereich")
        st.text_input(
            "Bitte Admin-Passwort eingeben:", 
            type="password", 
            on_change=password_entered, 
            key="password_input"
        )
        return False
    else:
        return True

def generate_poem_with_openai(api_key, prompt):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Du bist ein herzlicher, kreativer Dichter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8
    )
    return response.choices[0].message.content

# --- HAUPTPROGRAMM ---

def main():
    init_session_state()
    df = load_data()
    
    # Navigation in der Sidebar
    st.sidebar.title("Navigation")
    
    # Icons machen es hübscher
    nav_selection = st.sidebar.radio(
        "Gehe zu:", 
        ["🎉 Für Gäste (Eingabe)", "🔐 Für Host (Admin)"]
    )

    if nav_selection == "🎉 Für Gäste (Eingabe)":
        render_guest_view(df)
    else:
        # HIER IST DIE SICHERHEITSSCHLEUSE
        if check_password():
            # Button zum Ausloggen
            if st.sidebar.button("Log out"):
                st.session_state["is_admin_logged_in"] = False
                st.rerun()
            render_host_view()

# --- GAST ANSICHT ---

def render_guest_view(df):
    st.markdown(f"<h1 class='big-header'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.info("👋 Schön, dass du da bist! Hilf uns, das perfekte Gedicht zu erstellen.")
    
    eigenschaften_df = df[df['Typ'] == 'Eigenschaft']
    wuensche_df = df[df['Typ'] == 'Wunsch']

    with st.form("guest_form", clear_on_submit=True):
        
        st.subheader("1. Charakter & Art")
        st.caption("Wähle Eigenschaften, die passen (max. 3 empfohlen):")
        
        selected_eigenschaften = []
        # Gruppieren nach Kategorie
        for cat in eigenschaften_df['Kategorie'].unique():
            items = eigenschaften_df[eigenschaften_df['Kategorie'] == cat]['Text'].tolist()
            with st.expander(f"▼ {cat}", expanded=False):
                sel = st.multiselect(f"Auswahl ({cat}):", items)
                selected_eigenschaften.extend(sel)

        st.divider()

        st.subheader("2. Wünsche für die Zukunft")
        st.caption("Was soll das neue Lebensjahr bringen?")
        selected_wuensche = []
        for cat in wuensche_df['Kategorie'].unique():
            items = wuensche_df[wuensche_df['Kategorie'] == cat]['Text'].tolist()
            with st.expander(f"▼ {cat}", expanded=False):
                sel = st.multiselect(f"Auswahl ({cat}):", items)
                selected_wuensche.extend(sel)
            
        st.divider()
        
        insider = st.text_input("3. Optional: Ein Insider / Hobby / Besonderheit:")

        submitted = st.form_submit_button("Absenden 🚀")
        
        if submitted:
            if not selected_eigenschaften and not selected_wuensche:
                st.error("Bitte wähle zumindest eine Eigenschaft oder einen Wunsch aus.")
            else:
                st.session_state['votes_eigenschaften'].extend(selected_eigenschaften)
                st.session_state['votes_wuensche'].extend(selected_wuensche)
                if insider:
                    st.session_state['insider_infos'].append(insider)
                
                st.balloons()
                st.success("Vielen Dank! Deine Eingabe ist gespeichert.")
                time.sleep(2)
                st.rerun()

# --- HOST ANSICHT ---

def render_host_view():
    st.title("🔐 Admin Dashboard")
    st.success("Erfolgreich eingeloggt.")
    
    # Metriken
    count_votes = max(1, len(st.session_state['votes_eigenschaften']) // 3)
    st.metric("Geschätzte Teilnehmer bisher", count_votes)

    tab1, tab2 = st.tabs(["📊 Statistik", "🤖 KI Generator"])

    with tab1:
        col1, col2 = st.columns(2)
        top_eigenschaften = []
        top_wuensche = []

        with col1:
            st.subheader("Top Eigenschaften")
            if st.session_state['votes_eigenschaften']:
                c = Counter(st.session_state['votes_eigenschaften'])
                top_eigenschaften = [k for k, v in c.most_common(5)]
                # Daten für Chart aufbereiten
                chart_data = pd.DataFrame.from_dict(c, orient='index', columns=['Stimmen'])
                st.bar_chart(chart_data)
            else:
                st.info("Warte auf Daten...")

        with col2:
            st.subheader("Top Wünsche")
            if st.session_state['votes_wuensche']:
                c = Counter(st.session_state['votes_wuensche'])
                top_wuensche = [k for k, v in c.most_common(5)]
                chart_data = pd.DataFrame.from_dict(c, orient='index', columns=['Stimmen'])
                st.bar_chart(chart_data)
            else:
                st.info("Warte auf Daten...")

        with st.expander("📝 Gesammelte Insider-Infos ansehen"):
            if st.session_state['insider_infos']:
                for item in st.session_state['insider_infos']:
                    st.text(f"- {item}")
            else:
                st.write("Noch keine Insider-Infos.")

    with tab2:
        st.write("Hier generierst du das finale Gedicht.")
        
        # Eingabefelder für den Prompt
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", "Das Geburtstagskind")
        alter = c2.number_input("Alter", 1, 120, 40)
        
        insider_text = ""
        if st.session_state['insider_infos']:
            import random
            sample = random.sample(st.session_state['insider_infos'], min(3, len(st.session_state['insider_infos'])))
            insider_text = f"Erwähne am Rande auch kurz diese Details: {', '.join(sample)}."

        prompt = f"""
Verfasse ein Geburtstagsgedicht für {name} ({alter} Jahre).
Stil: Lustig, herzlich, Reime (AABB oder Kreuzreim).
WICHTIG - Baue diese Eigenschaften ein, die von Gästen gewählt wurden: {', '.join(top_eigenschaften)}.
Wünsche der Gäste: {', '.join(top_wuensche)}.
{insider_text}
Sprich das Geburtstagskind direkt mit "Du" an.
        """
        
        st.text_area("Der generierte Prompt:", value=prompt, height=150)

        # API Key Handling (Priorität: Secrets > Eingabefeld)
        api_key = None
        if "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
            st.success("✅ API Key aus Secrets geladen.")
        else:
            api_key = st.text_input("OpenAI API Key (sk-...)", type="password")
        
        if st.button("✨ Gedicht generieren", type="primary"):
            if not api_key:
                st.warning("Kein API Key gefunden.")
            elif not OPENAI_AVAILABLE:
                st.error("OpenAI Modul fehlt.")
            else:
                with st.spinner("Die KI dichtet..."):
                    try:
                        gedicht = generate_poem_with_openai(api_key, prompt)
                        st.balloons()
                        st.markdown(f"### 📜 Gedicht für {name}")
                        st.write(gedicht)
                    except Exception as e:
                        st.error(f"Fehler: {e}")

if __name__ == "__main__":
    main()