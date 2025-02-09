from datetime import datetime
from fastapi import FastAPI, HTTPException
from Server_.Exchanges import EXCHANGE_MAPPING

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

if __name__ == "__main__":
    # Launch server here in local on port 8000
    import uvicorn
    uvicorn.run("Server:app", host="0.0.0.0", port=8000, reload=True)