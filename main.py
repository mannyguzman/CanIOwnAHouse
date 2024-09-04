from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import json


app = FastAPI()

#C:\Users\manue\OneDrive\Documents\GitHub\WebAppTest\main.py

templates = Jinja2Templates(directory="html")

#@app.get("/")
#async def root():
#    return {"Message" : "Hello Test"}

#http://localhost:8000/

#ssh -i "MortCalculatorKey.pem" ec2-user@ec2-44-211-45-80.compute-1.amazonaws.com
#sudo su

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html",
    )

@app.post("/", response_class=HTMLResponse)
async def calculate_mortgage(
    request: Request,
    downpayment: float = Form(...),
    yearly_gross_income: float = Form(...)
):
    results = calculator(downpayment, yearly_gross_income)
    # aws - elastic beanstalk, ecs - load balancer, route 53
    # free tier - biling alerts - setup



    context = { 
        "request": request,
        "downpayment": downpayment,
        "yearly_gross_income": yearly_gross_income,
        "zestimates_average": zestimates_average,
    }

    context2 = context|results

    return templates.TemplateResponse("index.html", context2)

"""""
url = "https://zillow56.p.rapidapi.com/similar_sold_properties"


querystring = {"url":"https://www.zillow.com/homedetails/1930-S-Camac-St-Philadelphia-PA-19148/10395836_zpid/"}
#querystring = {"zpid":"28253016"}
#querystring = {"address":"1541 S Lambert St, Philadelphia, PA 19146"}

headers = {
	"x-rapidapi-key": "78805643a2msh5773e83c3fbdce7p1b0570jsnf6955db9e069",
	"x-rapidapi-host": "zillow56.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

#print("~ RAW JSON DATA ~")
#print(response.json())

data = response.json()

zestimates = [result['property']['zestimate'] for result in data['results']]
#zestimates = (['$404,000', '$329,200', '$325,300', '$399,800', '$333,600'])


def Average(zestimates): 
    return sum(zestimates) / len(zestimates)

zestimates_average =  Average(zestimates)
"""""

zestimates_average = 350000

#print("~ Zestimates: ~")
#print(zestimates)

print("~ Zestimates Average: ~")
print(zestimates_average)

#print("['$404,000', '$329,200', '$325,300', '$399,800', '$333,600']")

# Prompt for user for input
#downpayment = int(input("Enter how much you can put as Downpayment: "))
#yearly_gross_income = int(input("Enter your Yearly Gross Income "))

#downpayment = 50000
#yearly_gross_income = 150000

#input = {
#    "downpayment" : downpayment,
#     "yearly_gross_income" :  yearly_gross_income



def calculator(downpayment, yearly_gross_income):

    #Mortgage Payment Formula

    # M = P * [r * (1 + r)^n] / [(1 + r)^n - 1]

    # M total monthly payment   
    # P	Principal loan amount 
    # r	Monthly interest rate  = 0.07(7%)percentage / 12 months
    # n	Number of payments over the loan’s lifetime =  30 years * 12 months = 360 payments

    loan_term_years = 30
    interest = 0.07
    principal_loan_amount = zestimates_average - downpayment
    monthly_interest_rate = interest / 12 
    number_of_payments = loan_term_years * 12

    monthly_payments = principal_loan_amount * (monthly_interest_rate*(1+monthly_interest_rate)**number_of_payments)/((1+monthly_interest_rate)**number_of_payments-1)

    max_mortgage_budget = yearly_gross_income * 0.28 / 12
    max_debt_budget = yearly_gross_income * 0.36 / 12


    print("~ Monthly Payment: ${:.2f}, House Price: ${}, with a downpayment of: ${:.2f}".format(monthly_payments, int(zestimates_average), downpayment))

    print("~ Following the 28/36 Rule you can afford a monthly payment of: {:.2f}, as long as you don't have more than {:.2f} on monthly payments debt (e.g. Car Loans)".format(max_mortgage_budget, max_debt_budget - max_mortgage_budget))
    print("~ Your Monthly Budget is: ${:.2f} - ${:.2f} = ${:.2f}".format(monthly_payments,max_mortgage_budget,monthly_payments-max_mortgage_budget))
    
    return {
            "monthly_payments": monthly_payments,
            "max_mortgage_budget": max_mortgage_budget,
            "max_debt_budget": max_debt_budget,
            "monthly_budget": max_mortgage_budget - monthly_payments,
        }
