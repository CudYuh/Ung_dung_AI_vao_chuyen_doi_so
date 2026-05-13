from database import base
from sqlalchemy import Column, Integer, String


class QAA(base):
    __tablename__ = 'QAA'

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String)
    answer = Column(String)


class Product(base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True) # STT
    category = Column(String) # Loại hàng hóa
    name = Column(String, index=True) # Tên hàng hóa
    unit = Column(String) # Đơn vị tính
    specifications = Column(String) # Thông số kỹ thuật
    price = Column(String) # Giá thẩm định(VND)
    certificate_number = Column(String) # Chứng thư thẩm định số
    appraisal_date = Column(String) # Ngày thẩm định
    source = Column(String) # Nguồn dữ liệu
    appraiser = Column(String) # Người thẩm định

"""
INSIDE THE SQL DATABASE HERE IS THE EXACT DATA YOU WOULD WANT TO REPLICATE

DROP TABLE IF EXISTS QAA;

CREATE TABLE QAA (
	id SERIAL,
	question varchar(2000) DEFAULT NULL,
	answer varchar(2000) DEFAULT NULL,
	PRIMARY KEY (id)
);

"""