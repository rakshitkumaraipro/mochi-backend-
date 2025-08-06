import json
from datetime import date, datetime
from typing import List, Dict, Optional
from collections import defaultdict
import random

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# --- Pydantic Models for Data Structure and Validation ---

class Transaction(BaseModel):
    """Represents a single financial transaction."""
    date: date
    description: str
    amount: float
    type: str  # "debit" or "credit"
    category: str
    payment_method: str = Field(..., alias="payment_method")

class SummaryResponse(BaseModel):
    """Data model for the analytics summary endpoint."""
    mascot_name: str = "Mochi the Fox"
    total_spend: float
    total_income: float
    net_flow: float
    spend_by_category: Dict[str, float]
    monthly_burn_rate_projection: float
    money_left_from_income: float
    days_until_broke_projection: Optional[int]
    period_days: int

class Tip(BaseModel):
    """A single actionable savings tip."""
    title: str
    suggestion: str
    emoji: str

class TipsResponse(BaseModel):
    """Data model for the AI-powered tips endpoint."""
    mascot_name: str = "Mochi the Fox"
    daily_dopamine_boost: str
    personalized_tips: List[Tip]


# --- In-memory "Database" ---
# This dictionary will hold our application's state, loaded at startup.
app_state = {
    "transactions": []
}

# --- Lifespan Management (Startup/Shutdown Events) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    On startup, it loads the mock transaction data into memory.
    """
    print("🦊 App starting up! Loading transaction data...")
    try:
        with open("mock_transactions.json", "r") as f:
            transactions_data = json.load(f)
            # Use Pydantic to parse and validate data on load
            app_state["transactions"] = [Transaction(**t) for t in transactions_data]
        print(f"✅ Loaded {len(app_state['transactions'])} transactions successfully.")
    except FileNotFoundError:
        print("⚠️ WARNING: mock_transactions.json not found. The app will run with no data.")
        app_state["transactions"] = []
    except Exception as e:
        print(f"🚨 ERROR: Failed to load or parse mock_transactions.json: {e}")
        app_state["transactions"] = []
    
    yield  # The application runs while the lifespan context is active
    
    print("🦊 App shutting down. Clearing state...")
    app_state.clear()


# --- FastAPI App Initialization ---

app = FastAPI(
    title="Gen-Z Finance Buddy API",
    description="The backend for a cute, AI-powered financial wellness app.",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS (Cross-Origin Resource Sharing) to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Helper Functions for Analytics ---

def calculate_analytics(transactions: List[Transaction]):
    """Calculates core analytics from a list of transactions."""
    if not transactions:
        return 0, 0, {}, 0
        
    total_spend = sum(t.amount for t in transactions if t.type == 'debit')
    total_income = sum(t.amount for t in transactions if t.type == 'credit')
    
    spend_by_category = defaultdict(float)
    for t in transactions:
        if t.type == 'debit':
            spend_by_category[t.category] += t.amount
            
    first_date = min(t.date for t in transactions)
    last_date = max(t.date for t in transactions)
    period_days = (last_date - first_date).days + 1  # Inclusive of the first day
    
    return total_spend, total_income, dict(spend_by_category), period_days


# --- API Endpoints ---

@app.get("/transactions", response_model=List[Transaction])
async def get_all_transactions():
    """
    Retrieves all transactions from the mock data.
    This is the raw data feed for the frontend.
    """
    return app_state["transactions"]

@app.get("/summary", response_model=SummaryResponse)
async def get_summary(monthly_income: float = Query(..., gt=0, description="User's total monthly income.")):
    """
    Provides a detailed financial summary based on transaction data and user's income.
    This endpoint powers the main analytics dashboard.
    """
    transactions = app_state["transactions"]
    if not transactions:
        raise HTTPException(status_code=404, detail="No transaction data available to generate a summary.")

    total_spend, total_income, spend_by_category, period_days = calculate_analytics(transactions)

    daily_spend_rate = total_spend / period_days if period_days > 0 else 0
    monthly_burn_rate = daily_spend_rate * 30
    
    money_left = monthly_income - total_spend
    
    days_left = None
    if daily_spend_rate > 0:
        days_left = int(money_left / daily_spend_rate) if money_left > 0 else 0

    return SummaryResponse(
        total_spend=round(total_spend, 2),
        total_income=round(total_income, 2),
        net_flow=round(total_income - total_spend, 2),
        spend_by_category={k: round(v, 2) for k, v in spend_by_category.items()},
        monthly_burn_rate_projection=round(monthly_burn_rate, 2),
        money_left_from_income=round(money_left, 2),
        days_until_broke_projection=days_left,
        period_days=period_days
    )

@app.get("/tips", response_model=TipsResponse)
async def get_savings_tips():
    """
    Generates AI-powered, personalized savings tips and a dopamine boost message.
    This endpoint delivers the cute, actionable advice to the user.
    """
    transactions = app_state["transactions"]
    if not transactions:
        raise HTTPException(status_code=404, detail="No transaction data available to generate tips.")

    _, _, spend_by_category, _ = calculate_analytics(transactions)
    
    dopamine_boosts = [
        "You're doing amazing! Every small step is a huge win. ✨",
        "Look at you, taking control of your finances! We love to see it. 💖",
        "Keep slaying! Your future self will thank you for this. 🚀",
        "Remember, you got this! One good choice at a time. 😊",
        "Building good habits is a superpower. You're a hero! 🦸"
    ]

    tips = []
    
    # Sort categories by spending, highest first
    sorted_spend = sorted(spend_by_category.items(), key=lambda item: item[1], reverse=True)

    # Generate a tip for the top spending category
    if sorted_spend:
        top_category, top_amount = sorted_spend[0]
        if top_category == "Food Delivery":
            tips.append(Tip(
                title=f"Level-Up Your Kitchen Game!",
                suggestion=f"You're a top foodie, spending ₹{top_amount:.0f} on deliveries! Try cooking one meal at home this week to save big and feel like a chef.",
                emoji="🍳"
            ))
        elif top_category == "Shopping":
            tips.append(Tip(
                title="Master the 24-Hour Rule",
                suggestion=f"That shopping haul looks great! Next time you see something you love, try waiting 24 hours before buying. It's a secret trick to avoid impulse buys.",
                emoji="🛍️"
            ))
        elif top_category == "Going Out":
            tips.append(Tip(
                title="Pre-Game Like a Pro",
                suggestion=f"Fun nights out are the best! You could save a bit by having a drink at home before you head out. Your wallet will be just as happy as you are!",
                emoji="🥂"
            ))

    # Specific tip for 'Sutta' or 'Coffee' if present
    if "Sutta" in spend_by_category:
        amount = spend_by_category["Sutta"]
        monthly_saving = (amount / len(transactions) * 0.75) * 30 # Rough projection
        tips.append(Tip(
            title="Power-Up Your Health & Wallet",
            suggestion=f"Cutting back on just one sutta a day could save you over ₹{monthly_saving:.0f} a month. Imagine what you could do with that!",
            emoji="💪"
        ))
    
    if "Coffee" in spend_by_category and spend_by_category['Coffee'] > 200:
        tips.append(Tip(
            title="Become Your Own Barista",
            suggestion=f"Your coffee game is strong! Making your own brew a few times a week is not only fun but could easily save you hundreds. You got this!",
            emoji="☕"
        ))
        
    # Add a generic, positive tip
    tips.append(Tip(
        title="Check Your Subscriptions",
        suggestion="Do a quick check of your subscriptions like Netflix, etc. Sometimes we forget what we're paying for! A quick cleanup can unlock easy savings.",
        emoji="📺"
    ))

    return TipsResponse(
        daily_dopamine_boost=random.choice(dopamine_boosts),
        personalized_tips=tips[:3]  # Return the top 3 most relevant tips
    )

# --- To run the server locally ---
# Command: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    print("Starting server at http://127.0.0.1:8000")
    print("Swagger UI available at http://127.0.0.1:8000/docs")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)