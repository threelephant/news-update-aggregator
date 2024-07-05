# Personalized News Update Aggregator

The project aims to develop a microservice-based application that aggregates news and technology updates based on user preferences. The system fetches the latest news, picks the most interesting news using AI based on user preferences (optionally generates concise summaries using AI), and sends this information to users via email, Telegram, or other communication channels.

## Services

- [User Service](user-service/README.md)
- [News Aggregator Service](news-aggregator-service/README.md)
- [AI Processing Service](ai-processing-service/README.md)
- [Notification Service](notification-service/README.md)

## Requirements

- Docker
- Docker Compose
- RabbitMQ
- PostgreSQL

## Setup

1. Clone the repository:

   ```sh
   git clone https://github.com/your-repo/personalized-news-update-aggregator.git
   cd personalized-news-update-aggregator

2. Build and run the services using Docker Compose:

    ```sh
    docker-compose up --build
    ```
Access the services via their respective ports:

- User Service: http://localhost:5001
- News Aggregator Service: http://localhost:5002
- AI Processing Service: http://localhost:5003
- Notification Service: http://localhost:5004

Ensure RabbitMQ is running and accessible at localhost:5672.