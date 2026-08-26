import os
import json
import aio_pika
from .schemas import EventEnvelope

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5673/")

class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        # Ensure publisher confirms
        await self.channel.declare_confirm_select()
        self.exchange = await self.channel.declare_exchange(
            name="parking.events",
            type=aio_pika.ExchangeType.TOPIC,
            durable=True
        )

    async def publish(self, event: EventEnvelope, routing_key: str):
        if not self.exchange:
            await self.connect()
            
        message = aio_pika.Message(
            body=json.dumps(event.model_dump()).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=event.event_id,
            content_type="application/json"
        )
        
        await self.exchange.publish(
            message,
            routing_key=routing_key
        )

    async def close(self):
        if self.connection:
            await self.connection.close()

publisher = EventPublisher()

async def get_publisher():
    if not publisher.exchange:
        await publisher.connect()
    return publisher
