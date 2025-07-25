# 🌍 Footprint Buddy

**Footprint Buddy** is an interactive web app built with [Streamlit](https://streamlit.io/) to help users calculate, understand, and reduce their **annual carbon footprint** in a personalized manner.



---

## ✨ Features

🟢 **User Authentication**  
- Secure login/signup system (with SHA-256 password hashing)
- JSON-based user data persistence

🟢 **Carbon Footprint Calculator**  
Covers 8 key areas of your lifestyle:
1. 🚗 Commute habits
2. ✈️ Flight travel
3. 💡 Electricity consumption
4. 🍳 Cooking fuels used
5. 🍽️ Diet preferences
6. 🚰 Water usage
7. 🗑️ Waste generation & recycling
8. 📺 Streaming hours

🟢 **Instant Feedback**
- Total CO₂ emissions in tonnes/year
- Emission level classification: Low, Moderate, High, Very High
- Personalized eco-tips

🟢 **Interactive Visualizations**

- 📊 **Pie Chart** of emissions by sector
- 📋 **Bar Graph** to compare contributions

🟢 **Sleek and Responsive UI**
- Styled with custom **CSS**, **Google Fonts**, and responsive layout
- Beautiful modern visuals for better engagement

---



| Technology        | Role                      |
|------------------|---------------------------|
| **Python**        | Core programming language |
| **Streamlit**     | Web interface, state mgmt |
| **Plotly**        | Data Visualizations       |
| **JSON**          | User data persistence     |
| **Hashlib**       | Password hashing          |
| **HTML/CSS**      | Styling and layout        |

---




## 🛠️ How to Run Locally

### ✅ Prerequisites

- Python 3.8+
- `pip` (Python package manager)
- (Optional) Create a virtual environment with `venv` or `conda`

### 📥 Installation

```bash
# Clone the repository
git clone https://github.com/your-username/footprint-buddy.git
cd footprint-buddy

# Install dependencies
pip install -r requirements.txt