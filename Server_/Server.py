import os.path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from sympy import jacobi_symbol

from Server_.Exchanges import EXCHANGE_MAPPING
from Server_.Database import *
from Authentification.AuthentificationManager import *

app = FastAPI(title="Twap-Trading-API")

@app.get("/")
async def root():
    return {"message": "Welcome to the Twap-Trading-API"}

@app.get("/exchanges")
async def get_exchanges():
    return {"exchanges": list(EXCHANGE_MAPPING.keys())}

@app.get("/{exchange}/symbols")
async def get_symbols(exchange: str):
    if exchange not in list(EXCHANGE_MAPPING.keys()):
        raise HTTPException(status_code=404, detail="Exchange not available")
    else:
        exchange_object = EXCHANGE_MAPPING[exchange]
        return {"symbols": list(exchange_object.get_trading_pairs().keys())}

@app.get("/klines/{exchange}/{symbol}")
async def get_historical_data(exchange: str, symbol: str, interval: str, start_time: str, end_time: str):
    if exchange not in list(EXCHANGE_MAPPING.keys()):
        raise HTTPException(status_code=404, detail="Exchange not available")
    else:
        exchange_object = EXCHANGE_MAPPING[exchange]
        available_symbols = list(exchange_object.get_trading_pairs().keys())
        if symbol not in available_symbols:
            raise HTTPException(status_code=404, detail="Trading pair not available on this exchange")
        else:
            start_time_dt = datetime.fromisoformat(start_time)
            end_time_dt = datetime.fromisoformat(end_time)
            klines_df = await exchange_object.get_klines_data(symbol, interval, start_time_dt, end_time_dt)

            return {"klines": klines_df.to_dict(orient="index")}


'''Authentification'''

@app.post("/login",response_model = TokenResponse)
async def login(request: LoginRequest):

    user = database_api.retrieve_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401,detail="Invalid username")

    if user.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(request.username)
    return {"access_token":token}

@app.get("/secure")
async def secure_endpoint(username: str = Depends(verify_token)):
    """Protected endpoint requires valid JWT"""
    return {
        "message" : f"Hello {username}! This is secure data",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/register",status_code = 201)
async def register(request: RegisterRequest):
    user = database_api.retrieve_user_by_username(request.username)
    if user:
        raise HTTPException(status_code=400, detail="Username already exists")

    database_api.create_user(request.username,request.password, "user")
    return {"message": "User correctly registered"}


if __name__ == "__main__":
    # Launch server here in local on port 8000
    import uvicorn
    uvicorn.run("Server:app", host="0.0.0.0", port=8000, reload=True)