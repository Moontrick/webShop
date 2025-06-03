import asyncpg

class OutBoxDataBase:
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

    async def insert_new_request(self,
                                 cid,
                                 request_type,
                                 request_data):
        query = """
        INSERT INTO public.outbox (cid, request_type, request_data, status_request)
        VALUES ($1, $2, $3, $4)
        """
        try:
            await self.pool.execute(query, cid, request_type, request_data, 'new')
            return True
        except asyncpg.exceptions.UniqueViolationError:
            return False

    async def get_all_req_new(self):
        query = """
        SELECT * FROM public.outbox
        WHERE status_request = 'new'
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]


    async def update_req_status(self, cid):
        query = """
        UPDATE public.outbox SET status_request = 'solved'
        WHERE cid = $1
        """
        try:
            await self.pool.execute(query, cid)
        except Exception as e:
            print("Internal server error")

    async def get_all_req(self):
        query = """
        SELECT * FROM public.outbox;
        """
        try:
            return await self.pool.fetch(query)
        except:
            return ["Internal server error"]
        

    #Очиста outbox
    async def clear_all(self):
        query = """
        DELETE FROM public.outbox
        """
        try:
            return await self.pool.execute(query)
        except:
            return ["Internal server error"]
