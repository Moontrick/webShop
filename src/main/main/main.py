import uvicorn
import os
import asyncio
import json
import uuid
from fastapi import FastAPI, Request, Response
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from main.manager.outboxManager import OutBoxDataBase
from main.manager.models import UsersPost, ProductsPost, OrderPost
from contextlib import asynccontextmanager

memory_pool = {}
db_instance: OutBoxDataBase = None


class KafkaClient:
    def __init__(self):
        self._writer = AIOKafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
            enable_idempotence=True,
            acks="all",
            request_timeout_ms=30000,
            retry_backoff_ms=1000,
        )
        self._reader = AIOKafkaConsumer(
            os.getenv("RESPONSE_TOPIC"),
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
            group_id=os.getenv("BACK_GROUP"),
        )

    async def activate(self):
        await self._writer.start()
        await self._reader.start()
        asyncio.create_task(self._listen())
        asyncio.create_task(self._retry_failed())

    async def shutdown(self):
        await self._writer.stop()
        await self._reader.stop()

    async def _listen(self):
        global db_instance
        async for packet in self._reader:
            try:
                decoded = json.loads(packet.value.decode())
                cid = decoded["cid"]
                if cid in memory_pool:
                    await db_instance.update_req_status(cid)
                    memory_pool[cid].set_result(decoded["result"])
                    del memory_pool[cid]
            except Exception as err:
                print(f"[BROKER][ERROR]: {err}")

    async def _retry_failed(self):
        global db_instance
        while True:
            try:
                unsent = await db_instance.get_all_req_new()
                if unsent:
                    print(f"[RETRY] Found {len(unsent)} unsent messages")
                    for entry in unsent:
                        routing = {
                            "users": os.getenv("USERS_TOPIC"),
                            "orders": os.getenv("ORDER_TOPIC"),
                            "default": os.getenv("PRODUCTS_TOPIC"),
                        }
                        topic = routing.get(entry["request_type"], routing["default"])
                        cid = entry["cid"]
                        payload = entry["request_data"]

                        if cid in memory_pool:
                            continue

                        memory_pool[cid] = asyncio.Future()
                        await self._writer.send(topic, payload.encode(), key=cid.encode())
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[RETRY][ERROR]: {e}")
                await asyncio.sleep(30)


kafka: KafkaClient = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global kafka, db_instance
    dsn = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('DB_CONTAINER_NAME')}:{os.getenv('POSTGRES_PORT')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    db_instance = OutBoxDataBase()
    await db_instance.connect(dsn)
    kafka = KafkaClient()
    await kafka.activate()
    yield
    await kafka.shutdown()
    await db_instance.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/users")
async def route_users(req: Request):
    return await handle_query(req, "users", "get", "users")

@app.post("/users_add")
async def route_users_add(req: UsersPost):
    return await handle_query(req, "users", "post", "users_add")

@app.get("/products")
async def route_products(req: Request):
    return await handle_query(req, "products", "get", "products")

@app.post("/products_add")
async def route_products_add(req: ProductsPost):
    return await handle_query(req, "products", "post", "products_add")

@app.get("/orders")
async def route_orders(req: Request):
    return await handle_query(req, "orders", "get", "orders")

@app.post("/orders_add")
async def route_orders_add(req: OrderPost):
    return await handle_query(req, "orders", "post", "orders_add")

@app.get("/clear_all")
async def clear_all(req: Request):
    return await handle_query(req, "main", "get", "clear_all")


async def dispatcher_callback(topic, payload, cid):
    global kafka

    if cid in memory_pool:
        print(f"[WARN] CID {cid} already being handled, skipping duplicate dispatch")
        return Response(status_code=409, content="Duplicate CID")

    wait_result = asyncio.Future()
    memory_pool[cid] = wait_result
    await kafka._writer.send(
        topic, payload.encode("utf-8"), key=cid.encode()
    )

    try:
        result = await asyncio.wait_for(wait_result, timeout=30)
        return Response(
            status_code=200,
            content=json.dumps(result),
            media_type="application/json",
        )
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] Request {cid} timed out")
        return Response(status_code=504, content="Gateway Timeout")
    finally:
        memory_pool.pop(cid, None)


async def handle_query(req, category: str, method: str, endpoint: str):
    global db_instance
    cid = str(uuid.uuid4())

    try:
        topic_lookup = {
            "main": "main",
            "users": os.getenv("USERS_TOPIC"),
            "orders": os.getenv("ORDER_TOPIC"),
            "products": os.getenv("PRODUCTS_TOPIC"),
        }
        route = topic_lookup.get(category, topic_lookup["products"])
        if route == "main": 
            db_status = await db_instance.clear_all()
        if method == "get":
            data = {}
        else:
            data = req.dict()

        payload = json.dumps({
            "cid": cid,
            "type": category,
            "endpoint": endpoint,
            "data": data
        })

        db_status = await db_instance.insert_new_request(cid, category, payload)
        print("db_status", db_status)
        if db_status:
            print(f"[QUEUE] Task enqueued: {cid}")
            return await dispatcher_callback(route, payload, cid)
        else:
            return Response(status_code=500, content="DB insert failed")
    except Exception as err:
        print(f"[ERROR] While processing {category}: {err}")
        return Response(status_code=500, content="Internal Error")


def start():
    uvicorn.run(
        "main.main:app",
        host=os.getenv("BACK_HOST"),
        port=int(os.getenv("BACK_PORT")),
        reload=True
    )
