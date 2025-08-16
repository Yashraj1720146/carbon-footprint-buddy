import streamlit as st
import json
import os
import hashlib
import base64
import sqlite3
import plotly.graph_objects as go
import hmac
from datetime import datetime

# Optional PDF dependency: pip install fpdf2
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except Exception:
    FPDF_AVAILABLE = False

# --- Page Config ---
st.set_page_config(page_title="Footprint Buddy", layout="wide")

# --- Helper Functions for User Management (SQLite) ---
DB_PATH = "users.db"
CURRENT_PBKDF2_ITERS = 310_000  # target iterations for PBKDF2

def db_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

# Legacy SHA256 (kept for backward compatibility)
def legacy_sha256(password):
    return hashlib.sha256(password.encode()).hexdigest()

# New PBKDF2-based hashing with per-user salt
def hash_password_pbkdf2(password, salt=None, iterations=CURRENT_PBKDF2_ITERS):
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(dk).decode("ascii"), iterations

def verify_password(password, record):
    """
    record can be:
      - legacy string (sha256 hex)  -> verify against legacy
      - dict {"salt": b64, "hash": b64, "iter": int} -> verify PBKDF2
    """
    if isinstance(record, str):
        # legacy
        return hmac.compare_digest(record, legacy_sha256(password))
    if isinstance(record, dict):
        try:
            salt = base64.b64decode(record.get("salt", ""))
            iters = int(record.get("iter", CURRENT_PBKDF2_ITERS))
            expected = base64.b64decode(record.get("hash", ""))
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
    return False

def init_db():
    # Make the app self-initializing
    with db_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")  # better concurrency for Streamlit
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)
        conn.commit()

def get_user_password_blob(username):
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        return row[0] if row else None

def set_user_password_blob(username, blob):
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = ? WHERE username = ?", (blob, username))
        conn.commit()

def create_user_row(username, password_blob):
    try:
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password_blob))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Username already exists
        return False

def signup(username, password):
    # Basic guard (UI already validates)
    if not username or not password:
        return False
    if get_user_password_blob(username) is not None:
        return False
    salt_b64, hash_b64, iters = hash_password_pbkdf2(password)
    record = {"salt": salt_b64, "hash": hash_b64, "iter": iters}
    return create_user_row(username, json.dumps(record))

def login(username, password):
    blob = get_user_password_blob(username)
    if blob is None:
        return False

    # Parse stored password; can be JSON (PBKDF2) or legacy SHA256 hex string
    try:
        record = json.loads(blob)
    except Exception:
        record = blob  # legacy string

    ok = verify_password(password, record)

    # Auto-upgrade legacy SHA256 to PBKDF2 or bump low-iteration PBKDF2 on successful login
    if ok:
        needs_rehash = isinstance(record, str) or (isinstance(record, dict) and int(record.get("iter", 0)) < CURRENT_PBKDF2_ITERS)
        if needs_rehash:
            salt_b64, hash_b64, iters = hash_password_pbkdf2(password)
            new_record = {"salt": salt_b64, "hash": hash_b64, "iter": iters}
            set_user_password_blob(username, json.dumps(new_record))

    return ok

# Optional: one-time migration from users.json to SQLite
def migrate_json_users_to_sqlite(json_path="users.json"):
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, "r") as f:
            users = json.load(f)
        for username, record in users.items():
            if get_user_password_blob(username) is not None:
                continue
            blob = json.dumps(record) if isinstance(record, dict) else record
            create_user_row(username, blob)
        os.rename(json_path, json_path + ".migrated.bak")
        print("✅ Migration complete. Backup created:", json_path + ".migrated.bak")
    except Exception as e:
        print("⚠️ Migration failed:", e)

# Initialize DB (and optionally migrate old JSON users once)
init_db()
# migrate_json_users_to_sqlite()  # <- run once if you have existing users.json

# --- Session State Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "show_results" not in st.session_state:
    st.session_state.show_results = False
if "current_user" not in st.session_state:
    st.session_state.current_user = ""
if "dummy_rerun_flag" not in st.session_state:
    st.session_state.dummy_rerun_flag = False

# --- Rerun helper (instead of experimental_rerun) ---
def rerun():
    st.session_state.dummy_rerun_flag = not st.session_state.dummy_rerun_flag

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.show_results = False
    for key in ["login_username", "login_password", "signup_username", "signup_password", "confirm_password"]:
        if key in st.session_state:
            del st.session_state[key]
    rerun()

# --- Emission Factors ---
EMISSION_FACTORS = {
    "India": {
        "Transportation": {
            "Car (Petrol)": 0.18,   # kgCO2/km per vehicle; carpool applied per passenger
            "Car (Diesel)": 0.17,
            "Car (CNG)": 0.13,
            "Bus": 0.08,            # per passenger-km
            "Train": 0.04,          # per passenger-km
            "Bike": 0.05,
            "Walk/Bicycle": 0.0,
            "Electric Car": 0.05
        },
        "Electricity": 0.75,       # kgCO2/kWh (updated)
        "Diet": {
            "Non-Vegetarian": 2.5,  # kgCO2/meal
            "Vegetarian": 1.25,
            "Vegan": 0.9
        },
        "Waste": 0.1,              # kgCO2/kg
        "Water": 0.0003,           # kgCO2/liter
        "CookingFuel": {           # kgCO2/unit
            "LPG": 2.98,           # per kg
            "Natural Gas": 2.0,    # per m3
            "Electricity": 0.75,   # per kWh (align with electricity factor)
            "Biomass": 0.4         # per kg
        },
        # Network + datacenter only (device electricity already counted in household kWh)
        "Streaming": 0.03,         # kgCO2/hour
        "Flight": {
            "Short-haul": 0.15,    # kgCO2/km
            "Long-haul": 0.11      # kgCO2/km
        }
    }
}

# Modifiers for electricity source
ELECTRICITY_BY_SOURCE = {
    "Grid": 0.75,
    "Solar": 0.05,
    "Wind": 0.02,
    "Mixed": 0.50
}

# --- Custom CSS ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        .centered-card {
            max-width: 700px;
            margin: 80px auto 0 auto;
            padding: 50px 40px 40px 40px;
            background: #fff;
            border-radius: 18px;
            text-align: center;
            box-shadow: 2px 2px 25px rgba(0,0,0,0.18);
        }
        .main-header {
            font-family: 'Montserrat', sans-serif;
            font-size: 54px;
            color: #1b5e20;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .sub-header {
            font-family: 'Montserrat', sans-serif;
            font-size: 32px;
            color: #388e3c;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .welcome-message {
            font-family: 'Roboto', sans-serif;
            font-size: 26px;
            color: #2e7d32;
            margin-bottom: 30px;
        }
        .dev-credit {
            position: fixed;
            right: 30px;
            bottom: 18px;
            font-family: 'Roboto', sans-serif;
            font-size: 18px;
            color: #888;
            opacity: 0.85;
            z-index: 9999;
        }
        .stButton>button {
            font-size: 22px !important;
            font-weight: bold !important;
            padding: 10px 30px !important;
            border-radius: 10px !important;
            background: #d32f2f !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 1px 1px 8px rgba(0,0,0,0.08);
            cursor: pointer;
        }
        label, .stTextInput label, .stNumberInput label {
            font-size: 20px !important;
            font-family: 'Roboto', sans-serif;
            font-weight: bold;
        }
        .main-bg {
            background: linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%);
            min-height: 100vh;
            width: 100vw;
            position: fixed;
            left: 0;
            top: 0;
            z-index: -1;
        }
    </style>
    <div class="main-bg"></div>
""", unsafe_allow_html=True)

# --- LOGIN / SIGNUP PAGE ---
if not st.session_state.logged_in:
    st.markdown("""
        <style>
            .stApp {
                background: url("https://vapor-eu-north-1-prod-1614245610.s3.eu-north-1.amazonaws.com/editor-uploads/XXI6eRoAVTgaPMnF8IVlgeuKDEBecthMt4tvyNzR.png") no-repeat center center fixed;
                background-size: cover;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="centered-card">
        <div class="main-header">Footprint Buddy</div>
        <div class="sub-header">Welcome!</div>
        <div class="welcome-message">
            Start your journey to a greener future. Track, understand, and reduce your carbon footprint today!
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Sign Up"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if not username or not password:
                st.error("Please enter both username and password.")
            elif login(username, password):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.success("Login successful!")
                rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        st.subheader("Sign Up")
        new_username = st.text_input("Create Username", key="signup_username")
        new_password = st.text_input("Create Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        if st.button("Sign Up"):
            if not new_username or not new_password:
                st.error("Username and password cannot be empty.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif signup(new_username, new_password):
                st.success("Account created successfully! Please log in.")
            else:
                st.error("Username already exists.")

    st.markdown('<div class="dev-credit">Developed by Yashraj Pillay</div>', unsafe_allow_html=True)

# --- MAIN APP (AFTER LOGIN) ---
elif not st.session_state.show_results:
    col1, col2 = st.columns([8,1])
    with col2:
        if st.button("Logout", key="logout_btn", help="Logout"):
            logout()

    st.markdown(f"""
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; margin-top:30px; margin-bottom:30px;">
            <div style="font-family:'Montserrat',sans-serif; font-size:54px; color:#1b5e20; font-weight:700; text-align:center;">
                Footprint Buddy
            </div>
            <div style="font-family:'Montserrat',sans-serif; font-size:32px; color:#388e3c; font-weight:700; margin-top:10px; text-align:center;">
                Welcome, {st.session_state.current_user}!
            </div>
            <div style="font-family:'Roboto',sans-serif; font-size:26px; color:#2e7d32; margin-top:10px; text-align:center;">
                Calculate your annual carbon footprint and take your first step towards a greener tomorrow.
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    # 1. Commute
    st.markdown('<div class="sub-header">🚗 Daily commute distance (in km)</div>', unsafe_allow_html=True)
    commute_mode = st.selectbox("Mode of transport", list(EMISSION_FACTORS["India"]["Transportation"].keys()), key="commute_mode")
    commute_distance = st.number_input("Distance (km/day)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="distance_input")
    commute_days_per_week = st.number_input("Commute days per week", min_value=0, max_value=7, value=5, step=1, key="commute_days_per_week")
    carpooling = st.number_input("Number of people sharing (if car; buses/trains already per passenger)", min_value=1, max_value=10, value=1, step=1, key="carpooling_input")

    # 2. Flight Travel
    st.markdown('<div class="sub-header">✈️ Flight Travel</div>', unsafe_allow_html=True)
    short_flights = st.number_input("Number of short-haul flights per year", min_value=0, max_value=50, value=0, step=1, key="short_flights")
    long_flights = st.number_input("Number of long-haul flights per year", min_value=0, max_value=20, value=0, step=1, key="long_flights")
    flight_class = st.selectbox("Class of travel", ["Economy", "Business", "First"], key="flight_class")

    # 3. Electricity
    st.markdown('<div class="sub-header">💡 Monthly electricity consumption (in kWh)</div>', unsafe_allow_html=True)
    electricity = st.number_input("Electricity (kWh/month)", min_value=0.0, max_value=1000.0, value=0.0, step=1.0, key="electricity_input")
    elec_source = st.selectbox("Source of electricity", ["Grid", "Solar", "Wind", "Mixed"], key="elec_source")
    household_size = st.number_input("Number of people in household", min_value=1, max_value=20, value=1, step=1, key="household_size")

    # 4. Cooking Fuel
    st.markdown('<div class="sub-header">🍳 Cooking fuel type</div>', unsafe_allow_html=True)
    cooking_fuel_type = st.selectbox(
        "Select cooking fuel type",
        list(EMISSION_FACTORS["India"]["CookingFuel"].keys()),
        key="cooking_fuel_type"
    )
    if cooking_fuel_type == "LPG" or cooking_fuel_type == "Biomass":
        cooking_fuel_amount = st.number_input(f"Amount of {cooking_fuel_type} used (kg/month)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="cooking_fuel_amount")
    elif cooking_fuel_type == "Natural Gas":
        cooking_fuel_amount = st.number_input("Amount of Natural Gas used (m³/month)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="cooking_fuel_amount")
    elif cooking_fuel_type == "Electricity":
        cooking_fuel_amount = st.number_input("Amount of Electricity used for cooking (kWh/month)", min_value=0.0, max_value=1000.0, value=0.0, step=1.0, key="cooking_fuel_amount")
    else:
        cooking_fuel_amount = 0.0
    cooking_people = st.number_input("Number of people sharing kitchen", min_value=1, max_value=20, value=1, step=1, key="cooking_people")
    efficient_stove = st.radio("Use of energy-efficient stove?", ["Yes", "No"], key="efficient_stove")

    # 5. Diet
    st.markdown('<div class="sub-header">🍽️ Number of meals per day</div>', unsafe_allow_html=True)
    meals = st.number_input("Meals per day", min_value=0, max_value=10, value=3, step=1, key="meals_input")
    diet_type = st.selectbox("Diet type", list(EMISSION_FACTORS["India"]["Diet"].keys()), key="diet_type")
    eating_out = st.slider("Meals eaten out per week", min_value=0, max_value=21, value=0, step=1, key="eating_out_input")

    # 6. Water
    st.markdown('<div class="sub-header">🚰 Daily water usage (in liters)</div>', unsafe_allow_html=True)
    water = st.number_input("Water Usage (liters/day)", min_value=0.0, max_value=1000.0, value=0.0, step=1.0, key="water_input")
    water_saving = st.radio("Use of water-saving devices?", ["Yes", "No"], key="water_saving")
    water_source = st.selectbox("Source of water", ["Municipal", "Borewell", "Rainwater", "Other"], key="water_source")

    # 7. Waste
    st.markdown('<div class="sub-header">🗑️ Waste generated per week (in kg)</div>', unsafe_allow_html=True)
    waste = st.number_input("Waste (kg/week)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="waste_input")
    recycling = st.slider("Percentage of waste recycled/composted (%)", min_value=0, max_value=100, value=0, step=1, key="recycling_input")
    waste_type = st.multiselect("Type of waste", ["Organic", "Plastic", "Paper", "Glass", "Metal", "Other"], key="waste_type")

    # 8. Streaming
    st.markdown('<div class="sub-header">📺 Average hours of video streaming per week</div>', unsafe_allow_html=True)
    streaming_hours = st.number_input("Streaming hours/week", min_value=0.0, max_value=168.0, value=0.0, step=0.1, key="streaming_hours")
    streaming_device = st.selectbox("Device used for streaming", ["Phone", "Laptop", "TV", "Tablet", "Other"], key="streaming_device")

    # --- Emissions Calculation (with fixes) ---

    # 1. Commute (annualized). Use days/week; carpool reduction only for cars, including Electric Car.
    annual_commute_km = commute_distance * commute_days_per_week * 52
    base_commute_factor = EMISSION_FACTORS["India"]["Transportation"][commute_mode]
    is_car = commute_mode.startswith("Car") or (commute_mode == "Electric Car")
    if is_car and carpooling > 0:
        commute_emissions_kg = base_commute_factor * (annual_commute_km / max(1, carpooling))
    else:
        # bus/train/bike/walk/electric car: no carpool division (already per passenger-km or individual)
        commute_emissions_kg = base_commute_factor * annual_commute_km
    commute_emissions = round(commute_emissions_kg / 1000, 2)  # tonnes/year

    # 2. Flight Travel
    flight_class_multiplier = {"Economy": 1, "Business": 1.5, "First": 2.5}[flight_class]
    short_flight_emissions = short_flights * 1100 * EMISSION_FACTORS["India"]["Flight"]["Short-haul"] * flight_class_multiplier
    long_flight_emissions = long_flights * 6000 * EMISSION_FACTORS["India"]["Flight"]["Long-haul"] * flight_class_multiplier
    flight_emissions = round((short_flight_emissions + long_flight_emissions) / 1000, 2)  # tonnes/year

    # 3. Electricity (annualized, per household -> apportion per person; adjust by source; subtract cooking kWh if cooking is Electricity)
    electricity_year_kwh = electricity * 12

    if cooking_fuel_type == "Electricity":
        # Subtract cooking-electricity from household electricity to avoid double count
        cooking_kwh_year = cooking_fuel_amount * 12
        electricity_year_kwh = max(0.0, electricity_year_kwh - cooking_kwh_year)

    elec_factor = ELECTRICITY_BY_SOURCE.get(elec_source, EMISSION_FACTORS["India"]["Electricity"])
    electricity_emissions_kg = elec_factor * electricity_year_kwh
    # Apportion by household size
    electricity_emissions = round((electricity_emissions_kg / max(1, household_size)) / 1000, 2)

    # 4. Cooking Fuel (annualized; per-person via cooking_people; efficient stove reduction)
    cooking_fuel_amount_year = cooking_fuel_amount * 12
    cooking_factor = EMISSION_FACTORS["India"]["CookingFuel"][cooking_fuel_type]
    # Use electricity source factor if cooking uses electricity
    if cooking_fuel_type == "Electricity":
        cooking_factor = ELECTRICITY_BY_SOURCE.get(elec_source, EMISSION_FACTORS["India"]["Electricity"])
    cooking_fuel_emissions_kg = cooking_factor * cooking_fuel_amount_year

    # Efficient stove reduction (e.g., 20%)
    if efficient_stove == "Yes":
        cooking_fuel_emissions_kg *= 0.8

    # Per-person
    cooking_fuel_emissions = round((cooking_fuel_emissions_kg / max(1, cooking_people)) / 1000, 2)

    # 5. Diet (annualized per meal; eating out uplift for those meals)
    meals_year = meals * 365
    diet_base = EMISSION_FACTORS["India"]["Diet"][diet_type]
    meals_out_year = eating_out * 52
    meals_out_year = min(meals_out_year, meals_year)  # cap

    # 30% uplift for eating-out meals
    diet_emissions_kg = diet_base * (meals_year - meals_out_year) + (diet_base * 1.3) * meals_out_year
    diet_emissions = round(diet_emissions_kg / 1000, 2)

    # 6. Water (annualized; water-saving reduction 10%)
    water_year = water * 365
    water_factor = EMISSION_FACTORS["India"]["Water"]
    water_emissions_kg = water_factor * water_year
    if water_saving == "Yes":
        water_emissions_kg *= 0.9
    water_emissions = round(water_emissions_kg / 1000, 2)

    # 7. Waste (annualized, adjust for recycling)
    waste_year = waste * 52
    waste_emissions = EMISSION_FACTORS["India"]["Waste"] * waste_year * (1 - recycling/100)
    waste_emissions = round(waste_emissions / 1000, 2)

    # 8. Streaming (network + datacenter only; device energy already included in electricity)
    streaming_emissions_kg = EMISSION_FACTORS["India"]["Streaming"] * streaming_hours * 52
    streaming_emissions = round(streaming_emissions_kg / 1000, 2)

    total_emissions = round(
        commute_emissions + flight_emissions + electricity_emissions +
        cooking_fuel_emissions + diet_emissions + water_emissions +
        waste_emissions + streaming_emissions, 2
    )

    st.session_state.results = {
        "Commute": commute_emissions,
        "Flight": flight_emissions,
        "Electricity": electricity_emissions,
        "Cooking Fuel": cooking_fuel_emissions,
        "Diet": diet_emissions,
        "Water": water_emissions,
        "Waste": waste_emissions,
        "Streaming": streaming_emissions,
        "Total": total_emissions,
        # Details for display/future use
        "Details": {
            "Commute Mode": commute_mode,
            "Commute Days/Week": commute_days_per_week,
            "Carpooling": carpooling,
            "Short Flights": short_flights,
            "Long Flights": long_flights,
            "Flight Class": flight_class,
            "Electricity Source": elec_source,
            "Household Size": household_size,
            "Cooking Fuel Type": cooking_fuel_type,
            "Cooking People": cooking_people,
            "Efficient Stove": efficient_stove,
            "Diet Type": diet_type,
            "Eating Out": eating_out,
            "Water Saving": water_saving,
            "Water Source": water_source,
            "Recycling %": recycling,
            "Waste Types": waste_type,
            "Streaming Device": streaming_device
        }
    }

    if st.button("Calculate CO2 Emissions"):
        st.session_state.show_results = True
        rerun()

    st.markdown('<div class="dev-credit">Developed by Yashraj Pillay</div>', unsafe_allow_html=True)

# --- RESULTS PAGE ---
else:
    col1, col2 = st.columns([8,1])
    with col2:
        if st.button("Logout", key="logout_btn2", help="Logout"):
            logout()

    st.markdown("""
        <div style="text-align:center;">
            <div class="main-header">Your Footprint Buddy Results 🌍</div>
        </div>
    """, unsafe_allow_html=True)

    results = st.session_state.results
    details = results.get("Details", {})

    # Display results in two columns, two at a time
    factors = [
        ("Commute", "🚗 Commute", f"Mode: {details.get('Commute Mode','')}<br>Days/Week: {details.get('Commute Days/Week','')}<br>Carpooling (cars only): {details.get('Carpooling','')}"),
        ("Flight", "✈️ Flight Travel", f"Short-haul: {details.get('Short Flights','')}<br>Long-haul: {details.get('Long Flights','')}<br>Class: {details.get('Flight Class','')}"),
        ("Electricity", "💡 Electricity", f"Source: {details.get('Electricity Source','')}<br>Household Size: {details.get('Household Size','')}"),
        ("Cooking Fuel", "🍳 Cooking Fuel", f"Type: {details.get('Cooking Fuel Type','')}<br>People Sharing: {details.get('Cooking People','')}<br>Efficient Stove: {details.get('Efficient Stove','')}"),
        ("Diet", "🍽️ Diet", f"Diet Type: {details.get('Diet Type','')}<br>Meals Out/Week: {details.get('Eating Out','')}"),
        ("Water", "🚰 Water", f"Saving Devices: {details.get('Water Saving','')}<br>Source: {details.get('Water Source','')}"),
        ("Waste", "🗑️ Waste", f"Recycling: {details.get('Recycling %','')}%<br>Types: {', '.join(details.get('Waste Types',[]))}"),
        ("Streaming", "📺 Streaming", f"Device: {details.get('Streaming Device','')}")
    ]

    for i in range(0, len(factors), 2):
        c1, c2 = st.columns(2)
        for j, c in enumerate([c1, c2]):
            if i + j < len(factors):
                key, title, sub = factors[i + j]
                c.markdown(f"""
                    <div style='background:#f7fafc; padding:20px; border-radius:12px; margin-bottom:15px; font-family: "Roboto", sans-serif;'>
                        <h3 style="font-family: 'Montserrat', sans-serif; color:#1b5e20;">{title}</h3>
                        <p style="font-size:22px;">{results[key]} tonnes CO₂/year</p>
                        <small>{sub}</small>
                    </div>
                """, unsafe_allow_html=True)

    total = results['Total']

    # Only render charts if total > 0
    if total > 0:
        # Pie chart
        st.markdown("<h2 style='text-align:center; color:#1976d2; margin-top:40px;'>Pie Chart</h2>", unsafe_allow_html=True)
        pie_labels = ["Commute", "Flight", "Electricity", "Cooking Fuel", "Diet", "Water", "Waste", "Streaming"]
        pie_values = [results[k] for k in pie_labels]
        pie_colors = ['#1b5e20', '#1976d2', '#388e3c', '#ff7043', '#fbc02d', '#0288d1', '#8d6e63', '#7e57c2']

        fig = go.Figure(data=[go.Pie(
            labels=pie_labels,
            values=pie_values,
            marker=dict(colors=pie_colors),
            textinfo='label+percent+value',
            textfont=dict(size=18, color='black'),
            textposition='inside',
            insidetextorientation='radial',
            pull=[0.05]*8
        )])
        fig.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            height=650
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<br><br>", unsafe_allow_html=True)

        # Bar chart
        st.markdown("<h2 style='text-align:center; color:#388e3c; margin-bottom:20px;'>Bar Graph</h2>", unsafe_allow_html=True)
        bar_fig = go.Figure(data=[
            go.Bar(
                x=pie_labels,
                y=pie_values,
                marker_color=pie_colors,
                text=[f"{v} t" for v in pie_values],
                textposition='auto'
            )
        ])
        bar_fig.update_layout(
            title="",
            xaxis_title="Factor",
            yaxis_title="Tonnes CO₂/year",
            plot_bgcolor="#f7fafc",
            paper_bgcolor="#f7fafc",
            font=dict(family="Roboto, sans-serif", size=16)
        )
        st.plotly_chart(bar_fig, use_container_width=True)
    else:
        st.info("No emissions data to visualize yet — enter some values and calculate to see charts.")

    st.markdown(f"""
        <div style='background:#ffebee; padding:20px; border-radius:12px; margin-top:20px; font-family: "Roboto", sans-serif; text-align:center;'>
            <h3 style='color:#d32f2f; font-family: "Montserrat", sans-serif;'>🌍 Total Footprint</h3>
            <p style='font-size:28px; font-weight:bold; color:#d32f2f;'>{results['Total']} tonnes CO₂/year</p>
        </div>
    """, unsafe_allow_html=True)

    # --- Emission Level Classification ---
    if total < 2.0:
        st.success("✅ Your carbon footprint is LOW. 🌿 Your lifestyle is eco-friendly and close to sustainable global targets.")
    elif 2.0 <= total <= 4.5:
        st.info("🟡 Your carbon footprint is MODERATE. 😊 You’re doing okay, but there's room for improvement towards a more sustainable lifestyle.")
    elif 4.5 < total <= 7.0:
        st.warning("⚠️ Your carbon footprint is HIGH. 😟 Try to reduce flights, energy use, or shift to greener alternatives.")
    else:
        st.error("🚨 Your carbon footprint is VERY HIGH. 🔴 This level of emission is not sustainable. Consider making major changes to reduce impact.")

    st.info(
        "🌱 Every small step counts! By making conscious choices in your daily life, you can help create a cleaner, greener planet for future generations. "
        "Reduce, reuse, recycle, and inspire others to join you on the journey to lower carbon emissions. Together, we can make a difference."
    )

    # --- PDF Download (New) ---
    def make_pdf(results_dict, username):
        # Build a simple, portable PDF (uses built-in Helvetica; avoid non-Latin-1 emojis in PDF text)
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_title("Footprint Buddy - Results")
        pdf.set_author("Footprint Buddy")

        # Header
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 10, "Footprint Buddy - Carbon Footprint Report", ln=1)
        pdf.set_font("Helvetica", size=12)
        dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        pdf.cell(0, 8, f"User: {username}", ln=1)
        pdf.cell(0, 8, f"Generated: {dt}", ln=1)
        pdf.ln(4)

        # Total and classification
        total_val = results_dict.get("Total", 0.0)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"Total Footprint: {total_val:.2f} tonnes CO2/year", ln=1)

        if total_val < 2.0:
            classification = "LOW"
            note = "Your lifestyle is eco-friendly and close to sustainable global targets."
        elif 2.0 <= total_val <= 4.5:
            classification = "MODERATE"
            note = "You're doing okay, but there's room for improvement."
        elif 4.5 < total_val <= 7.0:
            classification = "HIGH"
            note = "Try to reduce flights, energy use, or shift to greener alternatives."
        else:
            classification = "VERY HIGH"
            note = "This level of emission is not sustainable. Consider major changes."

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Classification: {classification}", ln=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, note)
        pdf.ln(2)

        # Breakdown table
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(100, 8, "Category", border=1)
        pdf.cell(0, 8, "Tonnes CO2/year", border=1, ln=1)
        pdf.set_font("Helvetica", "", 11)

        cats = ["Commute", "Flight", "Electricity", "Cooking Fuel", "Diet", "Water", "Waste", "Streaming"]
        for cat in cats:
            pdf.cell(100, 8, cat, border=1)
            pdf.cell(0, 8, f"{results_dict.get(cat, 0.0):.2f}", border=1, ln=1)

        # Inputs summary
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Inputs Summary", ln=1)
        pdf.set_font("Helvetica", "", 11)
        d = results_dict.get("Details", {})

        def add_kv(k, v):
            pdf.multi_cell(0, 6, f"{k}: {v}")

        add_kv("Commute Mode", d.get("Commute Mode", ""))
        add_kv("Commute Days/Week", d.get("Commute Days/Week", ""))
        add_kv("Carpooling", d.get("Carpooling", ""))
        add_kv("Short Flights", d.get("Short Flights", ""))
        add_kv("Long Flights", d.get("Long Flights", ""))
        add_kv("Flight Class", d.get("Flight Class", ""))
        add_kv("Electricity Source", d.get("Electricity Source", ""))
        add_kv("Household Size", d.get("Household Size", ""))
        add_kv("Cooking Fuel Type", d.get("Cooking Fuel Type", ""))
        add_kv("Cooking People", d.get("Cooking People", ""))
        add_kv("Efficient Stove", d.get("Efficient Stove", ""))
        add_kv("Diet Type", d.get("Diet Type", ""))
        add_kv("Eating Out (meals/week)", d.get("Eating Out", ""))
        add_kv("Water Saving", d.get("Water Saving", ""))
        add_kv("Water Source", d.get("Water Source", ""))
        add_kv("Recycling %", d.get("Recycling %", ""))
        add_kv("Waste Types", ", ".join(d.get("Waste Types", [])))
        add_kv("Streaming Device", d.get("Streaming Device", ""))

        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(0, 5, "Note: Streaming emissions include only network and datacenter. Household electricity is apportioned per person. Cooking electricity is subtracted from household electricity to avoid double counting.")

        return pdf.output(dest="S").encode("latin-1")

    if FPDF_AVAILABLE:
        pdf_bytes = make_pdf(results, st.session_state.current_user)
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name=f"Footprint_Buddy_{st.session_state.current_user}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )
    else:
        st.info("To enable PDF download, please install fpdf2 (pip install fpdf2) and rerun the app.")

    if st.button("Go Back"):
        st.session_state.show_results = False
        rerun()

    st.markdown('<div class="dev-credit">Developed by Yashraj Pillay</div>', unsafe_allow_html=True)