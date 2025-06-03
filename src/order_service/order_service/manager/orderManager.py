import asyncpg

class OrderDataBase:
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
    

    async def get_all_products(self):
        query = """
        SELECT * FROM products;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        
    async def post_new_order(self, user_id, product_id, quantity):
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    product_query = "SELECT count FROM products WHERE id = $1 FOR UPDATE;"
                    product = await conn.fetchrow(product_query, product_id)

                    if not product:
                        return {"error": "Product not found"}

                    current_count = product["count"]
                    if current_count < quantity:
                        return {"error": "Not enough stock"}

                    update_query = """
                    UPDATE products SET count = count - $1 WHERE id = $2;
                    """
                    await conn.execute(update_query, quantity, product_id)

                    insert_query = """
                    INSERT INTO orders (user_id, product_id, quantity)
                    VALUES ($1, $2, $3)
                    RETURNING *;
                    """
                    order = await conn.fetchrow(insert_query, user_id, product_id, quantity)

                    return order

        except Exception as e:
            print(f"[DB ERROR] post_new_order: {e}")
            return {"error": "Failed to insert order"}

    

    async def get_all_orders(self):
        query = """
        SELECT * FROM orders;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        
    