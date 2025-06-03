import uvicorn
import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from order_service.manager.orderManager import OrderDataBase

db_instance: OrderDataBase = None
class OrderService:
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            os.getenv('ORDER_TOPIC'),
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            group_id=os.getenv('ORDER_GROUP')
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

                if request_type != 'orders':
                    continue

                result_data = []
                if endpoint == "orders":
                    orders = await db_instance.get_all_orders()
                    if orders is None:
                        result_data = []
                    else:
                        result_data = [dict(row) for row in orders]
                else:
                    user_id = data.get("user_id")
                    product_id = data.get("product_id")
                    quantity = data.get("quantity")

                    new_order = await db_instance.post_new_order(user_id, product_id, quantity)

                    if new_order is None:
                        result_data = []
                    else:
                        result_data = [dict(new_order)]

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
                print(f"[ERROR] While processing {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_client, db_instance
    conn_str = (f'postgresql://{os.getenv("POSTGRES_USER")}:'
            f'{os.getenv("POSTGRES_PASSWORD")}@'
            f'{os.getenv("DB_CONTAINER_NAME")}:{os.getenv("POSTGRES_PORT")}'
            f'/{os.getenv("POSTGRES_DB")}')
    db_instance = OrderDataBase()
    await db_instance.connect(conn_str)
    processor = OrderService()
    await processor.start()
    yield
    await processor.stop()
    await db_instance.disconnect()



app = FastAPI(lifespan=lifespan)

def start():
    uvicorn.run(
        "order_service.main:app",
        host=os.getenv("ORDER_HOST"),
        port=int(os.getenv("ORDER_PORT")),
        reload=True
    )

