import asyncpg

class ProductsDataBase:
    def __init__(self):
        self.pool = None

    async def connect(self, conn_string):
        try:
            self.pool = await asyncpg.create_pool(conn_string)
            if self.pool is not None:
                print(f"[SUCCESS] Connection to DB")
        except Exception as e:
            print(f"[ERROR] Error connecting to database: {e}")
            raise ConnectionError(f"[ERROR] Error connecting to database: {e}")

    async def disconnect(self):
        await self.pool.close()


    async def get_all_users(self):
        query = """
        SELECT * FROM users;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        
    async def post_new_product(self, product_name, price, count, sales):
        query = """
        INSERT INTO products (product_name, price, count, sales)
        VALUES ($1, $2, $3, $4)
        RETURNING *;
        """
        try:
            return await self.pool.fetchrow(query, product_name, price, count, sales)
        except Exception as e:
            print(f"[DB ERROR] post_new_product: {e}")
            return {"error": "Failed to insert products"}

    async def get_all_products(self):
        query = """
        SELECT * FROM products;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        
    

    async def get_all_orders(self):
        query = """
        SELECT * FROM orders;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        
    