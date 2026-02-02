from fastapi import FastAPI, BackgroundTasks, WebSocketDisconnect
from fastapi.responses import JSONResponse
from .schemas import PacketSchema
from . import background

app = FastAPI(title="voiceai-microservice")


@app.on_event("startup")
async def startup():
    # init DB is called lazily from db.init_db; background module will import as needed
    pass


@app.post("/v1/call/stream/{call_id}")
async def ingest_packet(call_id: str, packet: PacketSchema, background_tasks: BackgroundTasks):
    background_tasks.add_task(background.handle_packet, call_id, packet.dict())
    return JSONResponse(status_code=202, content={"status": "accepted"})


@app.post("/v1/call/{call_id}/complete")
async def complete_call(call_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(background.process_call_ai, call_id)
    return JSONResponse(status_code=202, content={"status": "processing_started"})


@app.websocket('/ws/call/{call_id}')
async def ws_call(websocket, call_id: str):
    await background.ws_manager.connect(call_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await background.ws_manager.disconnect(call_id, websocket)
