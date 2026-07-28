import os
os.environ['DATABASE_URL'] = 'mysql+pymysql://freelance_user:Kipkoech%402006@taw-freelance-db.mysql.database.azure.com:3306/freelance_marketplace?ssl=true&ssl_verify_cert=false'
os.environ['SECRET_KEY'] = 'temp-key'
from app import app, db
from models import Service, ServiceImage
with app.app_context():
    s = db.session.get(Service, 12)
    imgs = ServiceImage.query.filter_by(service_id=12).all()
    print(f"Service 12: {s.title}")
    print(f"image_filenames JSON: {s.image_filenames}")
    print(f"ServiceImage table: {[i.filename for i in imgs]}")
    print(f"image_list: {s.image_list}")
