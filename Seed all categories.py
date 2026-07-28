"""
seed_all_categories.py
Run ONCE from your project root:  python seed_all_categories.py
Creates / updates all 6 marketplace categories.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, db
from models import Category

CATEGORIES = [

  # ── 1. WEB DEVELOPMENT ────────────────────────────────────────────────
  {
    "name": "Web Development", "slug": "web-development",
    "description": "Hire skilled freelance web developers",
    "icon": "code", "layout_type": "freelancer", "price_type": "hourly",
    "custom_fields": [
      {"name":"skills","label":"Skills","type":"multi-select","required":True,
       "options":["React","Vue.js","Angular","Node.js","Python","Django","PHP","Laravel",
                  "TypeScript","JavaScript","AWS","MongoDB","PostgreSQL","MySQL","WordPress","GraphQL"]},
      {"name":"hourly_rate","label":"Hourly Rate (KES)","type":"number","required":True,"min":0,"max":99999,"placeholder":"e.g. 2500"},
      {"name":"experience_level","label":"Experience Level","type":"select","required":True,
       "options":["Beginner","Intermediate","Expert"]},
      {"name":"years_experience","label":"Years of Experience","type":"number","required":False,"min":0,"max":50,"placeholder":"e.g. 5"},
      {"name":"portfolio_url","label":"Portfolio URL","type":"text","required":False,"placeholder":"https://github.com/username"},
      {"name":"availability","label":"Availability","type":"select","required":False,
       "options":["Full-time","Part-time","Weekends Only","Flexible"]},
      {"name":"project_types","label":"Project Types","type":"multi-select","required":False,
       "options":["Web Apps","Mobile Apps","APIs","E-commerce","CMS","UI/UX Design","DevOps","Consulting"]},
    ],
    "card_fields":   ["skills","hourly_rate","experience_level","years_experience"],
    "detail_fields": ["skills","hourly_rate","experience_level","years_experience","portfolio_url","availability","project_types"],
    "available_filters": ["price","rating","experience_level","skills","availability"],
  },

  # ── 2. CAR SALES ──────────────────────────────────────────────────────
  {
    "name": "Car Sales", "slug": "car-sales",
    "description": "Buy and sell new and used cars across Kenya",
    "icon": "car", "layout_type": "product", "price_type": "fixed",
    "custom_fields": [
      {"name":"brand","label":"Brand","type":"select","required":True,
       "options":["Toyota","Honda","Mazda","Nissan","Mitsubishi","Subaru","Mercedes-Benz","BMW","Audi","Volkswagen","Ford","Hyundai","Kia","Isuzu","Land Rover","Other"]},
      {"name":"model","label":"Model","type":"text","required":True,"placeholder":"e.g. Camry, Axio"},
      {"name":"year","label":"Year","type":"number","required":True,"min":1990,"max":2025,"placeholder":"e.g. 2019"},
      {"name":"mileage","label":"Mileage (km)","type":"number","required":False,"min":0,"max":999999,"placeholder":"e.g. 45000"},
      {"name":"condition","label":"Condition","type":"select","required":True,
       "options":["Brand New","Very Good","Good","Fair"]},
      {"name":"body_type","label":"Body Type","type":"select","required":False,
       "options":["Sedan","SUV","Hatchback","Pickup/Truck","Van","Bus","Coupe","Station Wagon"]},
      {"name":"transmission","label":"Transmission","type":"select","required":False,"options":["Automatic","Manual"]},
      {"name":"fuel_type","label":"Fuel Type","type":"select","required":False,"options":["Petrol","Diesel","Hybrid","Electric","LPG"]},
      {"name":"engine_cc","label":"Engine Capacity (cc)","type":"number","required":False,"min":0,"max":9999,"placeholder":"e.g. 2000"},
      {"name":"color","label":"Color","type":"text","required":False,"placeholder":"e.g. Pearl White"},
      {"name":"registration","label":"Registration Status","type":"select","required":False,"options":["Registered","Not Registered","Foreign"]},
      {"name":"features","label":"Features","type":"multi-select","required":False,
       "options":["Air Conditioning","Power Windows","Power Steering","ABS","Airbags","Reverse Camera","Sunroof","Leather Seats","Alloy Wheels","Navigation/GPS","Bluetooth","Keyless Entry"]},
    ],
    "card_fields":   ["brand","model","year","mileage","condition"],
    "detail_fields": ["brand","model","year","mileage","condition","body_type","transmission","fuel_type","engine_cc","color","registration","features"],
    "available_filters": ["price","brand","year","mileage","condition","body_type","transmission","fuel_type"],
  },

  # ── 3. REAL ESTATE ────────────────────────────────────────────────────
  {
    "name": "Real Estate", "slug": "real-estate",
    "description": "Houses, apartments and land for sale or rent",
    "icon": "building", "layout_type": "property", "price_type": "negotiable",
    "custom_fields": [
      {"name":"property_type","label":"Property Type","type":"select","required":True,
       "options":["Apartment","House","Townhouse","Villa","Land","Commercial","Office","Warehouse","Studio"]},
      {"name":"listing_type","label":"Listing Type","type":"select","required":True,"options":["For Sale","For Rent","Short Stay"]},
      {"name":"bedrooms","label":"Bedrooms","type":"select","required":False,"options":["Studio","1","2","3","4","5","6+"]},
      {"name":"bathrooms","label":"Bathrooms","type":"select","required":False,"options":["1","2","3","4","5+"]},
      {"name":"area_sqm","label":"Area (sq meters)","type":"number","required":False,"min":0,"max":99999,"placeholder":"e.g. 150"},
      {"name":"location_city","label":"City","type":"select","required":True,
       "options":["Nairobi","Mombasa","Kisumu","Nakuru","Eldoret","Thika","Machakos","Nyeri","Meru","Other"]},
      {"name":"neighborhood","label":"Neighborhood","type":"text","required":False,"placeholder":"e.g. Kileleshwa, Westlands"},
      {"name":"building_status","label":"Building Status","type":"select","required":False,"options":["Complete","Under Construction","Off Plan"]},
      {"name":"furnished","label":"Furnished Status","type":"select","required":False,"options":["Furnished","Semi-Furnished","Unfurnished"]},
      {"name":"amenities","label":"Amenities","type":"multi-select","required":False,
       "options":["Swimming Pool","Gym","Security/Guard","CCTV","Parking","Generator","Borehole","Garden","Balcony","Lift/Elevator","Rooftop","Servant Quarter"]},
      {"name":"lease_duration","label":"Lease Duration","type":"select","required":False,"options":["Monthly","6 Months","1 Year","2 Years","Negotiable"]},
    ],
    "card_fields":   ["property_type","listing_type","bedrooms","bathrooms","area_sqm","location_city"],
    "detail_fields": ["property_type","listing_type","bedrooms","bathrooms","area_sqm","location_city","neighborhood","building_status","furnished","amenities","lease_duration"],
    "available_filters": ["price","property_type","listing_type","bedrooms","location_city","furnished"],
  },

  # ── 4. ELECTRONICS ────────────────────────────────────────────────────
  {
    "name": "Electronics", "slug": "electronics",
    "description": "Phones, laptops, TVs and gadgets",
    "icon": "laptop", "layout_type": "product", "price_type": "fixed",
    "custom_fields": [
      {"name":"brand","label":"Brand","type":"select","required":True,
       "options":["Apple","Samsung","Sony","LG","Huawei","Xiaomi","Oppo","Tecno","Infinix","HP","Dell","Lenovo","Asus","Acer","Canon","JBL","Bose","Other"]},
      {"name":"model","label":"Model","type":"text","required":True,"placeholder":"e.g. iPhone 14 Pro Max"},
      {"name":"category","label":"Device Type","type":"select","required":True,
       "options":["Smartphone","Laptop","Tablet","Desktop","TV","Monitor","Camera","Headphones","Speaker","Printer","Game Console","Smartwatch","Other"]},
      {"name":"condition","label":"Condition","type":"select","required":True,"options":["Brand New","Like New","Good","Fair"]},
      {"name":"storage","label":"Storage","type":"select","required":False,"options":["16GB","32GB","64GB","128GB","256GB","512GB","1TB","Other"]},
      {"name":"ram","label":"RAM","type":"select","required":False,"options":["2GB","4GB","6GB","8GB","12GB","16GB","32GB","Other"]},
      {"name":"screen_size","label":"Screen Size","type":"text","required":False,"placeholder":"e.g. 6.7 inch"},
      {"name":"color","label":"Color","type":"text","required":False,"placeholder":"e.g. Space Black"},
      {"name":"processor","label":"Processor","type":"text","required":False,"placeholder":"e.g. A16 Bionic, Intel i7"},
      {"name":"warranty","label":"Warranty","type":"select","required":False,
       "options":["No Warranty","1 Month","3 Months","6 Months","1 Year","2 Years","Manufacturer Warranty"]},
      {"name":"accessories","label":"Included Accessories","type":"multi-select","required":False,
       "options":["Original Box","Charger","Case","Screen Protector","Earphones","Manual","Receipt/Invoice"]},
    ],
    "card_fields":   ["brand","model","category","condition","warranty"],
    "detail_fields": ["brand","model","category","condition","storage","ram","screen_size","color","processor","warranty","accessories"],
    "available_filters": ["price","brand","category","condition","warranty","storage"],
  },

  # ── 5. CLOTHING ───────────────────────────────────────────────────────
  {
    "name": "Clothing", "slug": "clothing",
    "description": "Fashion, clothes, shoes and accessories",
    "icon": "tshirt", "layout_type": "product", "price_type": "fixed",
    "custom_fields": [
      {"name":"brand","label":"Brand","type":"text","required":False,"placeholder":"e.g. Nike, Zara, H&M"},
      {"name":"category","label":"Category","type":"select","required":True,
       "options":["T-Shirts","Shirts","Pants/Jeans","Dresses","Skirts","Jackets/Coats","Shoes","Sneakers","Boots","Sandals","Bags","Accessories","Underwear/Socks","Sportswear","Suits","Kids Clothing"]},
      {"name":"condition","label":"Condition","type":"select","required":True,"options":["Brand New","Like New","Good","Fair"]},
      {"name":"size","label":"Size","type":"select","required":True,
       "options":["XS","S","M","L","XL","XXL","XXXL","One Size","EU 36","EU 37","EU 38","EU 39","EU 40","EU 41","EU 42","EU 43","EU 44","EU 45"]},
      {"name":"color","label":"Color","type":"text","required":False,"placeholder":"e.g. Navy Blue"},
      {"name":"material","label":"Material","type":"select","required":False,"options":["Cotton","Polyester","Silk","Wool","Linen","Denim","Leather","Synthetic","Mixed"]},
      {"name":"gender","label":"Gender","type":"select","required":True,"options":["Men","Women","Unisex","Boys","Girls","Baby"]},
      {"name":"quantity","label":"Qty Available","type":"number","required":False,"min":1,"max":9999,"placeholder":"e.g. 1"},
    ],
    "card_fields":   ["brand","category","size","color","condition","gender"],
    "detail_fields": ["brand","category","condition","size","color","material","gender","quantity"],
    "available_filters": ["price","brand","category","condition","size","gender","material"],
  },

  # ── 6. OTHER ──────────────────────────────────────────────────────────
  {
    "name": "Other", "slug": "other",
    "description": "General services, products and everything else",
    "icon": "th-large", "layout_type": "generic", "price_type": "negotiable",
    "custom_fields": [
      {"name":"sub_category","label":"Sub-Category","type":"text","required":False,"placeholder":"e.g. Furniture, Books, Pets"},
      {"name":"condition","label":"Condition","type":"select","required":False,"options":["New","Like New","Good","Fair","For Parts"]},
      {"name":"location","label":"Location","type":"text","required":False,"placeholder":"e.g. Nairobi CBD"},
      {"name":"price_type","label":"Price Type","type":"select","required":False,"options":["Fixed","Negotiable","Free","Exchange/Swap"]},
    ],
    "card_fields":   ["sub_category","condition","location"],
    "detail_fields": ["sub_category","condition","location","price_type"],
    "available_filters": ["price","rating"],
  },
]

def seed():
    with app.app_context():
        created = updated = 0
        for data in CATEGORIES:
            cat = Category.query.filter_by(slug=data["slug"]).first()
            if cat:
                for k, v in data.items():
                    setattr(cat, k, v)
                updated += 1
                print(f"  ↻  Updated : {data['name']}")
            else:
                db.session.add(Category(**data))
                created += 1
                print(f"  ✅ Created : {data['name']}")
        db.session.commit()
        print(f"\n✅ Done — {created} created, {updated} updated.\n")

if __name__ == "__main__":
    seed()