import os, json
os.environ['DATABASE_URL'] = 'mysql+pymysql://freelance_user:Kipkoech%402006@taw-freelance-db.mysql.database.azure.com:3306/freelance_marketplace?ssl=true&ssl_verify_cert=false'
os.environ['SECRET_KEY'] = 'temp-key'
from app import app, db
from models import Service, ServiceImage
with app.app_context():
    s = db.session.get(Service, 7)
    imgs = ServiceImage.query.filter_by(service_id=7).all()
    print(f"Service 7 '{s.title}':")
    print(f"  category: {s.category_old}")
    print(f"  image_filenames JSON: {s.image_filenames}")
    print(f"  ServiceImage table: {[i.filename for i in imgs]}")
    print(f"  image_list: {s.image_list}")
