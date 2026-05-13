from database import base
from sqlalchemy import Column, Integer, String


class QAA(base):
    __tablename__ = 'QAA'

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String)
    answer = Column(String)


class Product(base):
    __tablename__ = 'danh_muc_vat_tu'

    id = Column('STT', Integer, primary_key=True, index=True)
    category = Column('Loại hàng hóa', String)
    name = Column('Tên hàng hóa', String, index=True)
    unit = Column('Đơn vị tính', String)
    specifications = Column('Thông số kỹ thuật', String)
    price = Column('Giá thẩm định(VND)', String)
    certificate_number = Column('Chứng thư thẩm định số', String)
    appraisal_date = Column('Ngày thẩm định', String)
    source = Column('Nguồn dữ liệu', String)
    appraiser = Column('Người thẩm định', String)

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