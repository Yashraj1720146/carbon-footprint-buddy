Footprint Buddy

Footprint Buddy is an interactive web app built with Streamlit to help users calculate, understand, 
and reduce their annual carbon footprint in a personalized manner.

---

Features

User Authentication
- Secure login/signup system with PBKDF2 password hashing
- SQLite database for storing user credentials

Carbon Footprint Calculator
Covers 8 key areas of your lifestyle:
1. Commute habits
2. Flight travel
3. Electricity consumption
4. Cooking fuels used
5. Diet preferences
6. Water usage
7. Waste generation & recycling
8. Streaming hours

Instant Feedback
- Total CO₂ emissions in tonnes/year
- Emission level classification: Low, Moderate, High, Very High
- Personalized eco-tips

Interactive Visualizations
- Pie Chart of emissions by sector
- Bar Graph to compare contributions

Sleek and Responsive UI
- Styled with custom CSS, Google Fonts, and responsive layout
- Modern visuals for better engagement

---

Technologies Used

- Python: Core programming language
- Streamlit: Web interface and state management
- Plotly: Data visualizations
- SQLite: User data persistence
- Passlib (PBKDF2): Password hashing
- HTML/CSS: Styling and layout

---

How to Run Locally

Prerequisites:
- Python 3.8+
- pip (Python package manager)
- Optional: virtual environment (venv or conda)

Installation:

# Clone the repository
git clone https://github.com/Yashraj1720146/carbon-footprint-buddy.git
cd carbon-footprint-buddy

# Optional: create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

Run the App:

cd FootprintBuddyMain
streamlit run main.py


- Open your browser to the URL shown in the terminal (usually http://localhost:8501)
- Create a new account or log in with existing credentials

---

Notes:

- User credentials are stored securely in SQLite with PBKDF2 hashing (
python -u .\check_db.py, to check the usesrs in the database )
- Database file: users.db (auto-created on first signup)
- .gitignore ensures sensitive files like users.db and virtual environments are not pushed to GitHub
