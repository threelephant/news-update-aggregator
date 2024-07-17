# Personalized News Update Aggregator

## Purpose of the System
The **Personalized News Update Aggregator** is a microservice-based application designed to aggregate news and technology updates tailored to individual user preferences. The system fetches the latest news and selects the most interesting articles using AI, optionally generating concise summaries. Users receive these updates via their preferred communication channels, such as email.

## System Diagram
![system-diagram](https://github.com/user-attachments/assets/3c293f18-0aad-4001-b788-937d9b38420a)
![system-diagram2](https://github.com/user-attachments/assets/1357ed7d-98fd-4546-8f7a-56508afc540a)

## Steps to Run the Application Locally

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/news-update-aggregator.git
   cd news-update-aggregator
   ```

2. **Set Up Environment Variables**
   Create a `.env` file in the `src/Accessor Service` directory and add the necessary environment variables:
   ```plaintext
   NEWS_DATA_API=your_news_data_api_key
   GEMINI_API_KEY=your_gemini_api_key
   RABBITMQ_URL=amqp://guest:guest@localhost:5672/
   DATABASE_URL=postgresql://user:password@localhost:15432/dbname
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=465
   EMAIL_SENDER=your_email@gmail.com
   EMAIL_PASSWORD=your_email_password
   EMAIL_RECEIVER=receiver_email@gmail.com
   ```

3. **Build and Run the Services with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the Services**
   The services will be available at:
   - **Manager Service:** `http://localhost:5004/docs`
   - **Accessor Service:** `http://localhost:5005/docs`

5. **Check the Logs**
   To view logs for each service, you can use:
   ```bash
   docker-compose logs -f
   ```

## Instructions for Testing the Application

### Using integration tests
Make sure Manager Service is running locally on http://localhost:5004 and you are using its virtual environment. Run the tests using pytest:
```commandline
cd tests
python -m pytest manager_tests.py 
```
These tests will send HTTP requests to the specified URLs, ensuring that the API endpoints function as expected.
### Using Swagger
1. Open your browser and navigate to:
   - **Manager Service:** `http://localhost:5005/docs`
   - **Accessor Service:** `http://localhost:5006/docs`

2. You can test the following endpoints:
   - **User Registration:** POST `/register`
   - **Login:** POST `/token`
   - **Save Preferences:** POST `/save_preferences`
   - **Request News:** POST `/news`

### Using Postman
1. Import the provided Postman collection into Postman to test the API endpoints.

2. Make requests to the services based on the defined routes in the collection.

### Example Requests

1. **Register User:**
   ```json
   POST /register
   {
       "username": "testuser",
       "password": "testpassword"
   }
   ```

2. **Login User:**
   ```json
   POST /token
   {
       "username": "testuser",
       "password": "testpassword"
   }
   ```

3. **Save Preferences:**
   ```json
   POST /save_preferences
   {
       "username": "testuser",
       "Authorization": "Bearer your_access_token",
       "preferences": {
           "category": ["technology", "science"]
       }
   }
   ```

4. **Request News:**
   ```json
   POST /news
   {
       "username": "testuser",
       "Authorization": "Bearer your_access_token"
   }
   ```

## Technologies Used
- **Frameworks:** FastAPI, Dapr
- **Database:** PostgreSQL
- **Message Broker:** RabbitMQ
- **Caching:** Redis
- **Containerization:** Docker, Docker Compose
- **AI Services:** Gemini AI
- **Communication:** Email
- **Reverse Proxy Server:** Nginx
- **Frontend:** React, Typescript
