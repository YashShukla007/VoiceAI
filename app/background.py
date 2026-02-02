import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .db import async_session
from . import models, ai_service
from sqlalchemy.dialects.postgresql import insert

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
    async with async_session() as session:
        async with session.begin():

            # 1️⃣ Ensure call exists (UPSERT — concurrency safe)
            stmt = (
                insert(models.Call)
                .values(
                    id=call_id,
                    state=models.CallState.IN_PROGRESS.value,
                    last_sequence=None,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(stmt)

            seq = packet["sequence"]

            # 2️⃣ Insert packet (ignore duplicates)
            pkt = models.Packet(
                call_id=call_id,
                sequence=seq,
                data=packet["data"],
                timestamp=packet["timestamp"],
            )

            try:
                session.add(pkt)
                await session.flush()
            except IntegrityError:
                await session.rollback()
                logger.info(f"Duplicate packet {seq} for {call_id}")
                return  # no need to continue

            # 3️⃣ Atomically update last_sequence (only if higher)
            await session.execute(
                models.Call.__table__
                .update()
                .where(
                    models.Call.id == call_id,
                    func.coalesce(models.Call.last_sequence, -1) < seq
                )
                .values(last_sequence=seq)
            )

            # 4️⃣ Optional: detect gaps (read AFTER update)
            res = await session.execute(
                select(models.Call.last_sequence)
                .where(models.Call.id == call_id)
            )
            last_seq = res.scalar_one()

            if last_seq is not None and seq != last_seq:
                logger.warning(
                    f"Packet out of order or missing for {call_id}: got {seq}, last {last_seq}"
                )

    # 5️⃣ Notify listeners (outside transaction)
    await ws_manager.broadcast(call_id, f"packet_received:{seq}")

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