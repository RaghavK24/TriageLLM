# Adaptive Router — Eval Summary

## Latency and cost vs concurrency

| N | avg (adapt) | avg (base) | p95 (adapt) | p95 (base) | cost (adapt) | cost (base) | latency Δ | cost Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 1332 ms | 2200 ms | 3095 ms | 2671 ms | $0.0012 | $0.0037 | **-39%** | **-68%** |
| 15 | 1285 ms | 2329 ms | 3084 ms | 3691 ms | $0.0039 | $0.0147 | **-45%** | **-73%** |
| 30 | 1651 ms | 3291 ms | 3610 ms | 5798 ms | $0.0079 | $0.0406 | **-50%** | **-81%** |
| 50 | 1926 ms | 4613 ms | 5547 ms | 7782 ms | $0.0507 | $0.0728 | **-58%** | **-30%** |

## Tier distribution (adaptive)

| N | weak (cheap) | strong (expensive) |
|---:|---:|---:|
| 5 | 5 | 0 |
| 15 | 14 | 1 |
| 30 | 27 | 3 |
| 50 | 41 | 9 |

## Routing accuracy on hand-labeled prompts

**48 / 50 = 96.0%**

| Expected | Got | Prompt |
|---|---|---|
| weak | weak ✅ | Hello! Are you online? |
| weak | weak ✅ | What is the maximum reimbursement amount for team lunches? |
| weak | weak ✅ | Where do I submit my Q3 quarterly review? |
| weak | weak ✅ | Does the new firewall block port 5432 by default? |
| weak | weak ✅ | Who is the engineering manager for the Orion subsystem? |
| weak | weak ✅ | What does the abbreviation 'TTFB' stand for in our metrics dashboard? |
| weak | weak ✅ | Please summarize the core features of the v4.5.1 patch release. |
| weak | weak ✅ | How do I request a new AWS IAM role for my test environment? |
| weak | weak ✅ | Is the VPN down right now? |
| weak | weak ✅ | What is the IP address of the staging database server? |
| weak | weak ✅ | Can you list the observed symptoms of the memory leak from yesterday's outage? |
| weak | weak ✅ | When is the next all-hands meeting scheduled? |
| weak | weak ✅ | How many days of bereavement leave are full-time employees entitled to? |
| weak | weak ✅ | Give me the direct link to the Jira board for Project Delta. |
| weak | weak ✅ | What is our standard internal SLA for responding to Sev-2 tickets? |
| weak | weak ✅ | Do we support Python 3.12 in the new deployment environment yet? |
| weak | weak ✅ | What is the dress code for the upcoming client visit? |
| weak | weak ✅ | How do I clear the local Redis cache on my dev machine? |
| weak | weak ✅ | Give me a brief summary of the onboarding process for contractors. |
| weak | weak ✅ | Which Slack channel is used for deployment alerts? |
| weak | weak ✅ | Is GitHub Copilot approved for use on proprietary codebases? |
| weak | weak ✅ | What is the default retention period for our S3 bucket logs? |
| weak | weak ✅ | Hi, I need help resetting my internal portal password. |
| weak | weak ✅ | Who do I contact if my laptop charger is broken? |
| weak | weak ✅ | Are we observing Martin Luther King Jr. Day as a paid holiday this year? |
| weak | strong ❌ | List the three main competitors in our Q4 market analysis document. |
| weak | weak ✅ | How can I update my emergency contact information in Workday? |
| weak | weak ✅ | What is the procedure for expensing home office equipment? |
| weak | weak ✅ | Where is the documentation for the user authentication API? |
| weak | weak ✅ | Which version of Postgres are we running in production? |
| weak | weak ✅ | Who handles the procurement of new server hardware? |
| weak | weak ✅ | Can I use my corporate card for an Uber ride from the airport? |
| weak | weak ✅ | What was the total revenue reported in the last fiscal year? |
| weak | weak ✅ | Are pets allowed in the downtown headquarters building? |
| weak | weak ✅ | How do I install the corporate root certificate on my iPhone? |
| weak | weak ✅ | What is the name of the new Chief Marketing Officer? |
| weak | weak ✅ | What time does the cafeteria stop serving lunch? |
| weak | strong ❌ | Provide the command to restart the Docker daemon on Ubuntu. |
| weak | weak ✅ | Is the new logo design approved for external marketing materials yet? |
| weak | weak ✅ | Thank you for the help earlier! |
| strong | strong ✅ | Design a highly available distributed locking service using Redis. Explain the t… |
| strong | strong ✅ | Calculate the expected queue length for an M/M/1 queuing system with an arrival … |
| strong | strong ✅ | Compare and contrast the internal architecture of Apache Kafka with RabbitMQ, sp… |
| strong | strong ✅ | Refactor this legacy C++ code to use modern C++20 paradigms (Concepts, Ranges). … |
| strong | strong ✅ | Derive the mathematical proof for the backpropagation algorithm in a multi-layer… |
| strong | strong ✅ | Architect a multi-region, active-active database failover strategy for a Postgre… |
| strong | strong ✅ | Analyze the time complexity of the A* search algorithm using an inadmissible heu… |
| strong | strong ✅ | Write a comprehensive Python script that uses the AST module to parse another Py… |
| strong | strong ✅ | Evaluate the security implications of using JWTs for session management compared… |
| strong | strong ✅ | Design an intricate microservices architecture for a real-time ride-sharing appl… |