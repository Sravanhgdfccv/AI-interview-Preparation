# AI-Based Interview Preparation System

## Technologies
- HTML
- CSS
- JavaScript
- Python Flask
- SQLite
- Generative AI API

## New Features
- AI-generated interview questions
- Student-selectable number of questions (3, 5, 10, 15, or 20)
- Fresh randomized/non-repeated questions for every session
- AI answer scoring and feedback
- Recommended/model answer shown immediately below feedback so students can learn the correct approach
- Question-wise feedback on the result page
- 1–5 star user feedback section
- Feedback stored in SQLite
- REST API endpoint for interview question generation
- REST API endpoint for submitting application feedback
- AI Study Assistant chatbot for students to ask questions and get GenAI answers
- Chatbot API endpoint accessed only through Flask backend
- Demo mode when no AI API key is configured

## OpenAI API setup
The project uses the OpenAI Responses API from Flask. New OpenAI integrations should use the Responses API rather than the retired Assistants API.

Create a `.env` file in the project root and add your own OpenAI API key:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-6-luna
FLASK_SECRET_KEY=change-this-secret
```

The application reads the API key only from the Flask backend environment. Do **not** put the key in HTML/JavaScript or commit it to GitHub. The key is required for live GenAI question generation and detailed model answers; without it, the project automatically uses demo questions and fallback evaluation.

Install:

```powershell
python -m pip install -r requirements.txt
```

Run:

```powershell
python app.py
```

Open http://127.0.0.1:5000

## AI Study Assistant
The project includes a floating **AI Study Assistant** chatbot. Students can ask questions about Java, Python, DBMS, computer networks, web development, interview concepts, or other study topics. The browser sends the question to Flask, and Flask calls the configured GenAI API. The OpenAI API key is never exposed to frontend JavaScript.

### Chat API
`POST /api/chat`

JSON:
```json
{
  "message": "Explain polymorphism in Java",
  "history": [],
  "context": {"current_question": "What is polymorphism?"}
}
```

The chatbot returns a JSON answer. If no API key is configured, the application returns a limited demo response instead of exposing a secret or failing silently.

## API endpoints
### Generate questions
`POST /api/interview/questions`

JSON:
```json
{
  "job_role": "Java Developer",
  "experience": "Fresher",
  "difficulty": "Easy",
  "interview_type": "Technical",
  "question_count": 10
}
```

### Submit application feedback
`POST /api/feedback`

Requires logged-in user.

JSON:
```json
{
  "rating": 5,
  "comments": "The interview practice was useful."
}
```

## Database
SQLite automatically creates `database/interview.db` with:
- users
- interviews
- questions
- app_feedback

Never commit `.env` or your API key to GitHub.


## Admin and Student Progress
The application now includes role-based Admin and Student workflows.

### Admin features
- Separate Admin Login at `/admin/login`
- Admin dashboard to track all registered students
- Student tracking columns: total interviews, today's interviews, 7-day activity, average score, and daily progress status
- Dashboard statistics for total students, total interviews, today's interviews, and average score
- Create new reusable AI-generated tests from the Admin dashboard
- Students can access Admin-created tests from the `/tests` page

### Admin credentials
For development, the application creates an admin account automatically on first database initialization using these environment variables:

```text
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=Admin@123
ADMIN_NAME=System Administrator
```

Change these values in `.env` before using the project beyond local development.

### Student progress
Each student has a **My Progress** dashboard showing:
- Today's completed interviews
- Interviews completed in the last 7 days
- Total completed interviews
- Average interview score
- Daily practice progress (daily goal: 1 interview)
- Recent daily interview activity

Completed interviews remain stored in SQLite, allowing students and administrators to track practice over time.

### Admin-created tests
An administrator can create a test by specifying:
- Test title
- Job role
- Experience level
- Difficulty
- Interview type
- Number of questions

The test questions are generated through the configured GenAI API and stored in SQLite. Students can select an available test and complete it through the same interview evaluation and scoring workflow.


## Offline AI Study Assistant
The chatbot uses a predefined local interview-study knowledge base. It does not require OPENAI_API_KEY and does not call an external AI service. Use the AI Study Assistant button on the home page. The browser sends questions to POST /api/chat. GET /api/chat returns a health/status response.
