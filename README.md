# FIT4110 Lab 04 - Access Gate Docker Packaging

Repo nay da duoc dieu chinh tu mau IoT sang bai cua nhom Gate. Core va Analytics la cac nhom/service ma Gate lam viec cung.

## Pham vi hien tai

File OpenAPI ban cung cap la contract chung co cac endpoint nhan event tu Gate va Core:

- `GET /health`
- `POST /analytics/access-events` - Gate gui access event
- `POST /analytics/business-events` - Core gui policy decision event
- `GET /analytics/events`
- `GET /analytics/kpi`
- `GET /analytics/dashboard`
- `GET /analytics/report/{id}`

Vi OpenAPI hien tai chua co endpoint nghiep vu rieng cua Access Gate nhu quet the, mo cong, dong cong, nen bai Lab 04 duoc trien khai theo huong: chay service theo contract chung va chung minh phan Gate thong qua `POST /analytics/access-events`.

## Cau truc quan trong

```text
contracts/smart-campus-analytics.openapi.yaml
src/iot_app/main.py
postman/collections/FIT4110_lab04_gate_core_analytics.postman_collection.json
postman/environments/FIT4110_lab04_local.postman_environment.json
Dockerfile
.dockerignore
.env.example
RUN_LOCAL.md
reports/
```

## Chay local khong Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn iot_app.main:app --app-dir src --host 0.0.0.0 --port 8000
```

Kiem tra:

```bash
curl http://localhost:8000/health
```

## Build va chay bang Docker

```bash
docker build -t fit4110/access-gate:lab04 .
docker run --rm --name fit4110-gate-lab04 -p 8000:8000 --env-file .env.example fit4110/access-gate:lab04
```

## Chay Newman tren container

Mo terminal khac:

```bash
npm install
npm run test:local
```

Report sinh ra:

```text
reports/newman-lab04-local.xml
reports/newman-lab04-local.html
```

## Lenh Makefile

```bash
make install
make lint
make mock
make build
make run
make test-docker
make stop
```

## Tieu chi Lab 04 da dap ung

- Co Dockerfile multi-stage.
- Container chay bang non-root user.
- Co `.dockerignore`.
- Co `.env.example`.
- Co `HEALTHCHECK` goi `GET /health`.
- Co OpenAPI contract chung trong `contracts/`.
- Co Postman/Newman collection cho auth, functional, negative, conflict va ProblemDetails.
- Co `RUN_LOCAL.md` de nguoi khac chay lai.

## Can bo sung neu giang vien yeu cau dung de tai Gate rieng

Neu thay/co yeu cau service Gate phai co API rieng, can them OpenAPI cho Gate, vi file hien tai la Analytics API. Cac endpoint Gate co the gom:

- `POST /gate/access-requests`
- `GET /gate/access-logs`
- `GET /gates/{gateId}/status`
- `POST /gates/{gateId}/open`

Khi co Gate OpenAPI rieng, co the thay/cap nhat service va Postman collection theo contract do.
