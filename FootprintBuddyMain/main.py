import streamlit as st
import json
import os
import hashlib
import plotly.graph_objects as go

# --- Page Config ---
st.set_page_config(page_title="Footprint Buddy", layout="wide")

# --- Helper Functions for User Management ---
USERS_FILE = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def signup(username, password):
    users = load_users()
    if username in users:
        return False  # Username exists
    users[username] = hash_password(password)
    save_users(users)
    return True

def login(username, password):
    users = load_users()
    return username in users and users[username] == hash_password(password)

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
            "Car (Petrol)": 0.18,   # kgCO2/km
            "Car (Diesel)": 0.17,
            "Car (CNG)": 0.13,
            "Bus": 0.08,
            "Train": 0.04,
            "Bike": 0.05,
            "Walk/Bicycle": 0.0,
            "Electric Car": 0.05
        },
        "Electricity": 0.82,      # kgCO2/kWh
        "Diet": {
            "Non-Vegetarian": 2.5, # kgCO2/meal
            "Vegetarian": 1.25,
            "Vegan": 0.9
        },
        "Waste": 0.1,             # kgCO2/kg
        "Water": 0.0003,          # kgCO2/liter
        "CookingFuel": {          # kgCO2/unit
            "LPG": 2.98,          # per kg
            "Natural Gas": 2.0,   # per m3
            "Electricity": 0.82,  # per kWh
            "Biomass": 0.4        # per kg
        },
        "Streaming": 0.36,        # kgCO2/hour (global avg, can be refined)
        "Flight": {
            "Short-haul": 0.15,   # kgCO2/km
            "Long-haul": 0.11     # kgCO2/km
        }
    }
}

# --- Custom CSS for fonts and layout (shared, but no background image here) ---
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
        /* Main and result page background */
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
    # Only apply background image on login/signup page
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

    # Developer credit at bottom right
    st.markdown('<div class="dev-credit">Developed by Yashraj Pillay</div>', unsafe_allow_html=True)

# --- MAIN APP (AFTER LOGIN) ---
elif not st.session_state.show_results:
    # Logout button at top right using columns
    col1, col2 = st.columns([8,1])
    with col2:
        if st.button("Logout", key="logout_btn", help="Logout"):
            logout()

    # Centered app name and welcome message with large, attractive font
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
    carpooling = st.number_input("Number of people sharing (if car/bus, else 1)", min_value=1, max_value=10, value=1, step=1, key="carpooling_input")

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

    # --- Emissions Calculation (main values only, details collected for future use) ---

    # 1. Commute (annualized, divided by carpooling)
    commute_distance_year = commute_distance * 365
    commute_emissions = EMISSION_FACTORS["India"]["Transportation"][commute_mode] * commute_distance_year / carpooling
    commute_emissions = round(commute_emissions / 1000, 2)  # tonnes/year

    # 2. Flight Travel
    # Short-haul: 1,100 km avg; Long-haul: 6,000 km avg
    flight_class_multiplier = {"Economy": 1, "Business": 1.5, "First": 2.5}[flight_class]
    short_flight_emissions = short_flights * 1100 * EMISSION_FACTORS["India"]["Flight"]["Short-haul"] * flight_class_multiplier
    long_flight_emissions = long_flights * 6000 * EMISSION_FACTORS["India"]["Flight"]["Long-haul"] * flight_class_multiplier
    flight_emissions = round((short_flight_emissions + long_flight_emissions) / 1000, 2)  # tonnes/year

    # 3. Electricity (annualized, per household)
    electricity_year = electricity * 12
    electricity_emissions = EMISSION_FACTORS["India"]["Electricity"] * electricity_year
    electricity_emissions = round(electricity_emissions / 1000, 2)  # tonnes/year

    # 4. Cooking Fuel (annualized)
    cooking_fuel_amount_year = cooking_fuel_amount * 12
    cooking_fuel_emissions = EMISSION_FACTORS["India"]["CookingFuel"][cooking_fuel_type] * cooking_fuel_amount_year
    cooking_fuel_emissions = round(cooking_fuel_emissions / 1000, 2)  # tonnes/year

    # 5. Diet (annualized, per meal, diet type)
    meals_year = meals * 365
    diet_emissions = EMISSION_FACTORS["India"]["Diet"][diet_type] * meals_year
    diet_emissions = round(diet_emissions / 1000, 2)  # tonnes/year

    # 6. Water (annualized)
    water_year = water * 365
    water_emissions = EMISSION_FACTORS["India"]["Water"] * water_year
    water_emissions = round(water_emissions / 1000, 2)  # tonnes/year

    # 7. Waste (annualized, adjust for recycling)
    waste_year = waste * 52
    waste_emissions = EMISSION_FACTORS["India"]["Waste"] * waste_year * (1 - recycling/100)
    waste_emissions = round(waste_emissions / 1000, 2)  # tonnes/year

    # 8. Streaming (annualized)
    streaming_emissions = EMISSION_FACTORS["India"]["Streaming"] * streaming_hours * 52
    streaming_emissions = round(streaming_emissions / 1000, 2)  # tonnes/year

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

    # Developer credit at bottom right
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
        ("Commute", "🚗 Commute", f"Mode: {details.get('Commute Mode','')}<br>Carpooling: {details.get('Carpooling','')}"),
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

    # Pie chart for all 8 factors using Plotly
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

    # Spacing between pie and bar chart
    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- Bar Graph for all 8 factors ---
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

    st.markdown(f"""
        <div style='background:#ffebee; padding:20px; border-radius:12px; margin-top:20px; font-family: "Roboto", sans-serif; text-align:center;'>
            <h3 style='color:#d32f2f; font-family: "Montserrat", sans-serif;'>🌍 Total Footprint</h3>
            <p style='font-size:28px; font-weight:bold; color:#d32f2f;'>{results['Total']} tonnes CO₂/year</p>
        </div>
    """, unsafe_allow_html=True)

    # --- Emission Level Classification ---
    total = results['Total']
    if total < 2.0:
        st.success("✅ Your carbon footprint is LOW. Great job! 🌿 Your lifestyle is eco-friendly and close to sustainable global targets.")
    elif 2.0 <= total <= 4.5:
        st.info("🟡 Your carbon footprint is MODERATE. 😊 You’re doing okay, but there's room for improvement towards a more sustainable lifestyle.")
    elif 4.5 < total <= 7.0:
        st.warning("⚠️ Your carbon footprint is HIGH. 😟 Try to reduce flights, energy use, or shift to greener alternatives.")
    else:
        st.error("🚨 Your carbon footprint is VERY HIGH. 🔴 This level of emission is not sustainable. Consider making major changes to reduce impact.")

    st.info(
        "🌱 Every small step counts! By making conscious choices in your daily life, you can help create a cleaner, greener planet for future generations. "
        "Reduce, reuse, recycle, and inspire others to join you on the journey to lower carbon emissions. Together, we can make a difference!"
    )

    # --- Go Back to Form Button ---
    if st.button("Go Back"):
        st.session_state.show_results = False
        rerun()

    # Developer credit at bottom right
    st.markdown('<div class="dev-credit">Developed by Yashraj Pillay</div>', unsafe_allow_html=True)