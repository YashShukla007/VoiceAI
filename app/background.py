import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .db import async_session
from . import models, ai_service

logger = logging.getLogger("voiceai")


class WSManager:
    def __init__(self):
        self._conns: Dict[str, Set[WebSocket]] = {}

    async def connect(self, call_id: str, websocket: WebSocket):
        await websocket.accept()
        self._conns.setdefault(call_id, set()).add(websocket)

    async def disconnect(self, call_id: str, websocket: WebSocket):
        conns = self._conns.get(call_id)
        if conns and websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, call_id: str, message: str):
        conns = list(self._conns.get(call_id, []))
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                pass


ws_manager = WSManager()


async def handle_packet(call_id: str, packet: dict):
    # Lightweight: insert packet and check ordering, log warning if hole
    async with async_session() as session:
        async with session.begin():
            # ensure call exists
            res = await session.execute(select(models.Call).where(models.Call.id == call_id))
            call = res.scalars().first()
            if not call:
                call = models.Call(id=call_id, state=models.CallState.IN_PROGRESS.value, last_sequence=None)
                session.add(call)
                await session.flush()

            seq = packet["sequence"]
            # check for missing packet
            if call.last_sequence is not None and seq != call.last_sequence + 1:
                logger.warning(f"Packet out of order or missing for {call_id}: got {seq}, last {call.last_sequence}")

            pkt = models.Packet(call_id=call_id, sequence=seq, data=packet["data"], timestamp=packet["timestamp"]) 
            try:
                session.add(pkt)
                # update last_sequence if higher
                if call.last_sequence is None or seq > call.last_sequence:
                    call.last_sequence = seq
                await session.flush()
            except IntegrityError:
                await session.rollback()
                logger.info(f"Duplicate packet {seq} for {call_id}")

    await ws_manager.broadcast(call_id, f"packet_received:{packet['sequence']}")


async def process_call_ai(call_id: str):
    # Aggregate data and call AI service with retries. Update call state accordingly.
    async with async_session() as session:
        async with session.begin():
            res = await session.execute(select(models.Call).where(models.Call.id == call_id))
            call = res.scalars().first()
            if not call:
                logger.error(f"Call {call_id} not found for processing")
                return
            call.state = models.CallState.PROCESSING_AI.value
            await session.flush()

        # fetch ordered packets
        async with session.begin():
            res = await session.execute(select(models.Packet).where(models.Packet.call_id == call_id).order_by(models.Packet.sequence))
            packets = res.scalars().all()
            text = " ".join(p.data for p in packets)
            print("Text Value: ", text)

    # call AI with retry
    try:
        transcript = await ai_service.transcribe_with_retry(text)
    except Exception as exc:
        async with async_session() as session:
            async with session.begin():
                res = await session.execute(select(models.Call).where(models.Call.id == call_id))
                call = res.scalars().first()
                if call:
                    call.state = models.CallState.FAILED.value
                await session.flush()
        await ws_manager.broadcast(call_id, "state:FAILED")
        logger.exception("AI processing failed ultimately")
        return

    # naive sentiment: positive if "good" in text else neutral
    sentiment = "positive" if "good" in text.lower() else "neutral"

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(select(models.Call).where(models.Call.id == call_id))
            call = res.scalars().first()
            if call:
                call.transcript = transcript
                call.sentiment = sentiment
                call.state = models.CallState.COMPLETED.value
                await session.flush()

    await ws_manager.broadcast(call_id, "state:COMPLETED")