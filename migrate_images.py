import os, json
os.environ['DATABASE_URL'] = 'mysql+pymysql://freelance_user:Kipkoech%402006@taw-freelance-db.mysql.database.azure.com:3306/freelance_marketplace?ssl=true&ssl_verify_cert=false'
os.environ['SECRET_KEY'] = 'temp-key'
from app import app, db
from models import Service, ServiceImage
with app.app_context():
    # Migrate all services with image_filenames JSON but no ServiceImage rows
    services = Service.query.all()
    for s in services:
        if s.image_filenames:
            existing = ServiceImage.query.filter_by(service_id=s.id).count()
            if existing == 0:
                try:
                    filenames = json.loads(s.image_filenames)
                    for fname in filenames:
                        if fname:
                            img = ServiceImage(service_id=s.id, filename=fname)
                            db.session.add(img)
                    db.session.commit()
                    print(f"Migrated service {s.id} '{s.title}': {filenames}")
                except Exception as e:
                    print(f"Error service {s.id}: {e}")
    print("done")
