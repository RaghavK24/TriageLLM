# DeBERTa Training Data — Labeling Guide for Gemini Pro

## How to Use

1. Open **Gemini Pro** (or any capable LLM)
2. Copy ONE batch at a time (everything between the `═══ COPY` lines)
3. Paste it into Gemini Pro
4. Copy the JSON output Gemini gives you
5. Save it as a file in `training/batches/`:
   - Batch 1 → `training/batches/batch_01_results.json`
   - Batch 2 → `training/batches/batch_02_results.json`
   - ... and so on
6. Repeat for all 8 batches
7. Run: `python training/merge_labels.py`
8. Run: `python training/train_deberta.py`

> **Tip:** If Gemini wraps the output in \`\`\`json ... \`\`\`, that's fine —
> the merge script strips it automatically.

---

## Batch 1 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. Hi, how are you?
2. What is the capital of France?
3. Tell me a joke.
4. What does API stand for?
5. How many continents are there?
6. What is a variable in programming?
7. Name three programming languages.
8. What year was Python first released?
9. Convert 100 Celsius to Fahrenheit.
10. What is a database?
11. Who invented the telephone?
12. What is the largest planet in our solar system?
13. Define the term 'latency'.
14. Compare and contrast microservices architecture with a monolithic approach. Analyze the trade-offs in terms of scalability, deployment complexity, team organization, and debugging difficulty. Provide concrete examples of when each approach is preferable.
15. Design a URL shortening service like bit.ly. Walk through the system design including the database schema, hashing strategy, handling collisions, redirect flow, and analytics. Discuss how you would scale it to handle 10 billion URLs.
16. Explain the CAP theorem and derive why a distributed system cannot simultaneously guarantee all three properties. Then analyze how DynamoDB, Cassandra, and PostgreSQL each make different trade-offs.
17. Given the following recursive function, analyze its time and space complexity, then refactor it to use dynamic programming and prove the optimized version runs in O(n):\n```python\ndef fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n```
18. Design an in-memory LRU cache that supports O(1) get and put operations. Explain why a hash map alone isn't sufficient and how combining it with a doubly-linked list solves the problem. Then extend your design to be thread-safe.
19. Derive the expected number of hash collisions when inserting n items into a hash table of size m using uniform hashing. Then compute the load factor threshold at which linear probing degrades to O(n) expected lookup time.
20. Explain the difference between optimistic and pessimistic concurrency control in databases. Analyze when each is preferable and design a hybrid approach that switches between them based on observed contention.
21. Analyze the trade-offs between B-trees and LSM-trees for database indexing. Explain write amplification, read amplification, and space amplification for each. Propose a strategy for a system that is 90% reads, 10% writes.
22. What is the difference between HTTP and HTTPS?
23. What is an algorithm?
24. What does SQL stand for?
25. What is a compiler?

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 2 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. What is an operating system?
2. What is cloud computing?
3. Define the term 'bandwidth'.
4. What is an IP address?
5. What is DNS?
6. What is a load balancer?
7. What is the difference between TCP and UDP?
8. What is a microservice?
9. List three types of databases.
10. What is the file extension for Python files?
11. How do I create a virtual environment in Python?
12. How do I start a new Git repository?
13. What is a for loop? Give a simple example.
14. Design a real-time chat application like WhatsApp. Cover the architecture for message delivery, read receipts, group chats, media sharing, and end-to-end encryption. Analyze how you would handle millions of concurrent WebSocket connections.
15. Design a distributed task queue system. Explain how you would handle task prioritization, retry logic with exponential backoff, dead letter queues, and exactly-once execution semantics. Analyze at-least-once vs exactly-once delivery.
16. Design a content delivery network (CDN). Explain cache invalidation, content routing, origin shielding, and edge computing. Derive the cache hit ratio needed to achieve a 95% reduction in origin server load.
17. Design a recommendation engine for an e-commerce platform. Compare collaborative filtering, content-based filtering, and hybrid approaches. Explain the cold-start problem and propose solutions.
18. Design a distributed log aggregation system that handles 100TB of logs per day. Compare Elasticsearch vs ClickHouse for this use case and justify your choice with specific technical trade-offs.
19. Analyze the time complexity of Dijkstra's algorithm with a Fibonacci heap vs a binary heap. Derive the conditions under which the Fibonacci heap provides a meaningful speedup and explain why it's rarely used in practice.
20. Explain the difference between BFS and DFS, their time and space complexities, and when each is preferred. Then design a solution for finding the shortest path in an unweighted graph with cycles, proving its correctness.
21. Given a stream of integers, design a data structure that supports O(1) insert and O(1) median finding. Explain why a two-heap approach works, prove its correctness, and analyze the amortized complexity.
22. What is the square root of 144?
23. List the primary colors.
24. Name three cloud providers.
25. What is the next number in the sequence: 2, 4, 6, 8, ?

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 3 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. Hello!
2. What's your name?
3. What is the speed of light?
4. Who wrote Romeo and Juliet?
5. What is the chemical formula for water?
6. What is the tallest mountain in the world?
7. How many planets are in the solar system?
8. What language is spoken in Brazil?
9. What is the currency of Japan?
10. Who painted the Mona Lisa?
11. What is the boiling point of water in Fahrenheit?
12. How many states are in the US?
13. What is the smallest country in the world?
14. Refactor the following Python function for readability and reduced cyclomatic complexity. Explain each change:\n```python\ndef process(data, mode, flag1, flag2):\n    result = []\n    for item in data:\n        if mode == 'A':\n            if flag1:\n                if item > 0:\n                    result.append(item * 2)\n                else:\n                    result.append(0)\n            else:\n                result.append(item)\n        elif mode == 'B':\n            if flag2:\n                result.append(item ** 2)\n            else:\n                if flag1:\n                    result.append(item + 1)\n                else:\n                    result.append(item - 1)\n    return result\n```
15. Analyze the following code for potential race conditions, memory leaks, and performance issues. Propose fixes:\n```python\nimport threading\nclass ConnectionPool:\n    _instance = None\n    def __new__(cls):\n        if cls._instance is None:\n            cls._instance = super().__new__(cls)\n            cls._instance.connections = []\n            cls._instance.lock = threading.Lock()\n        return cls._instance\n    def get_connection(self):\n        if self.connections:\n            return self.connections.pop()\n        return create_new_connection()\n    def release(self, conn):\n        self.connections.append(conn)\n```
16. Review this SQL query for performance issues. Explain what indexes would help and rewrite it optimally:\n```sql\nSELECT u.name, u.email,\n  (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) as order_count,\n  (SELECT MAX(created_at) FROM orders o WHERE o.user_id = u.id) as last_order\nFROM users u WHERE u.status = 'active'\nORDER BY u.created_at DESC LIMIT 100;\n```
17. Debug this async Python code that intermittently produces incorrect results. Identify the concurrency bug and provide a corrected version:\n```python\nimport asyncio\nclass Counter:\n    def __init__(self): self.count = 0\n    async def increment(self):\n        current = self.count\n        await asyncio.sleep(0.001)\n        self.count = current + 1\nasync def main():\n    counter = Counter()\n    await asyncio.gather(*[counter.increment() for _ in range(100)])\n    print(f'Expected 100, got {counter.count}')\n```
18. Prove that any comparison-based sorting algorithm requires Ω(n log n) comparisons in the worst case. Use the decision tree model and derive the information-theoretic lower bound.
19. Derive Bayes' theorem from first principles and apply it to compute the probability that a medical test result is a true positive given a sensitivity of 99%, specificity of 95%, and disease prevalence of 1%.
20. Derive the birthday paradox probability — the minimum number of people needed for a 50% chance of a shared birthday. Then apply this to analyze hash collision probabilities in a hash table with 2^32 buckets.
21. Prove that the greedy algorithm for the activity selection problem produces an optimal solution using an exchange argument.
22. What element has the symbol 'Fe'?
23. What is the capital of Australia?
24. Who discovered penicillin?
25. What is the longest river in the world?

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 4 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. Good morning!
2. I'm bored.
3. Tell me a fun fact.
4. What does HTML stand for?
5. Name five fruits.
6. What is 7 times 8?
7. Translate 'thank you' to French.
8. What is version control?
9. How do I print 'Hello World' in Java?
10. How do I install a pip package?
11. What is the difference between a list and a tuple in Python?
12. What is the purpose of a .gitignore file?
13. Describe what a primary key is in a database.
14. Design a payment processing system that handles credit card transactions. Explain idempotency, double-spend prevention, PCI compliance, and how you would handle partial failures across microservices using the saga pattern.
15. Design a feature flag system for a large-scale application. Explain percentage rollouts, A/B testing, user segmentation, and real-time flag updates. Analyze consistency requirements across distributed services.
16. Design a search autocomplete system that serves suggestions within 100ms. Cover data structures (tries vs inverted indexes), ranking algorithms, personalization, and trending queries. Derive the memory requirements for 100 million queries.
17. Architect a multi-tenant SaaS application. Explain the trade-offs between shared database, schema-per-tenant, and database-per-tenant approaches. Analyze query performance, data isolation, and operational complexity at 100,000 tenants.
18. Explain how garbage collection works in the JVM. Compare G1, ZGC, and Shenandoah collectors. Derive the relationship between heap size, pause times, and throughput for a latency-sensitive app with a p99 target of 10ms.
19. Analyze the security implications of JWT vs session-based authentication. Cover token theft, replay attacks, revocation strategies, and scalability. Derive the expected number of valid-but-revoked tokens at any time under a 1-hour lifetime and 0.1% revocation rate.
20. Design a disaster recovery strategy for a cloud-native application across three AWS regions. Cover RPO/RTO targets, active-active vs active-passive replication, DNS failover, and cost optimization.
21. Explain how vector databases work internally. Compare HNSW, IVF-PQ, and brute-force search in terms of recall, latency, and memory usage. Propose a tuning strategy for 10 million embeddings and a 50ms latency budget.
22. What is the difference between frontend and backend?
23. What is the difference between GET and POST requests?
24. What is the role of a product manager?
25. Explain what caching is in simple terms.

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 5 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. What is the difference between authentication and authorization?
2. Give me a brief overview of what Kubernetes does.
3. What is a container in Docker?
4. What is a firewall?
5. How do I check my Python version?
6. How do I create a list in Python?
7. How do I make text bold in Markdown?
8. How do I declare a variable in JavaScript?
9. How do I import a module in Python?
10. What are our support hours?
11. What version introduced tiered pricing?
12. When was v3.2.0 released?
13. What is an API endpoint?
14. You are building a multi-tenant SaaS application. A customer reports intermittent 504 Gateway Timeout errors during peak hours. Walk through your debugging methodology step by step, covering load balancer logs, application tracing, database slow query analysis, and connection pool exhaustion. Propose both short-term mitigations and long-term architectural fixes.
15. Design a CI/CD pipeline for a monorepo containing 5 microservices, 2 shared libraries, and a frontend. Explain selective builds, parallel test execution, canary deployments, and rollback. Analyze monorepo tooling (Bazel, Nx) vs polyrepo trade-offs.
16. Explain how OAuth 2.0 and OpenID Connect work together. Walk through Authorization Code flow with PKCE, explain why implicit flow was deprecated, and propose a token refresh strategy balancing security with UX.
17. Design a data pipeline processing 1TB of clickstream data daily. Compare batch (Spark) vs streaming (Flink), explain exactly-once semantics in Kafka, and propose a schema evolution strategy.
18. Explain how database sharding works. Compare range-based, hash-based, and directory-based strategies. Analyze cross-shard joins, rebalancing, and hot spots. Propose a sharding key for a social media app with 500 million users.
19. Design a blue-green deployment strategy for a stateful app with PostgreSQL. Explain backward-compatible schema migrations, connection draining, and automatic rollback. Compare with canary deployments.
20. Optimize a machine learning pipeline that takes 8 hours to train. Propose optimizations at each stage: data loading, feature engineering, training (data parallelism, mixed-precision, gradient accumulation), and evaluation. Derive expected speedup for each.
21. Design a comprehensive testing strategy for distributed microservices. Cover unit tests, integration tests, contract tests, end-to-end tests, chaos engineering, and performance tests. Explain the testing pyramid and trade-offs with CI/CD speed.
22. Convert 1 kilometer to miles.
23. What are the vowels in the English alphabet?
24. What is the opposite of 'hot'?
25. Sort these numbers: 5, 2, 8, 1, 9.

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 6 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. Hey, what's up?
2. Thanks for your help!
3. What can you do?
4. Tell me something interesting.
5. Who is the CEO of Apple?
6. What year did World War 2 end?
7. What continent is Egypt in?
8. What is the largest desert in the world?
9. What is the population of India roughly?
10. Summarize what Git does in one sentence.
11. Write a one-sentence summary of what Python is.
12. What is 15% of 200?
13. Name three web browsers.
14. Analyze this React component for performance anti-patterns, unnecessary re-renders, and potential bugs. Refactor using hooks best practices:\n```jsx\nfunction UserDashboard({ userId }) {\n  const [user, setUser] = useState(null);\n  const [posts, setPosts] = useState([]);\n  useEffect(() => {\n    fetch(`/api/users/${userId}`).then(r => r.json()).then(setUser);\n    fetch(`/api/users/${userId}/posts`).then(r => r.json()).then(setPosts);\n  });\n  const total = posts.reduce((acc, p) => acc + p.likes, 0);\n  return <div>{user?.name} - {total} likes</div>;\n}\n```
15. Review this Dockerfile for security vulnerabilities, layer optimization issues, and best practice violations. Rewrite it for production:\n```dockerfile\nFROM python:3.11\nCOPY . /app\nWORKDIR /app\nRUN pip install -r requirements.txt\nRUN apt-get update && apt-get install -y curl vim\nENV SECRET_KEY=mysecretkey123\nEXPOSE 8000\nCMD python app.py\n```
16. Refactor this JavaScript promise chain into clean async/await with proper error handling, retry logic, and timeout. Explain differences in error propagation:\n```javascript\nfunction fetchUserData(userId) {\n  return fetch(`/api/users/${userId}`)\n    .then(r => r.json())\n    .then(user => fetch(`/api/users/${userId}/preferences`)\n      .then(r => r.json())\n      .then(prefs => fetch(`/api/users/${userId}/notifications`)\n        .then(r => r.json())\n        .then(notifs => ({...user, prefs, notifs}))))\n    .catch(e => console.log(e))\n}\n```
17. Explain the transformer architecture from first principles. Derive the self-attention mechanism mathematically, explain why positional encodings are necessary, analyze the O(n²) complexity, and compare sparse attention and linear attention approaches.
18. Analyze the trade-offs between gRPC and REST for microservice communication. Cover serialization overhead, streaming, code generation, debugging tooling, and browser compatibility. Propose a decision matrix.
19. Explain how Kubernetes networking works, including pod-to-pod communication, services, ingress controllers, and network policies. Compare CNI plugins (Calico, Cilium, Flannel) and propose a network architecture for a multi-tenant cluster.
20. Derive the expected cost savings per 1000 requests for a two-tier router that sends fraction p of traffic to a cheap model at $0.10/MTok and (1-p) to an expensive model at $3.00/MTok, assuming 500 tokens per response. Compute p such that cost is 20% of always-expensive baseline.
21. Design a privacy-compliant data architecture for GDPR, CCPA, and data residency. Explain data subject access requests, right to erasure, and consent management across a distributed system. Analyze performance impact of encryption.
22. What is the difference between Java and JavaScript?
23. How many hours are in a day?
24. What is the plural of 'mouse'?
25. List three types of machine learning.

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 7 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. What is machine learning in one sentence?
2. What is a REST API?
3. What is the difference between == and === in JavaScript?
4. How do I create a new file in Python?
5. What is a foreign key in a database?
6. What is the largest ocean?
7. Name three types of cloud services (IaaS, PaaS, SaaS).
8. What is a webhook?
9. How do I write a comment in Python?
10. What is the difference between RAM and ROM?
11. What does CRUD stand for?
12. What is a CDN?
13. What is localhost?
14. Walk me through what happens when you type 'google.com' in a browser and press Enter. Cover every layer from DNS resolution through TCP/TLS handshake, HTTP request, server processing, response rendering, and JavaScript execution.
15. Explain how Python's import system works, including module search paths, __init__.py, relative vs absolute imports, circular imports, and the module cache. Analyze common import errors and debugging strategies.
16. Explain how Git works internally. Cover the object model (blobs, trees, commits), refs, the index/staging area, and how merge, rebase, and cherry-pick work at the object level.
17. Explain step by step how a neural network learns, from random initialization through forward propagation, loss computation, backpropagation, and weight updates. Derive the chain rule for a 2-layer network and explain the vanishing gradient problem.
18. Explain how Docker containers work at the Linux kernel level, covering namespaces (PID, network, mount, UTS, IPC, user), cgroups, union filesystem (overlay2), and seccomp profiles. Analyze container escape vectors.
19. Analyze the complete data flow in a Kafka-based event streaming system, from producer acknowledgment modes through partitioning, replication, consumer group coordination, offset management, and exactly-once semantics.
20. You have a PostgreSQL database that has grown to 5TB and queries are slowing down. Walk through systematic optimization: EXPLAIN ANALYZE interpretation, index strategy, query rewriting, partitioning, materialized views, and connection pooling. Estimate expected improvement for each.
21. Design a comprehensive monitoring and alerting system for microservices. Cover the four golden signals, distributed tracing with OpenTelemetry, log aggregation, and anomaly detection. Propose alerting strategy minimizing false positives while maintaining 99.99% detection.
22. Explain how HTTPS and TLS 1.3 work step by step. Compare with TLS 1.2, explain why 0-RTT resumption is faster but vulnerable to replay attacks, and propose mitigations.
23. What is the difference between HTTP/1.1 and HTTP/2?
24. What is an environment variable?
25. How do I install Node.js?

═══════════════════ COPY ABOVE THIS LINE ═══════════════════

---

## Batch 8 of 8

═══════════════════ COPY BELOW THIS LINE ═══════════════════

You are a prompt complexity judge for an LLM routing system that decides whether to send a user's prompt to a cheap/fast model or an expensive/powerful model.

**Classification rules:**

- **"weak"** = A small, fast model (like Llama 3.1 8B) can handle this. Examples:
  - Simple factual questions, definitions, lookups
  - Greetings, chit-chat, basic conversation
  - Basic arithmetic, conversions, short lists
  - Simple how-to with straightforward answers
  - Single-concept explanations that don't require deep reasoning

- **"strong"** = Only a large, powerful model (like Claude Sonnet or GPT-4o) can answer well. Examples:
  - Multi-step reasoning, analysis, or synthesis
  - System design, architecture questions
  - Code review, debugging, refactoring with explanations
  - Mathematical proofs or derivations
  - Compare-and-contrast requiring deep domain knowledge
  - Complex "step by step" technical explanations

For each prompt below, classify it and explain why in 1-2 sentences.

**Output ONLY a JSON array** with this exact format — no other text:
```json
[
  {"id": 1, "prompt": "<the original prompt>", "label": "weak", "reasoning": "Simple greeting."},
  {"id": 2, "prompt": "<the original prompt>", "label": "strong", "reasoning": "Requires multi-step analysis."}
]
```

Here are 25 prompts to classify:

1. What?
2. Hi there, nice to meet you.
3. How's it going?
4. Hello, can you help me?
5. Goodbye.
6. What day of the week is Christmas 2026?
7. What is 2 + 2?
8. What color is the sky?
9. Translate 'hello' to Japanese.
10. What is Python used for?
11. How do I make a list in HTML?
12. What does JSON stand for?
13. What is the expense reimbursement policy?
14. Analyze the trade-offs between different SQL isolation levels (READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE). For each, explain what anomalies it allows, give a concrete bug example in e-commerce, and derive the performance overhead of upgrading from READ COMMITTED to SERIALIZABLE.
15. Design a migration strategy for moving a monolithic application to microservices. Cover the strangler fig pattern, database decomposition, event-driven communication, and distributed transactions. Propose a 6-month phased plan.
16. Explain how a relational database processes a SQL query step by step, from parsing through planning, optimization (join ordering, index selection), and execution. Analyze how the optimizer chooses between nested loop, hash, and merge joins.
17. Explain the mathematical foundations of gradient descent optimization. Derive the convergence rate for convex functions, explain learning rate scheduling, compare Adam vs SGD with momentum, and analyze the saddle point problem.
18. Prove that the Halting Problem is undecidable using a diagonalization argument. Then explain the implications for static analysis tools and why perfect bug detection is impossible.
19. Derive the master theorem for divide-and-conquer recurrences T(n) = aT(n/b) + f(n). Apply it to analyze merge sort, Strassen's matrix multiplication, and binary search.
20. Explain the internals of the V8 JavaScript engine, including the parser, AST, Ignition interpreter, TurboFan compiler, and hidden classes. Analyze inline caching and deoptimization triggers.
21. Design a search engine for a 100-million document corpus. Cover crawling, indexing (inverted index construction), ranking (TF-IDF, BM25, learning-to-rank), and serving. Handle near-duplicate detection, freshness, and multi-language support.
22. Explain step by step how to implement binary search correctly, including edge cases (empty arrays, single elements, duplicates, off-by-one errors). Then prove termination and correctness.
23. What is an adaptive router?
24. What is load fraction?
25. What does RAG stand for?

═══════════════════ COPY ABOVE THIS LINE ═══════════════════
