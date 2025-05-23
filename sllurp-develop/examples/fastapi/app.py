#!/usr/bin/env python
#
# app.py - Example of using Sllurp with FastAPI
#

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from queue import Queue
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sllurp.llrp import (
    LLRP_DEFAULT_PORT,
    LLRPReaderClient,
    LLRPReaderConfig,
    LLRPReaderState,
)
from starlette.websockets import WebSocket, WebSocketDisconnect


# Pydantic model for RFID tag data
class RFIDTag(BaseModel):
    epc: str  # ascii representation of EPC
    channel: int  # RF channel index
    last_seen: int  # Timestamp of last detection
    seen_count: int  # Number of times the tag was seen
    antennaID: int
    rssi: int
    phase_angle: int
    doppler_frequency: int

# RFID Reader Configuration
READER_IP = "192.168.0.219"  # Ensure correct IP
PORT = LLRP_DEFAULT_PORT


# Store the reader and tag data
READER: Optional[LLRPReaderClient] = None
TAG_DATA: list[RFIDTag] = []
TAG_QUEUE = Queue()
ACTIVE_CONNECTIONS = []
ANTENNA_TAG_COUNTS = defaultdict(int)


async def process_queue():
    while True:
        # Check queue in a loop
        if not TAG_QUEUE.empty():
            tags = TAG_QUEUE.get()
            logging.info(f"Processing tags from queue: {tags}")
            # Send to all websocket connections
            for connection in ACTIVE_CONNECTIONS[:]:
                try:
                    await connection.send_json({"tags": tags})
                    logging.info("Sent tags to websocket connection")
                except Exception as e:
                    logging.error(f"Error sending to websocket: {e}")
                    ACTIVE_CONNECTIONS.remove(connection)
        await asyncio.sleep(0.1)  # Small delay to prevent CPU hogging

# ADDED IN ########
async def monitor_inventory():
    """Monitor reader state and log antenna usage."""
    # Added: Periodic check to ensure inventory is running and antennas are cycling
    while READER and READER.is_alive():
        state = LLRPReaderState.getStateName(READER.llrp.state)
        logging.debug(f"Inventory monitor: Reader state is {state}")
        if state != "STATE_INVENTORYING":
            logging.warning("Inventory not running, attempting to restart")
            READER.llrp.startInventory()
            logging.info(f"Restarted inventory, state: {LLRPReaderState.getStateName(READER.llrp.state)}")
        # Added: Log tag counts per antenna to verify cycling
        antenna_counts = {ant: ANTENNA_TAG_COUNTS[ant] for ant in [1, 2, 3, 4]}
        logging.info(f"Antenna tag counts: {antenna_counts}")
        await asyncio.sleep(5)  # Check every 5 seconds
#########################

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: Initialize the reader
    global READER
    try:
        config = LLRPReaderConfig()
        config.reset_on_connect = True
        config.start_inventory = True
        config.report_every_n_tags = 1
        config.antennas = [1,2,3,4]
        config.tx_power = {1:30,2:30,3:30,4:30}
        config.report_timeout_ms = 100
        config.tag_content_selector = {
            'EnableROSpecID': True,
            'EnableSpecIndex': False,
            'EnableInventoryParameterSpecID': False,
            'EnableAntennaID': True,
            'EnableChannelIndex': True,
            'EnablePeakRSSI': True,
            'EnableFirstSeenTimestamp': False,
            'EnableLastSeenTimestamp': True,
            'EnableTagSeenCount': True,
            'EnableAccessSpecID': False,
            'EnableRFPhaseAngle': True,
            'EnableRFDopplerFrequency': True
        }

        # Enable GPI event listener
        # This will trigger the start of inventory when the GPI port 1 is High
        # and stop the inventory when the GPI port 1 is Low
        config.event_selector = {
            "GPIEvent": False,
        }
        #config.impinj_extended_configuration = True
        config.impinj_search_mode = 2

        READER = LLRPReaderClient(READER_IP, PORT, config)
        READER.add_tag_report_callback(tag_report_cb)
        READER.add_event_callback(handle_event)
        READER.connect()
        logging.info(f"RFID Reader initialized, state: {LLRPReaderState.getStateName(READER.llrp.state)}")

        task = asyncio.create_task(process_queue())
        yield
        task.cancel()
    finally:
        # Shutdown: Clean up the reader
        if READER and READER.is_alive():
            try:
                READER.llrp.stopPolitely()
                READER.disconnect()
                logging.info("RFID Reader disconnected during shutdown")
            except Exception as e:
                logging.error(f"Error during reader shutdown: {e}")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all domains (change to specific origin for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Enable logging
logging.basicConfig(level=logging.DEBUG)
sllurp_logger = logging.getLogger("sllurp")
sllurp_logger.setLevel(logging.DEBUG)
sllurp_logger.addHandler(logging.StreamHandler())


# Define a callback for tag data
def tag_report_cb(_reader, tag_reports):
    """Callback to process tag data"""
    global TAG_DATA
    print(f"Raw tag reports: {tag_reports}")
    new_tags = [
        RFIDTag(
            epc=tag["EPC"].decode("ascii", errors="ignore"),
            channel=tag["ChannelIndex"],
            last_seen=tag["LastSeenTimestampUTC"],
            seen_count=tag["TagSeenCount"],
            antennaID=tag["AntennaID"],
            phase_angle=tag["ImpinjRFPhaseAngle"],
            doppler_frequency=tag["ImpinjRFDopplerFrequency"],
            rssi=tag["PeakRSSI"]
        )
        for tag in tag_reports
    ]
    TAG_DATA.extend(new_tags)  # Store every read in TAG_DATA
    # CHANGED: Only send new tags to WebSocket, not entire TAG_DATA
    serializable_tags = [tag.model_dump() for tag in new_tags]
    print(f"New tags added: {serializable_tags}")  # Debug
    # CHANGED: Added debug to show total reads accumulated
    print(f"Total TAG_DATA: {len(TAG_DATA)} reads")  # Debug
    TAG_QUEUE.put(serializable_tags)
    logging.info(f"Received {len(tag_reports)} tags")


# Define callback for events
def handle_event(_reader, event):
    if "GPIEvent" in event:
        gpi_event = event.get("GPIEvent")
        logging.info(f"GPI Event: {gpi_event}")

        if gpi_event and gpi_event.get("GPIPortNumber") == 1:
            if gpi_event.get("GPIEvent"):
                if READER and READER.is_alive():
                    logging.info("Starting inventory via GPI")
                    start_reading()
            else:
                logging.info("Stopping inventory")
                stop_reading()

    if "ConnectionAttemptEvent" in event:
        connection_event = event["ConnectionAttemptEvent"]
        logging.info(f"Connection Event: {connection_event}")
    else:
        logging.info(f"Other Event: {event}")


def clear_tag_data():
    """Clear stored tag data"""
    global TAG_DATA
    TAG_DATA = []


def start_reading():
    if READER and READER.is_alive():
        clear_tag_data()
        READER.llrp.startInventory()
        return

def stop_reading():
    if READER and READER.is_alive():
        READER.llrp.stopPolitely()
        return


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logging.info("New WebSocket connection attempt")

    await websocket.accept()
    logging.info("WebSocket connection accepted")
    ACTIVE_CONNECTIONS.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
        ACTIVE_CONNECTIONS.remove(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        if websocket in ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.remove(websocket)


@app.get("/start")
async def start():
    start_reading()
    return {"message": "Reading started"}


@app.get("/stop")
async def stop():
    stop_reading()
    return {"message": "Reading stopped"}


@app.get("/start-stop")
async def start_stop():
    start_reading()
    await asyncio.sleep(1)
    stop_reading()


@app.get("/last-read")
async def get_tags():
    return {"tags": TAG_DATA}

@app.get("/all-reads")
async def get_all_reads():
    serializable_tags = [tag.model_dump() for tag in TAG_DATA]
    return {"tags": serializable_tags}

@app.get("/status")
async def status():
    return {"status": READER.is_alive()}


@app.get("/state")
async def is_reading():
    return {
        "state": LLRPReaderState.getStateName(READER.llrp.state),
        "code": READER.llrp.state,
    }


@app.get("/clear")
async def clear():
    """API: Clear stored tag data"""
    clear_tag_data()
    return {"message": "Tag data cleared"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4000)