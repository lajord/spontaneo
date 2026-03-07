import asyncio
from app.recuperation_data.google_places import google_places_service

async def main():
    print("Testing Google Places API New Integration...")
    results = await google_places_service.search_with_radius(
        query="Boulangerie",
        lat=48.8566, # Paris
        lng=2.3522,
        radius_m=1000 # 1km
    )

    print(f"\nFound {len(results)} results.")
    for r in results[:3]:
        print("-", r.get("nom"), "||", r.get("telephone"), "||", r.get("site_web"))

if __name__ == "__main__":
    asyncio.run(main())
