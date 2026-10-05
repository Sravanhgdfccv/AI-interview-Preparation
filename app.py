import os, json, sqlite3, re
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
DB_DIR = os.path.join(BASE_DIR, "database")
DB = os.path.join(DB_DIR, "interview.db")

def db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student')""")
        c.execute("""CREATE TABLE IF NOT EXISTS interviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            job_role TEXT, experience TEXT, difficulty TEXT,
            interview_type TEXT, score REAL, test_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, interview_id INTEGER,
            question TEXT, user_answer TEXT, ai_feedback TEXT, score REAL,
            ideal_answer TEXT)""")
        # Add the learning answer column to older databases created by previous versions.
        cols = [row[1] for row in c.execute("PRAGMA table_info(questions)").fetchall()]
        if "ideal_answer" not in cols:
            c.execute("ALTER TABLE questions ADD COLUMN ideal_answer TEXT")
        c.execute("""CREATE TABLE IF NOT EXISTS app_feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            interview_id INTEGER, rating INTEGER, comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            job_role TEXT NOT NULL, experience TEXT NOT NULL,
            difficulty TEXT NOT NULL, interview_type TEXT NOT NULL,
            question_count INTEGER NOT NULL, created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS test_questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, test_id INTEGER NOT NULL,
            question TEXT NOT NULL, ideal_answer TEXT)""")
        # Migrations for databases created by earlier project versions.
        user_cols = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
        if "role" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
        interview_cols = [row[1] for row in c.execute("PRAGMA table_info(interviews)").fetchall()]
        if "test_id" not in interview_cols:
            c.execute("ALTER TABLE interviews ADD COLUMN test_id INTEGER")

        # Create/update the admin account from environment variables.
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin@123").strip()
        admin_name = os.getenv("ADMIN_NAME", "System Administrator").strip() or "System Administrator"
        if admin_email and admin_password:
            existing_admin = c.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
            if existing_admin:
                c.execute("UPDATE users SET role='admin' WHERE id=?", (existing_admin[0],))
            else:
                c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                          (admin_name, admin_email, generate_password_hash(admin_password), "admin"))
        c.commit()

def ai_generate_questions(role, experience, difficulty, interview_type, question_count=5, previous_questions=None):
    question_count = max(1, min(int(question_count), 20))
    previous_questions = previous_questions or []
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return demo_questions(role, difficulty, interview_type, question_count, previous_questions)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        previous_text = "\n".join(f"- {q}" for q in previous_questions[-50:]) or "None"
        prompt = f"""You are an interview preparation assistant.
Generate exactly {question_count} UNIQUE {difficulty} {interview_type} interview questions for a {role} candidate with {experience} experience.

Important rules:
1. Generate a fresh set of questions for this session.
2. Do NOT repeat any question from the previous-question list below.
3. Avoid questions that are only minor rewordings of previous questions.
4. Keep questions relevant to the selected role, experience, difficulty, and interview type.
5. Return ONLY valid JSON in this format:
{{"questions":[{{"question":"...","answer":"key points for a good answer"}}]}}

Previous questions to avoid:
{previous_text}
"""
        r = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-6-luna"), input=prompt)
        raw = r.output_text.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw)
        data = json.loads(raw)
        questions = data.get("questions", [])
        if len(questions) >= question_count:
            return {"questions": questions[:question_count]}
        return demo_questions(role, difficulty, interview_type, question_count, previous_questions)
    except Exception:
        return demo_questions(role, difficulty, interview_type, question_count, previous_questions)

def demo_questions(role, difficulty, interview_type, question_count=5, previous_questions=None):
    import random
    previous = {str(q).strip().lower() for q in (previous_questions or [])}
    role_lower = role.lower()

    common = [
        ("Tell me about yourself and why you are interested in this role.", "Give a concise education, skills, project and career summary connected to the role."),
        ("Explain one project you have worked on.", "Cover the problem, technologies, your contribution, challenges and result."),
        ("What is your biggest technical strength?", "State one relevant strength and support it with a concrete example."),
        ("How do you learn a new technology?", "Explain a structured approach using documentation, practice and projects."),
        ("Describe a technical challenge you faced and how you solved it.", "Use a clear situation, action and result with technical details."),
        ("How do you debug a program that is not producing the expected output?", "Explain reproduction, logs, isolation, testing and verification."),
        ("What is an API and why is it useful?", "Explain application-to-application communication, endpoints, requests and responses."),
        ("What is a REST API?", "Explain resources, HTTP methods, endpoints, statelessness and common response formats."),
        ("What is a database and why do applications use one?", "Explain persistent structured storage, querying and data management."),
        ("What is version control and why is Git useful?", "Explain tracking changes, collaboration, branches and rollback."),
        ("What is the difference between frontend and backend development?", "Explain user interface/client-side work versus server-side logic, APIs and data."),
        ("How would you improve the performance of a slow application?", "Discuss measurement, bottlenecks, algorithms, database queries, caching and testing."),
        ("How do you make code easier for other developers to maintain?", "Mention naming, modularity, documentation, testing and consistent conventions."),
        ("What is object-oriented programming?", "Explain objects/classes and concepts such as encapsulation, inheritance, polymorphism and abstraction."),
        ("What is the difference between a process and a thread?", "Explain independent processes versus lightweight execution units sharing process resources."),
        ("What happens when you enter a URL in a web browser?", "Cover DNS, connection, HTTP request/response and browser rendering at a high level."),
        ("What are HTTP GET and POST methods used for?", "GET retrieves resources; POST commonly sends data to create or process a resource."),
        ("What is authentication and how is it different from authorization?", "Authentication verifies identity; authorization determines permitted actions."),
        ("How would you protect sensitive user data in a web application?", "Mention secure transport, password hashing, validation, access control and secret management."),
        ("Why should we hire you for this role?", "Connect skills, learning ability, projects and attitude to the job requirements.")
    ]

    java = [
        ("What are the main OOP concepts in Java?", "Encapsulation, inheritance, polymorphism and abstraction."),
        ("What is the difference between == and equals() in Java?", "== compares primitive values or references; equals() can compare logical object equality."),
        ("What is exception handling in Java?", "Explain try, catch, finally, throw and throws."),
        ("What is an ArrayList and when would you use it?", "A resizable List implementation that maintains order and allows duplicates."),
        ("What is the difference between an array and ArrayList in Java?", "Arrays have fixed size; ArrayList is resizable and provides collection methods."),
        ("What is method overloading versus method overriding?", "Overloading changes parameters in the same class; overriding redefines inherited behavior."),
        ("What is the difference between an interface and a class in Java?", "An interface defines a contract; a class can hold state and implementation and implement interfaces."),
        ("What is a constructor in Java?", "A special member used to initialize a new object."),
        ("What are access modifiers in Java?", "public, protected, default and private control visibility."),
        ("What is the Java Collections Framework?", "A set of interfaces and classes such as List, Set, Queue and Map for managing groups of objects."),
        ("What is the difference between HashMap and HashSet?", "HashMap stores key-value pairs; HashSet stores unique values and is backed conceptually by hashing."),
        ("Why is String immutable in Java?", "Its value cannot change after creation, supporting safety, caching and predictable behavior."),
        ("What is garbage collection in Java?", "Automatic memory management that reclaims objects that are no longer reachable."),
        ("What is the difference between checked and unchecked exceptions?", "Checked exceptions are compile-time checked; unchecked exceptions derive from RuntimeException."),
        ("What does the static keyword mean in Java?", "The member belongs to the class rather than an individual instance.")
    ]

    python_q = [
        ("What are lists and tuples in Python, and how are they different?", "Lists are mutable; tuples are immutable sequence types."),
        ("What is a Python dictionary?", "A mutable mapping of unique keys to values."),
        ("What is a Python virtual environment?", "An isolated environment for project-specific Python packages."),
        ("What is the difference between == and is in Python?", "== compares values; is compares object identity."),
        ("What are Python decorators?", "Callables that wrap or modify functions/classes without changing their core source."),
        ("What is exception handling in Python?", "Explain try, except, else, finally and raising exceptions."),
        ("What is a list comprehension?", "A concise syntax for building lists from iterables with expressions and optional conditions."),
        ("What are *args and **kwargs?", "*args captures positional arguments; **kwargs captures keyword arguments."),
        ("What is Flask used for?", "A lightweight Python web framework used to build web applications and APIs."),
        ("How does a Flask route work?", "A route maps a URL and HTTP method to a Python view function.")
    ]

    hr = [
        ("What are your strengths?", "Choose relevant strengths and support them with examples."),
        ("What is one weakness you are currently improving?", "Choose a genuine manageable weakness and explain concrete improvement steps."),
        ("Where do you see yourself in five years?", "Describe realistic growth, learning and contribution aligned with the role."),
        ("Why do you want to join this company?", "Connect the company/role with your skills, interests and growth goals."),
        ("Describe a time you worked successfully in a team.", "Use a situation, your contribution, collaboration and result."),
        ("How do you handle pressure or tight deadlines?", "Explain prioritization, communication and a concrete example."),
        ("How would you handle a disagreement with a teammate?", "Emphasize listening, facts, respectful discussion and shared goals."),
        ("What motivates you to do your best work?", "Connect motivation to learning, ownership, impact or problem solving."),
        ("Tell me about a failure and what you learned from it.", "Show accountability, learning and a change in future behavior."),
        ("Are you comfortable learning technologies that are new to you?", "Show adaptability with an example of learning something quickly.")
    ]

    pool = list(common)
    if "java" in role_lower:
        pool += java
    if "python" in role_lower or "flask" in role_lower:
        pool += python_q
    if interview_type.lower() in {"hr", "mixed"}:
        pool += hr

    fresh = [(q, a) for q, a in pool if q.strip().lower() not in previous]
    if len(fresh) < question_count:
        fresh = pool

    random.SystemRandom().shuffle(fresh)
    selected = fresh[:question_count]
    return {"questions": [{"question": q, "answer": a} for q, a in selected]}

def ai_evaluate(question, answer, expected):
    if not answer.strip():
        return {"score": 0, "feedback": "No answer was provided. Try answering in 2–4 clear sentences."}
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            prompt = f"""Evaluate this interview answer.
Question: {question}
Candidate answer: {answer}
Expected key points: {expected}
Return ONLY JSON: {{"score": number from 0 to 10, "feedback":"brief constructive feedback", "ideal_answer":"a clear, interview-ready model answer the student can study"}}"""
            r = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-6-luna"), input=prompt)
            text = re.sub(r"^```json\s*|\s*```$", "", r.output_text.strip())
            result = json.loads(text)
            result.setdefault("ideal_answer", expected)
            return result
        except Exception:
            pass
    # Simple deterministic fallback so the app works without an API key.
    words = set(re.findall(r"[a-zA-Z]+", answer.lower()))
    expected_words = set(re.findall(r"[a-zA-Z]+", expected.lower()))
    overlap = len(words & expected_words) / max(1, len(expected_words))
    score = round(min(10, max(2, 2 + overlap * 8)), 1)
    feedback = "Good attempt. Add more specific technical terms and an example." if score < 7 else "Good answer. Add a concrete example to make it stronger."
    return {"score": score, "feedback": feedback, "ideal_answer": expected}


def ai_chat_answer(message, context=None, history=None):
    """Offline interview study assistant using predefined Q&A. No external API is required."""
    message = str(message or "").strip().lower()
    if not message:
        return {"answer": "Please enter a question."}

    # Offline knowledge base: common interview/study questions and concise answers.
    knowledge = [
        ("polymorphism", "Polymorphism means one interface or method name can have different implementations. In Java, it is mainly achieved through method overloading (compile-time) and method overriding (run-time)."),
        ("encapsulation", "Encapsulation means bundling data and methods inside a class and controlling access to the data using access modifiers such as private, protected, and public."),
        ("inheritance", "Inheritance allows one class to acquire properties and methods of another class. In Java it is commonly implemented with extends and supports code reuse."),
        ("abstraction", "Abstraction hides implementation details and exposes only essential functionality. In Java it can be achieved using abstract classes and interfaces."),
        ("oops", "The four main OOP principles are encapsulation, inheritance, polymorphism, and abstraction."),
        ("class and object", "A class is a blueprint that defines data and behavior. An object is an instance of that class created at runtime."),
        ("constructor", "A constructor is a special class member used to initialize objects. It has the same name as the class and has no return type."),
        ("exception handling", "Exception handling manages runtime errors using try, catch, finally, throw, and throws so the program can handle failures gracefully."),
        ("arraylist", "ArrayList is a resizable Java collection that implements List. It allows indexed access, permits duplicates, and provides dynamic sizing."),
        ("hashmap", "HashMap stores key-value pairs. Keys are unique, values may repeat, and average lookup, insertion, and removal are O(1)."),
        ("string", "String in Java represents a sequence of characters. String objects are immutable, meaning their contents cannot be changed after creation."),
        ("recursion", "Recursion is a technique where a function calls itself to solve smaller instances of a problem. It needs a base condition to stop."),
        ("binary search", "Binary search works on sorted data by repeatedly dividing the search range in half. Its time complexity is O(log n)."),
        ("linear search", "Linear search checks elements one by one until the target is found or the collection ends. Its time complexity is O(n)."),
        ("bubble sort", "Bubble sort repeatedly compares adjacent elements and swaps them when they are in the wrong order. Its average and worst-case time complexity is O(n²)."),
        ("quick sort", "Quick sort selects a pivot and partitions elements around it, then recursively sorts the partitions. Average time is O(n log n), worst case O(n²)."),
        ("merge sort", "Merge sort divides the array into halves, recursively sorts them, and merges the sorted halves. Its time complexity is O(n log n) and it is stable."),
        ("time complexity", "Time complexity describes how an algorithm's running time grows with input size. Common complexities include O(1), O(log n), O(n), O(n log n), and O(n²)."),
        ("stack", "A stack is a LIFO data structure: the last element inserted is the first removed. Common operations are push, pop, and peek."),
        ("queue", "A queue is a FIFO data structure: the first element inserted is the first removed. Common operations are enqueue and dequeue."),
        ("dbms", "A DBMS is software used to create, store, organize, retrieve, and manage data in databases while providing security, consistency, and controlled access."),
        ("normalization", "Normalization organizes relational data to reduce redundancy and update anomalies. Common normal forms are 1NF, 2NF, 3NF, and BCNF."),
        ("primary key", "A primary key uniquely identifies each row in a table. It must be unique and cannot contain NULL values."),
        ("foreign key", "A foreign key is a column or set of columns that references a key in another table, helping maintain referential integrity."),
        ("acid", "ACID properties are Atomicity, Consistency, Isolation, and Durability. They help transactions remain reliable and consistent."),
        ("sql", "SQL is Structured Query Language used to create, read, update, delete, and manage data in relational databases."),
        ("join", "A SQL JOIN combines rows from two or more tables using a related column. Common types are INNER, LEFT, RIGHT, and FULL JOIN."),
        ("index", "A database index is a data structure that speeds up data retrieval, usually at the cost of additional storage and slower writes."),
        ("operating system", "An operating system manages hardware and software resources and provides services to applications. Examples include Windows, Linux, and macOS."),
        ("process", "A process is a program in execution. It has its own execution state and resources such as memory and process control information."),
        ("thread", "A thread is a lightweight unit of execution within a process. Threads in the same process can share memory and resources."),
        ("deadlock", "Deadlock occurs when processes wait indefinitely for resources held by one another. The four necessary conditions are mutual exclusion, hold and wait, no preemption, and circular wait."),
        ("paging", "Paging divides logical memory into fixed-size pages and physical memory into frames. It helps manage memory without requiring contiguous allocation."),
        ("computer network", "A computer network connects devices so they can exchange data and share resources using communication protocols."),
        ("tcp", "TCP is a connection-oriented transport protocol that provides reliable, ordered, and error-checked delivery of data."),
        ("udp", "UDP is a connectionless transport protocol with low overhead. It does not guarantee delivery, ordering, or retransmission."),
        ("tcp vs udp", "TCP provides reliable ordered delivery and connection management, while UDP is faster and lightweight but does not guarantee delivery or ordering."),
        ("ip address", "An IP address identifies a device or network interface at the network layer. IPv4 uses 32-bit addresses and IPv6 uses 128-bit addresses."),
        ("dns", "DNS translates domain names such as example.com into IP addresses so clients can locate servers on a network."),
        ("rest api", "A REST API exposes resources through HTTP endpoints and commonly uses GET, POST, PUT/PATCH, and DELETE methods. REST systems are generally stateless."),
        ("api", "An API is an interface that allows software components to communicate through defined requests and responses."),
        ("html", "HTML is the standard markup language used to structure content on web pages."),
        ("css", "CSS controls the presentation and layout of HTML elements, including colors, spacing, fonts, and responsive design."),
        ("javascript", "JavaScript is a programming language commonly used to add dynamic behavior and interactivity to web pages."),
        ("flask", "Flask is a lightweight Python web framework used to build web applications and APIs using routes, request handling, templates, and extensions."),
        ("sqlite", "SQLite is a lightweight, serverless relational database stored in a single file. It is useful for local applications and prototypes."),
        ("git", "Git is a distributed version-control system used to track source-code changes and collaborate safely on software projects."),
        ("generative ai", "Generative AI creates new content such as text, code, images, or other outputs from learned patterns and user instructions."),
        ("machine learning", "Machine learning enables systems to learn patterns from data and make predictions or decisions without explicitly programming every rule."),
        ("tell me about yourself", "A strong answer should briefly cover your education, relevant technical skills, projects, strengths, and career goal. Keep it structured and relevant to the role."),
        ("why should we hire you", "Explain the value you can bring through relevant skills, projects, willingness to learn, communication, and reliability. Support claims with a short example."),
        ("why this company", "Mention specific aspects of the company such as its products, technology, culture, or opportunities, and connect them to your interests and career goals."),
        ("strengths", "Choose two or three genuine strengths relevant to the role, such as quick learning, problem solving, communication, or consistency, and give a short example."),
        ("weakness", "Choose a genuine but manageable weakness and explain the concrete steps you are taking to improve it. Avoid presenting a critical job requirement as a weakness."),
        ("handle pressure", "I handle pressure by staying calm, prioritizing tasks, breaking large work into smaller steps, and communicating early if there is a risk to a deadline. During my studies or projects, I focus on completing the most important task first and verify my work before submission."),
        ("pressure", "I handle pressure by prioritizing urgent and important tasks, creating a short plan, avoiding unnecessary distractions, and communicating clearly with teammates. I see reasonable pressure as an opportunity to stay focused and improve my time management."),
        ("tight deadlines", "When I have a tight deadline, I first understand the required outcome, divide the work into smaller tasks, prioritize the critical parts, and track progress. If I face a blocker, I communicate it early instead of waiting until the deadline."),
        ("teamwork", "Good teamwork requires communication, respect, responsibility, and willingness to support others. I listen to teammates, share ideas clearly, complete my assigned work, and help resolve problems toward the common goal."),
        ("conflict", "I handle conflict by listening to the other person's view, focusing on facts rather than personal opinions, discussing possible solutions respectfully, and choosing the option that best supports the team and project."),
        ("leadership", "Leadership means taking responsibility, communicating a clear goal, supporting team members, making decisions when needed, and ensuring the team moves toward the expected result."),
        ("relocation", "Yes, I am open to relocation if the role provides a good opportunity to learn, contribute, and grow professionally. I would plan the transition responsibly and adapt to the new work environment."),
        ("work from home", "I can work effectively from home by maintaining a dedicated schedule, communicating regularly with the team, attending meetings on time, and keeping my tasks organized."),
        ("expected salary", "As a fresher, my primary focus is on learning, contributing, and building my career. I am comfortable with the company's standard compensation for the role and am open to discussing it based on the responsibilities and overall opportunity."),
        ("career goal", "My short-term goal is to strengthen my technical and professional skills through real projects. My long-term goal is to become a dependable software professional who can take ownership of complex problems and contribute meaningful solutions."),
        ("failure", "I treat failure as feedback. I first identify what went wrong, understand the root cause, take responsibility for my part, and apply what I learned to prevent the same mistake in future work."),
        ("achievement", "Describe one meaningful academic or project achievement, explain the challenge, your specific contribution, the skills you used, and the measurable or practical result."),
        ("motivation", "I am motivated by learning new technologies, solving problems, seeing measurable progress, and contributing to useful projects. Completing a difficult task successfully also motivates me to take on more responsibility."),
        ("subject java", "Important Java interview areas include OOP, classes and objects, inheritance, polymorphism, abstraction, interfaces, exception handling, collections, strings, multithreading, JVM basics, and memory management."),
        ("subject python", "Important Python interview areas include data types, lists and tuples, dictionaries, sets, functions, comprehensions, exceptions, modules, virtual environments, OOP, decorators, generators, and Flask basics."),
        ("subject dbms", "Important DBMS interview areas include keys, normalization, ER models, SQL, joins, indexes, transactions, ACID properties, concurrency control, constraints, and database design."),
        ("subject sql", "Important SQL interview areas include SELECT, WHERE, GROUP BY, HAVING, ORDER BY, joins, subqueries, aggregate functions, constraints, indexes, views, INSERT, UPDATE, DELETE, and transactions."),
        ("subject operating system", "Important OS interview areas include processes, threads, CPU scheduling, synchronization, deadlocks, memory management, paging, segmentation, virtual memory, page replacement, and file systems."),
        ("subject computer networks", "Important Computer Networks interview areas include OSI and TCP/IP models, IP addressing, DNS, HTTP/HTTPS, TCP, UDP, three-way handshake, routing, switching, MAC addresses, and common network devices."),
        ("subject html", "Important HTML interview areas include semantic elements, forms, input types, tables, lists, links, images, audio/video, accessibility, and the difference between block and inline elements."),
        ("subject css", "Important CSS interview areas include selectors, box model, display, position, Flexbox, Grid, responsive design, media queries, specificity, pseudo-classes, and the difference between relative, absolute, fixed, and sticky positioning."),
        ("subject javascript", "Important JavaScript interview areas include variables, data types, functions, arrays, objects, DOM, events, scope, hoisting, closures, promises, async/await, fetch, and ES6 features."),
        ("subject flask", "Important Flask interview areas include routes, HTTP methods, request and response objects, templates, sessions, JSON APIs, blueprints, error handling, environment variables, and database integration."),
        ("subject sqlite", "Important SQLite interview areas include tables, primary and foreign keys, CRUD operations, joins, indexes, transactions, constraints, parameterized queries, and its serverless single-file architecture."),
        ("subject rest", "Important REST API interview areas include resources, endpoints, HTTP methods, status codes, JSON, statelessness, authentication, authorization, validation, error handling, and CRUD operations."),
        ("subject data structures", "Important Data Structures interview areas include arrays, linked lists, stacks, queues, hash tables, trees, heaps, graphs, recursion, and choosing a structure based on operation and complexity requirements."),
        ("subject algorithms", "Important Algorithms interview areas include searching, sorting, recursion, divide and conquer, greedy algorithms, dynamic programming, backtracking, graph algorithms, and time and space complexity."),
        ("subject generative ai", "Important Generative AI interview areas include prompts, tokens, language models, embeddings, context, hallucinations, model APIs, structured output, retrieval-augmented generation, responsible AI, and API security."),
        ("what is oops", "OOP is a programming paradigm based on objects and classes. Its main principles are encapsulation, inheritance, polymorphism, and abstraction. It improves modularity, reuse, and maintainability."),
        ("what is normalization", "Normalization is the process of organizing relational tables to reduce data redundancy and prevent insertion, update, and deletion anomalies. Common normal forms include 1NF, 2NF, 3NF, and BCNF."),
        ("what is sql join", "A SQL JOIN combines related rows from multiple tables. INNER JOIN returns matching rows, LEFT JOIN keeps all rows from the left table, RIGHT JOIN keeps all rows from the right table, and FULL JOIN returns matching and non-matching rows from both sides where supported."),
        ("what is tcp handshake", "TCP establishes a connection using a three-way handshake: the client sends SYN, the server responds with SYN-ACK, and the client sends ACK. This synchronizes sequence numbers and establishes the connection."),
        ("what is http", "HTTP is an application-layer protocol used for communication between clients and servers on the web. Common methods include GET, POST, PUT, PATCH, and DELETE, and responses include status codes such as 200, 404, and 500."),
        ("what is git", "Git is a distributed version-control system. Common commands include clone, status, add, commit, pull, push, branch, merge, and checkout or switch."),
    ]

    # Prefer longer/more specific phrases first and return the best keyword match.
    best = None
    best_score = 0
    for key, answer in knowledge:
        tokens = [t for t in re.findall(r"[a-z0-9]+", key) if len(t) > 2]
        score = sum(1 for t in tokens if t in message)
        if key in message:
            score += 3
        if score > best_score:
            best_score = score
            best = answer

    if best:
        return {"answer": best, "demo": True, "offline": True}

    # Helpful response when a question is outside the predefined knowledge base.
    return {
        "answer": (
            "I am the Offline AI Study Assistant and I currently use predefined interview-study Q&A, so no API key is required. "
            "Try asking about Java, OOP, DBMS, SQL, OS, Computer Networks, HTML, CSS, JavaScript, Flask, SQLite, REST APIs, "
            "algorithms, Generative AI, or common HR interview questions."
        ),
        "demo": True,
        "offline": True
    }

@app.route("/")
def index():
    return render_template("index.html", logged_in="user_id" in session)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form["name"].strip(), request.form["email"].strip(), request.form["password"]
        try:
            with db() as c:
                c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                          (name, email, generate_password_hash(password)))
                c.commit()
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        with db() as c:
            user = c.execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip(),)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session["user_id"], session["name"], session["role"] = user["id"], user["name"], user["role"]
            return redirect(url_for("index"))
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/start", methods=["POST"])
def start():
    role = request.form["job_role"].strip()
    experience = request.form["experience"]
    difficulty = request.form["difficulty"]
    itype = request.form["interview_type"]
    try:
        question_count = int(request.form.get("question_count", 5))
    except ValueError:
        question_count = 5
    question_count = max(1, min(question_count, 20))

    previous_questions = []
    if "user_id" in session:
        with db() as c:
            rows = c.execute(
                """SELECT q.question FROM questions q
                   JOIN interviews i ON q.interview_id=i.id
                   WHERE i.user_id=? AND LOWER(i.job_role)=LOWER(?)
                   ORDER BY q.id DESC LIMIT 50""",
                (session["user_id"], role)
            ).fetchall()
            previous_questions = [row["question"] for row in rows]

    data = ai_generate_questions(role, experience, difficulty, itype, question_count, previous_questions)
    session["interview"] = {"role": role, "experience": experience, "difficulty": difficulty,
                            "type": itype, "question_count": question_count, "test_id": None,
                            "questions": data["questions"], "answers": []}
    return redirect(url_for("interview"))

@app.route("/interview")
def interview():
    data = session.get("interview")
    if not data:
        return redirect(url_for("index"))
    return render_template("interview.html", data=data)

@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = session.get("interview")
    payload = request.get_json()
    q = data["questions"][int(payload["index"])]
    result = ai_evaluate(q["question"], payload["answer"], q["answer"])
    answers = data.setdefault("answers", [])
    while len(answers) <= int(payload["index"]):
        answers.append({"question": "", "answer": "", "feedback": "", "score": 0})
    answers[int(payload["index"])] = {
        "question": q["question"],
        "answer": payload.get("answer", ""),
        "feedback": result.get("feedback", ""),
        "ideal_answer": result.get("ideal_answer", q.get("answer", "")),
        "score": float(result.get("score", 0))
    }
    session["interview"] = data
    session.modified = True
    return jsonify(result)

@app.route("/finish", methods=["POST"])
def finish():
    if "user_id" not in session:
        return redirect(url_for("login"))
    data = session.get("interview")
    score = float(request.form.get("score", 0))
    with db() as c:
        cur = c.execute("""INSERT INTO interviews(user_id,job_role,experience,difficulty,interview_type,score,test_id)
                           VALUES(?,?,?,?,?,?,?)""",
                        (session["user_id"], data["role"], data["experience"], data["difficulty"], data["type"], score, data.get("test_id")))
        interview_id = cur.lastrowid
        for item in data.get("answers", []):
            if item.get("question"):
                c.execute(
                    "INSERT INTO questions(interview_id,question,user_answer,ai_feedback,score,ideal_answer) VALUES(?,?,?,?,?,?)",
                    (interview_id, item.get("question"), item.get("answer", ""), item.get("feedback", ""), item.get("score", 0), item.get("ideal_answer", ""))
                )
        c.commit()
    session["last_result"] = {"score": score, "role": data["role"], "interview_id": interview_id}
    session.pop("interview", None)
    return redirect(url_for("result"))

@app.route("/result")
def result():
    result_data = session.get("last_result")
    if not result_data:
        return redirect(url_for("index"))
    questions = []
    if "user_id" in session:
        with db() as c:
            questions = c.execute(
                "SELECT question, user_answer, ai_feedback, score, ideal_answer FROM questions WHERE interview_id=? ORDER BY id",
                (result_data["interview_id"],)
            ).fetchall()
    return render_template("result.html", result=result_data, questions=questions)

@app.route("/api/chat", methods=["GET", "POST"])
def api_chat():
    if request.method == "GET":
        return jsonify({"message": "The offline AI Study Assistant is working. Send a POST request with JSON: {\"message\":\"your question\"}."})
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message is required."}), 400
    if len(message) > 3000:
        return jsonify({"error": "Please keep your question under 3000 characters."}), 400
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    result = ai_chat_answer(message, context, history)
    return jsonify(result), 200

@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    if "user_id" not in session:
        return jsonify({"error": "Please login before submitting feedback."}), 401
    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    comments = str(payload.get("comments", "")).strip()[:1000]
    interview_id = session.get("last_result", {}).get("interview_id")
    if rating not in range(1, 6):
        return jsonify({"error": "Rating must be between 1 and 5."}), 400
    if not comments:
        return jsonify({"error": "Please enter feedback comments."}), 400
    with db() as c:
        c.execute(
            "INSERT INTO app_feedback(user_id,interview_id,rating,comments) VALUES(?,?,?,?)",
            (session["user_id"], interview_id, rating, comments)
        )
        c.commit()
    return jsonify({"success": True, "message": "Thank you for your feedback!"})

@app.route("/api/interview/questions", methods=["POST"])
def api_questions():
    payload = request.get_json(silent=True) or {}
    role = str(payload.get("job_role", "")).strip()
    experience = str(payload.get("experience", "Fresher"))
    difficulty = str(payload.get("difficulty", "Easy"))
    interview_type = str(payload.get("interview_type", "Technical"))
    try:
        question_count = int(payload.get("question_count", 5))
    except (TypeError, ValueError):
        question_count = 5
    question_count = max(1, min(question_count, 20))
    if not role:
        return jsonify({"error": "job_role is required."}), 400

    previous_questions = []
    if "user_id" in session:
        with db() as c:
            rows = c.execute(
                """SELECT q.question FROM questions q
                   JOIN interviews i ON q.interview_id=i.id
                   WHERE i.user_id=? AND LOWER(i.job_role)=LOWER(?)
                   ORDER BY q.id DESC LIMIT 50""",
                (session["user_id"], role)
            ).fetchall()
            previous_questions = [row["question"] for row in rows]

    return jsonify(ai_generate_questions(
        role, experience, difficulty, interview_type, question_count, previous_questions
    ))

def admin_required():
    return "user_id" in session and session.get("role") == "admin"

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        with db() as c:
            user = c.execute("SELECT * FROM users WHERE email=? AND role='admin'", (request.form["email"].strip().lower(),)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session["user_id"], session["name"], session["role"] = user["id"], user["name"], user["role"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.")
    return render_template("admin_login.html")

@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    with db() as c:
        students = c.execute("""SELECT u.id, u.name, u.email,
            COUNT(i.id) AS total_interviews,
            SUM(CASE WHEN date(i.created_at)=date('now','localtime') THEN 1 ELSE 0 END) AS today_interviews,
            SUM(CASE WHEN i.created_at >= datetime('now','-7 days','localtime') THEN 1 ELSE 0 END) AS week_interviews,
            COALESCE(ROUND(AVG(i.score),1),0) AS avg_score
            FROM users u LEFT JOIN interviews i ON i.user_id=u.id
            WHERE u.role='student' GROUP BY u.id ORDER BY u.id DESC""").fetchall()
        tests = c.execute("SELECT * FROM tests ORDER BY id DESC").fetchall()
        total_students = c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
        total_interviews = c.execute("SELECT COUNT(*) FROM interviews").fetchone()[0]
        today_interviews = c.execute("SELECT COUNT(*) FROM interviews WHERE date(created_at)=date('now','localtime')").fetchone()[0]
        avg_score = c.execute("SELECT COALESCE(ROUND(AVG(score),1),0) FROM interviews").fetchone()[0]
    return render_template("admin_dashboard.html", students=students, tests=tests,
                           total_students=total_students, total_interviews=total_interviews,
                           today_interviews=today_interviews, avg_score=avg_score)

@app.route("/admin/tests/new", methods=["GET", "POST"])
def admin_new_test():
    if not admin_required():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        title = request.form["title"].strip()
        role = request.form["job_role"].strip()
        experience = request.form["experience"]
        difficulty = request.form["difficulty"]
        itype = request.form["interview_type"]
        try:
            count = max(1, min(int(request.form.get("question_count", 5)), 20))
        except ValueError:
            count = 5
        if not title or not role:
            flash("Test title and job role are required.")
            return render_template("admin_test_new.html")
        data = ai_generate_questions(role, experience, difficulty, itype, count, [])
        with db() as c:
            cur = c.execute("""INSERT INTO tests(title,job_role,experience,difficulty,interview_type,question_count,created_by)
                               VALUES(?,?,?,?,?,?,?)""", (title,role,experience,difficulty,itype,count,session["user_id"]))
            test_id = cur.lastrowid
            for q in data["questions"]:
                c.execute("INSERT INTO test_questions(test_id,question,ideal_answer) VALUES(?,?,?)",
                          (test_id, q.get("question",""), q.get("answer","")))
            c.commit()
        flash("New test created successfully.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_test_new.html")

@app.route("/tests")
def tests():
    if "user_id" not in session:
        return redirect(url_for("login"))
    with db() as c:
        rows = c.execute("SELECT * FROM tests ORDER BY id DESC").fetchall()
    return render_template("tests.html", tests=rows)

@app.route("/test/<int:test_id>")
def start_test(test_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    with db() as c:
        test = c.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
        qs = c.execute("SELECT question,ideal_answer FROM test_questions WHERE test_id=? ORDER BY id", (test_id,)).fetchall()
    if not test or not qs:
        flash("Test is not available.")
        return redirect(url_for("tests"))
    session["interview"] = {"role": test["job_role"], "experience": test["experience"],
                            "difficulty": test["difficulty"], "type": test["interview_type"],
                            "question_count": len(qs), "test_id": test_id,
                            "test_title": test["title"],
                            "questions": [{"question": q["question"], "answer": q["ideal_answer"] or ""} for q in qs],
                            "answers": []}
    return redirect(url_for("interview"))

@app.route("/dashboard")
def student_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    with db() as c:
        today = c.execute("SELECT COUNT(*) FROM interviews WHERE user_id=? AND date(created_at)=date('now','localtime')", (session["user_id"],)).fetchone()[0]
        week = c.execute("SELECT COUNT(*) FROM interviews WHERE user_id=? AND created_at>=datetime('now','-7 days','localtime')", (session["user_id"],)).fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM interviews WHERE user_id=?", (session["user_id"],)).fetchone()[0]
        avg = c.execute("SELECT COALESCE(ROUND(AVG(score),1),0) FROM interviews WHERE user_id=?", (session["user_id"],)).fetchone()[0]
        recent = c.execute("SELECT * FROM interviews WHERE user_id=? ORDER BY id DESC LIMIT 10", (session["user_id"],)).fetchall()
    progress = min(100, int(today * 100))
    return render_template("student_dashboard.html", today=today, week=week, total=total, avg=avg, progress=progress, recent=recent)

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    with db() as c:
        rows = c.execute("SELECT * FROM interviews WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("history.html", rows=rows)

init_db()

if __name__ == "__main__":
    app.run(debug=True)
