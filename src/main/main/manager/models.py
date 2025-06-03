from pydantic import BaseModel


class UsersPost(BaseModel):
    username: str
    email: str
    password: str


class ProductsPost(BaseModel):
    product_name: str
    price: int
    count: int
    sales: int

class OrderPost(BaseModel):
    user_id: int
    product_id: int
    quantity: int
