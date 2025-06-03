import uvicorn
import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from products_service.manager.productManager import ProductsDataBase

db_instance: ProductsDataBase = None
class ProductsService:
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            os.getenv('PRODUCTS_TOPIC'),
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            group_id=os.getenv('PRODUCTS_GROUP')
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            enable_idempotence=True, 
        )

    async def start(self):
        await self.producer.start()
        await self.consumer.start()
        asyncio.create_task(self.process_messages())

    async def stop(self):
        await self.producer.stop()
        await self.consumer.stop()

    async def process_messages(self):
        async for msg in self.consumer:
            try:
                message = json.loads(msg.value.decode())

                cid = message.get("cid")
                request_type = message.get("type")
                endpoint = message.get("endpoint")
                data = message.get("data", {})

                if request_type != 'products':
                    continue
                result_data = []
                if endpoint == "products":
                    products = await db_instance.get_all_products()
                    if products is None:
                        result_data = []
                    else:
                        result_data = [dict(row) for row in products]
                else:
                    product_name = data.get("product_name")
                    price = data.get("price")
                    count = data.get("count")
                    sales = data.get("sales")
                    print(product_name, price, count, sales)

                    new_products = await db_instance.post_new_product(product_name, price, count, sales)

                    if new_products is None:
                        result_data = []
                    else:
                        result_data = [dict(new_products)]

                response = {
                    "cid": cid,
                    "result": result_data
                }

                await self.producer.send(
                    os.getenv('RESPONSE_TOPIC'),
                    json.dumps(response).encode(),
                    key=cid.encode(),
                )

            except Exception as e:
                print(f"[ERROR] Processing message failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_client, db_instance
    conn_str = (f'postgresql://{os.getenv("POSTGRES_USER")}:'
            f'{os.getenv("POSTGRES_PASSWORD")}@'
            f'{os.getenv("DB_CONTAINER_NAME")}:{os.getenv("POSTGRES_PORT")}'
            f'/{os.getenv("POSTGRES_DB")}')
    db_instance = ProductsDataBase()
    await db_instance.connect(conn_str)
    processor = ProductsService()
    await processor.start()
    yield
    await processor.stop()
    await db_instance.disconnect()



app = FastAPI(lifespan=lifespan)

def start():
    uvicorn.run(
        "products_service.main:app",
        host=os.getenv("PRODUCTS_HOST"),
        port=int(os.getenv("PRODUCTS_PORT")),
        reload=True
    )

