.PHONY: help install test clean docker-build docker-up docker-down peer1 peer2 peer3

help:
	@echo "P2P File Sharing - Available Commands"
	@echo "======================================"
	@echo "  make install       - Install dependencies and package"
	@echo "  make test          - Run automated tests"
	@echo "  make peer1         - Start peer on port 5001"
	@echo "  make peer2         - Start peer on port 5002 (connects to peer1)"
	@echo "  make peer3         - Start peer on port 5003 (connects to peer1&2)"
	@echo "  make docker-build  - Build Docker images"
	@echo "  make docker-up     - Start all Docker peers"
	@echo "  make docker-down   - Stop all Docker peers"
	@echo "  make clean         - Clean up generated files"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	pip install -e .
	@echo "✓ Installation complete!"

test:
	@echo "Running automated test..."
	python test_p2p.py test

test-demo:
	@echo "Starting interactive demo..."
	python test_p2p.py demo

peer1:
	@echo "Starting Peer 1 on port 5001..."
	p2p-chat --port 5001

peer2:
	@echo "Starting Peer 2 on port 5002 (connecting to localhost:5001)..."
	p2p-chat --port 5002 --connect-to localhost:5001

peer3:
	@echo "Starting Peer 3 on port 5003..."
	p2p-chat --port 5003 --connect-to localhost:5001 --connect-to localhost:5002

docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-up:
	@echo "Starting all Docker peers..."
	docker-compose up

docker-down:
	@echo "Stopping all Docker peers..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

docker-peer1:
	@echo "Accessing peer1 container..."
	docker exec -it p2p-peer1 bash

docker-peer2:
	@echo "Accessing peer2 container..."
	docker exec -it p2p-peer2 bash

docker-peer3:
	@echo "Accessing peer3 container..."
	docker exec -it p2p-peer3 bash

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ *.egg-info
	rm -rf downloads/* .metadata/*
	rm -f shared/test_file.dat
	@echo "✓ Cleanup complete!"

setup-dirs:
	@echo "Creating directory structure..."
	mkdir -p src/p2p src/cli shared downloads logs
	touch src/__init__.py src/p2p/__init__.py src/cli/__init__.py
	@echo "✓ Directories created!"

lint:
	@echo "Running code quality checks..."
	flake8 src/ --max-line-length=100 || true
	@echo "✓ Lint complete!"

format:
	@echo "Formatting code..."
	black src/ || true
	@echo "✓ Format complete!"