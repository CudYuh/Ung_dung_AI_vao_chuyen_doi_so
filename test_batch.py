import asyncio
from FastAPIApplication.routers.valuation_api import _process_single_product

async def main():
    res = await _process_single_product("iPhone 13")
    print("RESULT:", res)

asyncio.run(main())
