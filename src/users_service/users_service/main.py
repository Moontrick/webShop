import uvicorn
import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from users_service.manager.usersManager import UserDataBase

db_instance: UserDataBase = None
class UsersService:
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            os.getenv('USERS_TOPIC'),
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            group_id=os.getenv('USERS_GROUP')
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

                if request_type != 'users':
                    continue

                result_data = []
                if endpoint == "users":
                    users = await db_instance.get_all_users()
                    if users is None:
                        result_data = []
                    else:
                        result_data = [dict(row) for row in users]
                else:
                    username = data.get("username")
                    email = data.get("email")
                    password = data.get("password")
                    new_user = await db_instance.post_new_user(username, email, password)

                    if new_user is None:
                        result_data = []
                    else:
                        result_data = [dict(new_user)]

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
    db_instance = UserDataBase()
    await db_instance.connect(conn_str)
    processor = UsersService()
    await processor.start()
    yield
    await processor.stop()
    await db_instance.disconnect()



app = FastAPI(lifespan=lifespan)

def start():
    uvicorn.run(
        "users_service.main:app",
        host=os.getenv("USERS_HOST"),
        port=int(os.getenv("USERS_PORT")),
        reload=True
    )

