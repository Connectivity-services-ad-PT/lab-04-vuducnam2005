# RUN_LOCAL.md - Access Gate Lab 04

Tai lieu nay huong dan chay lai Access Gate service. Core va Analytics la cac nhom/service ma Gate lam viec cung.

## 1. Cai dependency Newman/Prism/Spectral

```bash
npm install
```

## 2. Build Docker image

```bash
docker build -t fit4110/access-gate:lab04 .
```

## 3. Run container

```bash
docker run --rm \
  --name fit4110-gate-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/access-gate:lab04
```

Mo terminal khac va kiem tra health:

```bash
curl http://localhost:8000/health
```

Ket qua mong doi:

```json
{
  "status": "ok",
  "service": "access-gate-service",
  "time": "2026-05-26T00:00:00+00:00"
}
```

## 4. Chay Newman tren container

```bash
npm run test:local
```

Report duoc sinh tai:

```text
reports/newman-lab04-local.xml
reports/newman-lab04-local.html
```

## 5. Lenh nhanh

```bash
make build
make run
make test-docker
make stop
```

## Ghi chu pham vi

File `contracts/smart-campus-analytics.openapi.yaml` la contract chung. Trong Lab 04 nay, repo duoc dong goi nhu Access Gate service; phan lam viec voi Analytics duoc test qua `POST /analytics/access-events`, va phan lam viec voi Core duoc test qua `POST /analytics/business-events`.
