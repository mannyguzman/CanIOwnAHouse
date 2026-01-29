from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Query
import csv
from pathlib import Path


app = FastAPI()
templates = Jinja2Templates(directory="html")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for caching
CITY_PRICES = {}
CITY_STATE_LIST = []
RENT_CITY_PRICES = {}
RENT_CITY_STATE_LIST = []

def load_city_data(filepath: str, price_column: str):
    """Load city data from CSV file"""
    city_prices = {}
    city_list = []
    
    try:
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                city = row["RegionName"].strip().title()
                state = row["State"].strip().upper()
                city_state_key = f"{city}, {state}"
                
                try:
                    price = int(float(row[price_column]))
                    city_prices[city_state_key] = price
                    city_list.append(city_state_key)
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        print(f"Warning: File {filepath} not found")
    
    return city_prices, city_list

def initialize_data():
    """Initialize all data on startup"""
    global CITY_PRICES, CITY_STATE_LIST, RENT_CITY_PRICES, RENT_CITY_STATE_LIST
    
    CITY_PRICES, CITY_STATE_LIST = load_city_data("CityHousePrices2025.csv", "HousePriceAverage")
    RENT_CITY_PRICES, RENT_CITY_STATE_LIST = load_city_data("CityRentPrices2025.csv", "RentPriceAverage")

def find_city_price(city_input: str, is_rent: bool = False):
    """Find price for a city (either house or rent)"""
    city_db = RENT_CITY_PRICES if is_rent else CITY_PRICES
    city_list = RENT_CITY_STATE_LIST if is_rent else CITY_STATE_LIST
    
    # Try exact match first
    if city_input in city_db:
        return city_db[city_input], city_input
    
    # Try with proper formatting
    if ',' in city_input:
        try:
            city_part, state_part = [x.strip() for x in city_input.split(",")]
            city_key = f"{city_part.title()}, {state_part.upper()}"
            if city_key in city_db:
                return city_db[city_key], city_key
        except ValueError:
            pass
    
    # Try partial match (city only)
    matches = [key for key in city_list if key.lower().startswith(f"{city_input.lower()},")]
    if matches:
        city_key = matches[0]
        return city_db[city_key], city_key
    
    return None, city_input.title()

def calculate_mortgage(downpayment: float, yearly_gross_income: float, mortgage_rate: float, home_price: float):
    """Calculate mortgage affordability"""
    interest = mortgage_rate * 0.01
    principal_loan_amount = home_price - downpayment
    monthly_interest_rate = interest / 12
    number_of_payments = 30 * 12  # 30 years
    
    if principal_loan_amount <= 0:
        monthly_payments = 0
    else:
        monthly_payments = principal_loan_amount * (
            monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments
        ) / ((1 + monthly_interest_rate) ** number_of_payments - 1)
    
    max_mortgage_budget = yearly_gross_income * 0.28 / 12
    max_debt_budget = yearly_gross_income * 0.36 / 12
    
    if monthly_payments <= max_mortgage_budget:
        affordability = "Yes"
    elif monthly_payments <= max_debt_budget:
        affordability = "Maybe"
    else:
        affordability = "No"
    
    return {
        "monthly_payments": monthly_payments,
        "max_mortgage_budget": max_mortgage_budget,
        "max_debt_budget": max_debt_budget,
        "monthly_budget": max_mortgage_budget - monthly_payments,
        "affordability": affordability
    }

def calculate_rent(yearly_gross_income: float, rent_price: float):
    """Calculate rent affordability using 30% rule"""
    max_rent_budget = yearly_gross_income * 0.30 / 12
    monthly_budget = max_rent_budget - rent_price
    
    if rent_price <= max_rent_budget:
        affordability = "Yes"
    elif rent_price <= max_rent_budget * 1.1:  # 10% tolerance
        affordability = "Maybe"
    else:
        affordability = "No"
    
    return {
        "monthly_payments": rent_price,
        "max_rent_budget": max_rent_budget,
        "monthly_budget": monthly_budget,
        "affordability": affordability
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    initialize_data()

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page for buying/owning"""
    return templates.TemplateResponse("index.html", {"request": request, "page_type": "own"})

@app.get("/rent", response_class=HTMLResponse)
async def rent_page(request: Request):
    """Rent calculator page"""
    return templates.TemplateResponse("rent.html", {"request": request, "page_type": "rent"})

@app.get("/autocomplete")
async def autocomplete_city(q: str = Query(..., min_length=1), type: str = Query("own")):
    """Autocomplete for cities (both own and rent)"""

    # Select the correct list
    if type == "rent":
        city_list = RENT_CITY_STATE_LIST
    else:
        city_list = CITY_STATE_LIST
    q_lower = q.lower()
    matches = [entry for entry in city_list if q_lower in entry.lower()]
    return JSONResponse(content=matches[:10])

@app.post("/evaluate", response_class=HTMLResponse)
async def evaluate_own(request: Request):
    """Evaluate buying affordability"""
    form = await request.form()
    
    city = form.get("city", "").strip()
    downpayment = float(form.get("downpayment", 0))
    yearly_gross_income = float(form.get("yearly_gross_income", 0))
    mortgage_rate = float(form.get("mortgage_rate", 6.8))
    home_price_custom = form.get("home_price")
    
    # Use custom price if provided, otherwise look up city price
    if home_price_custom:
        try:
            home_price = float(home_price_custom)
            city_key = city.title() if ',' not in city else city
        except ValueError:
            home_price = None
    else:
        home_price, city_key = find_city_price(city, is_rent=False)
    
    if not home_price:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "City not found. Please enter a valid city,state or use custom home price.",
            "city": city,
            "downpayment": downpayment,
            "yearly_gross_income": yearly_gross_income,
            "mortgage_rate": mortgage_rate,
            "page_type": "own"
        })
    
    results = calculate_mortgage(downpayment, yearly_gross_income, mortgage_rate, home_price)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "searched_city": city_key,
        "zestimates_average": home_price,
        "downpayment": downpayment,
        "yearly_gross_income": yearly_gross_income,
        "mortgage_rate": mortgage_rate,
        "page_type": "own",
        **results
    })

@app.post("/rent/evaluate", response_class=HTMLResponse)
async def evaluate_rent(request: Request):
    """Evaluate rent affordability"""
    form = await request.form()
    
    city = form.get("city", "").strip()
    yearly_gross_income = float(form.get("yearly_gross_income", 0))
    
    # Find rent price for city
    rent_price, city_key = find_city_price(city, is_rent=True)
    
    if not rent_price:
        return templates.TemplateResponse("rent.html", {
            "request": request,
            "error": "City not found in rent database.",
            "city": city,
            "yearly_gross_income": yearly_gross_income,
            "page_type": "rent"
        })
    
    results = calculate_rent(yearly_gross_income, rent_price)
    
    return templates.TemplateResponse("rent.html", {
        "request": request,
        "searched_city": city_key,
        "rent_price_average": rent_price, 
        "yearly_gross_income": yearly_gross_income,
        "page_type": "rent",
        **results
    })

