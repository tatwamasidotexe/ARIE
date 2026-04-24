.PHONY: docker-up docker-down db-init backend ingestion worker frontend

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

db-init:
	cd database && bash init.sh

backend:
	cd backend && python -m venv venv 2>/dev/null || true
	cd backend && . venv/bin/activate && pip install -r requirements.txt -q && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

ingestion-reddit:
	cd ingestion && pip install -r requirements.txt -q 2>/dev/null || true
	cd ingestion && python -m ingestion.reddit_scraper

ingestion-rss:
	cd ingestion && pip install -r requirements.txt -q 2>/dev/null || true
	cd ingestion && python -m ingestion.rss_fetcher

worker:
	cd workflows && pip install -r requirements.txt -q 2>/dev/null || true
	cd workflows && pip install -r ../agents/requirements.txt -q 2>/dev/null || true
	cd workflows && python -m workflows.worker

frontend:
	cd frontend && npm install && npm run dev
