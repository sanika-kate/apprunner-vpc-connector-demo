#!/usr/bin/env python3

from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from logbook import Logger, StreamHandler
import requests
import sh
import os
import psycopg
import uvicorn
import boto3
import json
import sys

app = FastAPI(
    title="App Runner VPC Demo",
    description="Demo API that demonstrates a connection from an App Runner service to a database residing in a VPC",
    version="1.0.0",
)

# ---------- App Runner–safe configuration ----------
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8080))   # MUST use App Runner PORT
TABLE_NAME = os.getenv("TABLE_NAME", "access")
TARGET = os.getenv("TARGET", "0.0.0.0")    # used only for /test-connection
# -------------------------------------------------

StreamHandler(sys.stdout).push_application()
logger = Logger()


def secrets_helper():
    client = boto3.client("secretsmanager")
    secret_string = client.get_secret_value(
        SecretId=os.getenv("DBSECRETSNAME")
    )["SecretString"]
    return json.loads(secret_string)


@app.get("/health")
def health():
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"Status": "Healthy"}
    )


def pg_client():
    return psycopg.connect(
        f"dbname={os.getenv('DB_NAME', 'apprunnerdemo')} "
        f"user={os.getenv('DB_USER')} "
        f"password={os.getenv('DB_PASS')} "
        f"host={os.getenv('DB_HOST')}"
    )


def update_table(user_agent):
    conn = pg_client()
    try:
        conn.execute(
            f"INSERT INTO {TABLE_NAME}(last_update, user_agent) "
            f"VALUES('{datetime.now().isoformat()}', '{user_agent}')"
        )
        conn.commit()
    except Exception as e:
        logger.error(e)
    finally:
        conn.close()


@app.get("/recent-visits")
def recent_visits():
    conn = pg_client()
    latest_queries = []
    try:
        records = conn.execute(
            f"SELECT * FROM {TABLE_NAME} ORDER BY last_update DESC LIMIT 10"
        )
        for record in records:
            latest_queries.append(
                {"timestamp": str(record[0]), "user_agent": str(record[1])}
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"Response": latest_queries}
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"Response": "Error, unable to produce recent visits"}
        )


@app.get("/test-connection")
def test_connection():
    result = sh.nc("-vz", "-w2", TARGET, str(PORT), _err_to_out=True).strip("\n")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"Response": str(result)}
    )


@app.get("/ecs-private-service")
def ecs_private_service():
    ecs_service_url = os.getenv("ECSPRIVATESERVICE")
    result = requests.get(ecs_service_url)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"Response": str(result.content)}
    )


@app.get("/")
def root(request: Request):
    user_agent = request.headers.get("user-agent")
    update_table(user_agent)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"Response": "Registered request"}
    )


# ---------- App Runner entrypoint ----------
if __name__ == "__main__":
    logger.info("Starting App Runner service...")

    if os.getenv("APPRUNNERSERVICE"):
        secrets = secrets_helper()
        os.environ["DB_PASS"] = secrets["password"]
        os.environ["DB_USER"] = secrets["username"]

