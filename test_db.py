from FastAPIApplication.database import session_local
from FastAPIApplication.models import Product
from sqlalchemy import func
from datetime import datetime

db = session_local()
try:
    max_id = db.query(func.max(Product.id)).scalar() or 0
    new_id = int(max_id) + 1
    
    new_product = Product(
        id=new_id,
        name='Test Name',
        price='1000',
        source='Source',
        specifications='Specs',
        category='Category',
        unit='Cái',
        appraisal_date=datetime.now().strftime("%d/%m/%Y"),
        appraiser="AI System",
        certificate_number="AI-" + datetime.now().strftime("%Y%m%d%H%M")
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    print("Success:", new_product.id)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
