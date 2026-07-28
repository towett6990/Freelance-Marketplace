import os
os.environ['DATABASE_URL'] = 'mysql+pymysql://freelance_user:Kipkoech%402006@taw-freelance-db.mysql.database.azure.com:3306/freelance_marketplace?ssl=true&ssl_verify_cert=false'
os.environ['SECRET_KEY'] = 'temp-key'
from app import app, db
from models import Service, ServiceImage
with app.app_context():
    s = Service.query.get(6)
    if s:
        imgs = ServiceImage.query.filter_by(service_id=6).all()
        print(f"Service 6 '{s.title}':")
        print(f"  image_filenames: {s.image_filenames}")
        print(f"  ServiceImage rows: {[i.filename for i in imgs]}")
    else:
        print("Service 6 not found")
        for svc in Service.query.all():
            print(f"  Service {svc.id}: {svc.title}")
