from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi import Query
import requests
import json
import csv
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory="html")

app.mount("/static", StaticFiles(directory="static"), name="static")

def load_city_prices_from_csv(filepath="CityHousePrices2025.csv"):
    city_prices = {}
    city_state_list = []
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            city = row["RegionName"].strip().title()
            state = row["State"].strip().upper()
            city_state_key = f"{city}, {state}"
            
            try:
                price = int(float(row["HousePriceAverage"]))
                city_prices[city_state_key] = price
                city_state_list.append(city_state_key)
            except ValueError:
                continue  # Skip bad data
    return city_prices, city_state_list

# Static city price data
CITY_PRICES, CITY_STATE_LIST = load_city_prices_from_csv()

#@app.get("/")
#async def root():
#    return {"Message" : "Hello Test"}
#http://localhost:8000/


@app.get("/autocomplete")
async def autocomplete_city(q: str = Query(..., min_length=1)):
    q_lower = q.lower()
    matches = [entry for entry in CITY_STATE_LIST if q_lower in entry.lower()]
    return JSONResponse(content=matches[:10])  # limit to top 10 matches

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html",
    )

#Simple Form v1
@app.post("/evaluate", response_class=HTMLResponse)
async def evaluate(request: Request):
    form = await request.form()
    city = form.get("city", "").strip()
    downpayment = float(form.get("downpayment", 0))
    yearly_gross_income = float(form.get("yearly_gross_income", 0))
    mortgage_rate = float(form.get("mortgage_rate", 0))
    home_price = form.get("home_price") 
    
    if home_price:
        try:
            price = float(home_price)
        except ValueError:
            price = None
    else:
        # Try to find price using city
        if ',' in city:
            city_part, state_part = [x.strip() for x in city.split(",")]
            city_key = f"{city_part.title()}, {state_part.upper()}"
            price = CITY_PRICES.get(city_key)
        else:
            matches = [key for key in CITY_PRICES if key.startswith(f"{city.title()},")]
            if matches:
                city_key = matches[0]
                price = CITY_PRICES[city_key]
            else:
                city_key = city.title()
                price = None
                
    if ',' in city:
        # Normalize city input
        try:
            city_part, state_part = [x.strip() for x in city.split(",")]
            city_key = f"{city_part.title()}, {state_part.upper()}"
        except ValueError:
            city_key = city.strip().title()
            price = CITY_PRICES.get(city_key)
    else:
    #To find first match when writing only the city name
        matches = [key for key in CITY_PRICES if key.startswith(f"{city.title()},")]
        if matches:
            city_key = matches[0]
            price = CITY_PRICES[city_key]
        else:
            city_key = city.title()
            price = None


    if not price:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "City not found.",
            "city": city
        })

    results = calculator(downpayment, yearly_gross_income, mortgage_rate, price)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "searched_city": city_key,
        "zestimates_average": price,
        "downpayment": downpayment,
        "yearly_gross_income": yearly_gross_income,
        "mortgage_rate": mortgage_rate,
        **results
    })


#Search City
@app.post("/search-city", response_class=HTMLResponse)
async def search_city(request: Request, city: str = Form(...)):
    try:
        city_part, state_part = [x.strip() for x in city.split(",")]
        city_key = f"{city_part.title()}, {state_part.upper()}"
    except ValueError:
        # Fallback if the user didn't enter a comma-separated city,state
        city_key = city.strip().title()

    price = CITY_PRICES.get(city_key)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "searched_city": city_key,
        "zestimates_average": price,
        "price_found": price is not None
    })


#Calculate Mortgage
@app.post("/calculate-mortgage", response_class=HTMLResponse)
async def calculate_mortgage(
    request: Request,
    downpayment: float = Form(...),
    yearly_gross_income: float = Form(...),
    mortgage_rate: float = Form(...),
    home_price: float = Form(...)
):
    results = calculator(downpayment, yearly_gross_income, mortgage_rate, home_price)

    return templates.TemplateResponse("index.html", {
        "request": request,
        **results,
        "downpayment": downpayment,
        "yearly_gross_income": yearly_gross_income,
        "mortgage_rate": mortgage_rate,
        "home_price": home_price
    })

zestimates_average = 0

def calculator(downpayment, yearly_gross_income, mortgage_rate, home_price):
    
    zestimates_average = home_price if home_price > 0 else 350000
    
    if mortgage_rate is None:
        mortgage_rate = 0.7

    #Mortgage Payment Formula

    # M = P * [r * (1 + r)^n] / [(1 + r)^n - 1]

    # M total monthly payment   
    # P	Principal loan amount 
    # r	Monthly interest rate  = 0.07(7%)percentage / 12 months
    # n	Number of payments over the loan’s lifetime =  30 years * 12 months = 360 payments
    
    loan_term_years = 30
    interest = mortgage_rate * 0.01
    principal_loan_amount = zestimates_average - downpayment
    monthly_interest_rate = interest / 12 
    number_of_payments = loan_term_years * 12

    monthly_payments = principal_loan_amount * (monthly_interest_rate*(1+monthly_interest_rate)**number_of_payments)/((1+monthly_interest_rate)**number_of_payments-1)

    max_mortgage_budget = yearly_gross_income * 0.28 / 12
    max_debt_budget = yearly_gross_income * 0.36 / 12

    if monthly_payments <= max_mortgage_budget:
        affordability = "Yes"
    elif monthly_payments <= max_debt_budget:
        affordability = "Maybe"
    else: 
        affordability = "No"

    print("~ Monthly Payment: ${:.2f}, House Price: ${}, with a downpayment of: ${:.2f}".format(monthly_payments, int(zestimates_average), downpayment))

    print("~ Following the 28/36 Rule you can afford a monthly payment of: {:.2f}, as long as you don't have more than {:.2f} on monthly payments debt (e.g. Car Loans)".format(max_mortgage_budget, max_debt_budget - max_mortgage_budget))
    print("~ Your Monthly Budget is: ${:.2f} - ${:.2f} = ${:.2f}".format(monthly_payments,max_mortgage_budget,monthly_payments-max_mortgage_budget))
    
    return {
    "monthly_payments": monthly_payments,
    "max_mortgage_budget": max_mortgage_budget,
    "max_debt_budget": max_debt_budget,
    "monthly_budget": max_mortgage_budget - monthly_payments,
    "zestimates_average": zestimates_average,
    "affordability": affordability
    }
