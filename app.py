import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
import logging
import datetime
import time
import io
from fpdf import FPDF

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(message)s")
logger = logging.getLogger("PropData")

"""
PropData Estimator - Karachi Real Estate Valuation Engine
---------------------------------------------------------
Author: Muhammad Danish (Lead Data Strategist)
Company: CyberWeb Labs
Version: 11.0 (Enterprise Edition)
Created: November 2025

Description:
A parametric valuation model that estimates property prices in Karachi 
based on location tiers, plot size, construction quality, and market 
volatility factors. Integrated with PDF reporting and Geolocation mapping.
"""

MARKET_CLUSTERS = {
    "Elite / Premium": {
        "DHA Phase 8": 190000, "DHA Phase 6": 165000, "DHA Phase 5": 160000, "DHA Phase 2": 145000,
        "Clifton Block 2": 170000, "Clifton Block 5": 165000, "KDA Scheme 1": 150000, 
        "Navy Housing (Karsaz)": 155000, "Askari 4": 125000, "Askari 5": 120000,
        "PECHS Block 2": 130000, "PECHS Block 6": 140000
    },
    "Upper Mid-Range": {
        "Bahadurabad": 110000, "Mohammad Ali Society": 115000, "Al-Hilal Society": 105000,
        "Gulshan Block 13D": 95000, "Gulshan Block 10": 90000, "North Nazimabad (Hyderi)": 100000,
        "North Nazimabad Block H": 95000, "Garden West": 95000, "Federal B Area": 90000
    },
    "Mid-Range": {
        "Gulistan-e-Jauhar Blk 1": 80000, "Gulistan-e-Jauhar Blk 15": 75000, 
        "Scheme 33 (Saadi Town)": 65000, "Scheme 33 (Metrovil)": 60000,
        "Bahria Town (Precinct 1)": 110000, "Bahria Town (Precinct 10)": 85000,
        "Malir Cantt": 95000, "Bufferzone": 70000, "North Karachi": 60000
    },
    "Affordable": {
        "New Karachi": 45000, "Surjani Town": 35000, "Korangi Crossing": 55000,
        "Korangi Industrial": 60000, "Orangi Town": 30000, "Lyari": 35000, 
        "Taiser Town": 25000, "Baldia Town": 30000
    }
}
BASE_RATES = {loc: price for cluster in MARKET_CLUSTERS.values() for loc, price in cluster.items()}

AREA_COORDINATES = {
    "DHA Phase 8": [24.7933, 67.0654], "DHA Phase 6": [24.8066, 67.0555], "DHA Phase 5": [24.8150, 67.0450], "DHA Phase 2": [24.8300, 67.0700],
    "Clifton Block 2": [24.8214, 67.0312], "Clifton Block 5": [24.8250, 67.0350], "KDA Scheme 1": [24.8615, 67.0944], 
    "Navy Housing (Karsaz)": [24.8766, 67.0940], "Askari 4": [24.9150, 67.1250], "Askari 5": [24.9012, 67.1156],
    "PECHS Block 2": [24.8650, 67.0560], "PECHS Block 6": [24.8590, 67.0680],
    "Bahadurabad": [24.8825, 67.0694], "Mohammad Ali Society": [24.8760, 67.0850], "Al-Hilal Society": [24.8850, 67.0750],
    "Gulshan Block 13D": [24.9180, 67.0970], "Gulshan Block 10": [24.9300, 67.1050], 
    "North Nazimabad (Hyderi)": [24.9380, 67.0450], "North Nazimabad Block H": [24.9450, 67.0400],
    "Garden West": [24.8750, 67.0250], "Federal B Area": [24.9450, 67.0750],
    "Gulistan-e-Jauhar Blk 1": [24.9250, 67.1350], "Gulistan-e-Jauhar Blk 15": [24.9150, 67.1450],
    "Scheme 33 (Saadi Town)": [24.9850, 67.1650], "Scheme 33 (Metrovil)": [24.9750, 67.1150],
    "Bahria Town (Precinct 1)": [25.0400, 67.3000], "Bahria Town (Precinct 10)": [25.0500, 67.3200],
    "Malir Cantt": [24.9500, 67.1900], "Bufferzone": [24.9650, 67.0650], "North Karachi": [24.9850, 67.0550],
    "New Karachi": [24.9950, 67.0650], "Surjani Town": [25.0250, 67.0550], "Korangi Crossing": [24.8350, 67.1350],
    "Korangi Industrial": [24.8250, 67.1250], "Orangi Town": [24.9450, 66.9950], "Lyari": [24.8650, 66.9950],
    "Taiser Town": [25.0550, 67.0850], "Baldia Town": [24.9100, 66.9700]
}

@dataclass
class MarketConfig:
    QUALITY_MULTIPLIERS: Dict[str, float] = field(default_factory=lambda: {
        "A+ (Luxury)": 1.60, "A (Premium)": 1.30, "B (Standard)": 1.00, "C (Basic)": 0.85
    })
    ROAD_WIDTH_FACTORS: Dict[str, float] = field(default_factory=lambda: {
        "Main Boulevard (100ft+)": 1.15, 
        "Wide Road (60-80ft)": 1.08,
        "Standard Street (30-40ft)": 1.00, 
        "Narrow Lane (<30ft)": 0.95
    })
    COMMERCIAL_MULTIPLIER: float = 1.60
    ROOM_PREMIUM: int = 1200000

class PDFReport(FPDF):
    def header(self):
        try: self.image('logo_black.png', 10, 8, 25)
        except: pass
        self.set_font('Arial', 'B', 14)
        self.cell(80)
        self.cell(30, 10, 'PropData - Valuation Report', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | CyberWeb Labs PropData', 0, 0, 'C')

def create_pdf_bytes(payload: Dict[str, Any]) -> bytes:
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    date_str = datetime.date.today().strftime('%d-%b-%Y')
    pdf.cell(0, 8, f"Date: {date_str}", ln=True)
    clean_loc = payload['location'].encode('latin-1', 'ignore').decode('latin-1')
    pdf.cell(0, 8, f"Location: {clean_loc} ({payload['type']})", ln=True)
    pdf.ln(6)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Estimated Value: {payload['fmt_price']}", ln=True, border=0, fill=True)
    pdf.ln(6)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, f"Plot Area: {payload['area']} sq. yards\nRoad Category: {payload['road_width']}")
    if payload['type'] == "Residential":
        pdf.multi_cell(0, 7, f"Bedrooms: {payload['bedrooms']}\nQuality: {payload['quality']}")
    pdf.ln(6)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, "Financial Breakdown", ln=True)
    pdf.set_font('Arial', '', 10)
    bd = payload['breakdown']
    pdf.cell(120, 7, "Land Value:", 0, 0)
    pdf.cell(0, 7, f"PKR {bd['land']:,.0f}", ln=True)
    if payload['type'] == "Residential":
        pdf.cell(120, 7, "Structure Value:", 0, 0)
        pdf.cell(0, 7, f"PKR {bd['structure']:,.0f}", ln=True)
    if bd.get('features', 0) > 0:
        pdf.cell(120, 7, "Feature Premiums:", 0, 0)
        pdf.cell(0, 7, f"PKR {bd['features']:,.0f}", ln=True)
    pdf.ln(8)
    pdf.set_font('Arial', 'I', 9)
    pdf.multi_cell(0, 6, "Disclaimer: This is an algorithmic estimate for informational purposes only.")
    return pdf.output(dest='S').encode('latin-1', 'replace')

class ValuationEngine:
    def __init__(self, config: MarketConfig):
        self.config = config

    def calculate_depreciation_factor(self, construction_year: int) -> float:
        current = datetime.date.today().year
        age = max(0, current - construction_year)
        if age <= 0: return 1.10
        if age <= 5: return 1.00
        if age <= 10: return 0.85
        if age <= 20: return 0.70
        return 0.55

    def calculate_estimate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            base = BASE_RATES.get(params['location'], 50_000)
            road_f = self.config.ROAD_WIDTH_FACTORS.get(params['road_width'], 1.0)
            land_value = base * road_f * params['area']

            structure_value = 0.0
            depreciation = 1.0
            if params['type'] == "Residential":
                raw_struct = params['bedrooms'] * self.config.ROOM_PREMIUM
                quality_mult = self.config.QUALITY_MULTIPLIERS.get(params['quality'], 1.0)
                depreciation = self.calculate_depreciation_factor(params['year_built'])
                structure_value = raw_struct * quality_mult * depreciation

            features = 0.0
            if params.get('is_corner'): features += land_value * 0.15
            if params.get('is_park'): features += land_value * 0.10
            if params.get('is_west_open'): features += land_value * 0.05

            total = land_value + structure_value + features
            if params['type'] == "Commercial": total *= self.config.COMMERCIAL_MULTIPLIER

            variance = float(np.random.uniform(0.97, 1.03))
            final = float(total * variance)

            breakdown = {
                "base_rate": base, "land": land_value, "structure": structure_value,
                "features": features, "depreciation_factor": depreciation, "pre_variance": total
            }
            return {"price": final, "breakdown": breakdown}
        except Exception as e:
            logger.exception("Calculation error")
            raise

    @staticmethod
    @st.cache_data
    def generate_forecast(start_price: float, months: int) -> pd.DataFrame:
        months = int(months)
        growth = np.linspace(start_price, start_price * 1.12, months)
        noise = np.random.normal(0, start_price * 0.015, months)
        values = growth + noise
        dates = pd.date_range(start=datetime.date.today(), periods=months, freq='ME')
        return pd.DataFrame({"Date": dates, "Market Value": values})

def format_pk(amount: float) -> Tuple[float, float, str]:
    crore = amount / 10_000_000
    lakh = amount / 100_000
    return crore, lakh, f"PKR {amount:,.0f}"

DARK_CSS = """
<style>
    .stApp { background-color: #0d1117; color: #e6e6e6; font-family: 'Inter', sans-serif; }
    .header-card { 
        background: linear-gradient(145deg, #161b22, #0d1117);
        padding: 20px; border-radius: 12px; border: 1px solid #30363d; 
        box-shadow: 0 4px 20px rgba(0,0,0,0.3); margin-bottom: 20px; text-align: center;
    }
    .metric-card { 
        background: #161b22; padding: 20px; border-radius: 10px; 
        border: 1px solid #30363d; box-shadow: 0 4px 15px rgba(0,180,216,0.1); text-align: center;
    }
    .input-card { 
        background: #161b22; padding: 20px; border-radius: 10px; 
        border: 1px solid #30363d; margin-bottom: 20px;
    }
    h1, h2, h3 { color: #58a6ff !important; }
    p, label { color: #c9d1d9 !important; }
    .price { color: #238636; font-size: 1.8rem; font-weight: 800; }
    .sub-price { color: #8b949e; font-size: 1rem; }
    .stButton>button { 
        background-color: #238636; color: white; border: 1px solid rgba(240,246,252,0.1); 
        border-radius: 6px; font-weight: 600;
    }
    .stButton>button:hover { background-color: #2ea043; border-color: #8b949e; }
    .footer { color: #8b949e; font-size: 0.8rem; text-align: center; margin-top: 30px; }
</style>
"""

class Application:
    def __init__(self):
        self.cfg = MarketConfig()
        self.engine = ValuationEngine(self.cfg)
        st.set_page_config(page_title="PropData | Karachi", page_icon="🏢", layout="wide", initial_sidebar_state="auto", menu_items={
        'Get Help': 'https://www.linkedin.com/in/muhammad-danish-data-science/',
        'Report a bug': "mailto:contact@cyberweblabs.com",
        'About': "### PropData v11.0\nBuilt by **CyberWeb Labs**.\n\nEngineered by **Muhammad Danish** using Python, Pandas, and Altair."
    })
        st.markdown(DARK_CSS, unsafe_allow_html=True)
        if "history" not in st.session_state: st.session_state["history"] = []

    def render(self):
        st.markdown("""
        <div class="header-card">
            <h1 style='margin:0; font-size:2rem; background: linear-gradient(90deg, #58a6ff, #00b4d8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                PropData Estimator
            </h1>
            <p style='color:#8b949e; margin-top:5px;'>AI-Powered Karachi Real Estate Valuation</p>
        </div>
        """, unsafe_allow_html=True)

        left, right = st.columns([1, 1.2], gap="large")

        with left:
            st.markdown('<div class="input-card">', unsafe_allow_html=True)
            st.markdown("### 📍 Location Details")
            
            # MOVED OUTSIDE FORM for interactivity
            zone = st.selectbox("Market Zone", list(MARKET_CLUSTERS.keys()))
            location = st.selectbox("Area / Sector", list(MARKET_CLUSTERS[zone].keys()))
            
            with st.form("valuation"):
                st.markdown("---")
                st.markdown("### 📐 Plot Specs")
                c1, c2 = st.columns(2)
                with c1:
                    area = st.slider("Area (Sq. Yards)", 50, 4000, 240, step=10)
                    prop_type = st.radio("Type", ["Residential", "Commercial"], horizontal=True)
                with c2:
                    road_width = st.selectbox("Road Width", list(self.cfg.ROAD_WIDTH_FACTORS.keys()), index=2)
                    year_built = st.number_input("Built Year", 1950, 2025, 2020)

                if prop_type == "Residential":
                    st.markdown("### 🏠 Structure")
                    c3, c4 = st.columns(2)
                    with c3: bedrooms = st.slider("Bedrooms", 1, 12, 3)
                    with c4: quality = st.select_slider("Quality", options=list(self.cfg.QUALITY_MULTIPLIERS.keys()), value="B (Standard)")
                else:
                    bedrooms, quality = 0, "B (Standard)"

                st.markdown("### ✨ Attributes")
                fc1, fc2, fc3 = st.columns(3)
                with fc1: is_corner = st.checkbox("Corner")
                with fc2: is_park = st.checkbox("Park Facing")
                with fc3: is_west = st.checkbox("West Open")

                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Run Valuation", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            st.markdown("### 🗺️ Location Context")
            if location in AREA_COORDINATES:
                lat, lon = AREA_COORDINATES[location]
                st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}), zoom=13, use_container_width=True)
            else:
                st.info("Map coordinates unavailable for this sector.")

            if submitted:
                params = {
                    "location": location, "area": int(area), "type": prop_type,
                    "road_width": road_width, "year_built": int(year_built),
                    "bedrooms": int(bedrooms), "quality": quality,
                    "is_corner": bool(is_corner), "is_park": bool(is_park), "is_west_open": bool(is_west)
                }

                with st.spinner("Calculating..."):
                    time.sleep(0.4)
                    result = self.engine.calculate_estimate(params)

                price = float(result["price"])
                bd = result["breakdown"]
                crore, lakh, fmt_price = format_pk(price)

                st.markdown("---")
                st.markdown(f"""
                <div class="metric-card">
                    <p style="color:#8b949e; margin:0;">Estimated Market Value</p>
                    <p class="price">{fmt_price}</p>
                    <p class="sub-price">{crore:.2f} Crore  |  {lakh:.0f} Lakh</p>
                </div>
                """, unsafe_allow_html=True)

                col_pdf, col_space = st.columns([1, 1])
                with col_pdf:
                    payload = {
                        "location": params["location"], "type": params["type"], "fmt_price": fmt_price,
                        "area": params["area"], "year_built": params["year_built"], "road_width": params["road_width"],
                        "bedrooms": params["bedrooms"], "quality": params["quality"], "breakdown": bd
                    }
                    pdf_bytes = create_pdf_bytes(payload)
                    st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="Valuation_Report.pdf", mime="application/pdf", use_container_width=True)

                with st.expander("View Cost Breakdown"):
                    st.write(f"**Base Land Rate:** PKR {bd['base_rate']:,} / sqyd")
                    st.write(f"**Total Land Value:** PKR {bd['land']:,.0f}")
                    st.write(f"**Structure Cost:** PKR {bd['structure']:,.0f}")
                    st.write(f"**Feature Premiums:** PKR {bd['features']:,.0f}")

        st.markdown("<div class='footer'>PropData • Built by CyberWeb Labs</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    Application().render()