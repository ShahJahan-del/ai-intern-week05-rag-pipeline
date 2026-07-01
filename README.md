---
title: RAG Pipeline FastAPI Service
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# ai-intern-week05-rag-pipeline
Fifth week of the AI Engineering internship learning plan

# Customer Support RAG Pipeline

This repository hosts a production-ready **Retrieval-Augmented Generation (RAG)** pipeline optimized for automated customer support delivery. The application exposes an asynchronous backend API using **FastAPI** and utilizes **ChromaDB** as a vector database, orchestrating contextual groundings with Google's **Gemini 2.5 Flash** model for response generation.

---

## API Usage Guide & Endpoints

FastAPI automatically generates an interactive documentation page. You can access it by opening your Hugging Face Space URL and appending `/docs` at the end of the address (e.g., `https://shahjahan-del-ai-intern-week05-rag-pipeline.hf.space/docs`).

### Core Endpoints

* **`GET /healthz`**: Liveness probe ensuring the FastAPI container is active, stable, and ready to receive traffic.
* **`POST /ask`**: The core RAG transaction gateway. It expects a JSON body containing a customer question, runs the semantic vector search against ChromaDB, passes the context to Gemini, and delivers a grounded response.

### How to Test the API (Step-by-Step)

1. Open the **FastAPI Swagger UI** page (`/docs`).
2. Click on the **`POST /ask`** endpoint bar to expand its options.
3. Click the **"Try it out"** button located on the top right of the route block. This unlocks the interactive request body.
4. In the **Request body** JSON editor, replace the placeholder text with your customer question. For example:
   ```json
   {
     "question": "How can I track my order status?"
   }
Click the large blue "Execute" button.

Scroll down to the Responses section:

Code 200: Indicates a successful workflow execution.

Response Body: Read the generated answer along with the document IDs used as ground truths under the sources array.

---

## Architecture Overview

The pipeline implements an isolated, self-contained RAG workflow structured into two distinct operational phases: the **Data Ingestion Loop** and the **Runtime Query-Response Chain**.

[ Data Ingestion Loop ]
Hugging Face Dataset -> Document Prep -> Gemini Embedding -> ChromaDB Storage

[ Runtime API Chain ]
User Question -> FastAPI POST /ask -> ChromaDB Query -> Context Extraction

System Instructions + Context + Question -> Gemini 2.5 Flash -> JSON Response

### 1. The Ingestion Subsystem (Data Preparation)
* **Dataset Sourcing:** At startup, the pipeline dynamically fetches the customer support FAQ dataset (`MakTek/Customer_support_faqs_dataset`) from Hugging Face.
* **Document Processing & Formatting:** Each row is mapped into structured string templates linking questions to their respective answers (`Question: ... \nAnswer: ...`), ensuring clean contextual semantic blocks.
* **Rate-Limited Semantic Vectorization:** Text sequences are passed to the `GoogleGeminiEmbeddingFunction` (`models/gemini-embedding-001`). To respect the Google Free Tier API limits (**100 requests per minute**), the system partitions data processing into sub-batches of 25 records separated by a 15-second cooling timer.
* **Vector Database Storage:** Vector embeddings, physical text documents, and source row metadata are securely written into a local **ChromaDB** (`PersistentClient`) instance.

### 2. The Retrieval & Generation Infrastructure (Runtime)
* **API Ingestion Point:** A lightweight **FastAPI** web server exposes a structured `POST /ask` endpoint accepting JSON request payloads validated via **Pydantic**.
* **Vector Semantic Retrieval:** When a query arrives, it is processed into a search embedding (`task_type="RETRIEVAL_QUERY"`) and matched against the ChromaDB collection using cosine similarity to extract the top $k=2$ closest matching documents.
* **Grounded LLM Prompt Engineering:** The extracted text blocks are coupled with strict system instructions designed to prevent hallucinations (forcing the agent to output exactly *"I don't know."* if the context is irrelevant).
* **Deterministic Execution:** The final prompt payload is dispatched to **Gemini 2.5 Flash** configured with a temperature of `0.0` to guarantee consistent, objective customer service responses.

---

## Comprehensive Q&A Validation (See 'Q&A_test_results' folder for screenshots)

The system was rigorously evaluated across 10 distinct edge cases and standard inputs. Below are the actual verified input-output payloads from the deployment testing logs:

### 1. In-Scope: Order Tracking
* **Question:** How can I track my order status?
* **Answer:** You can track your order by logging into your account and navigating to the "Order History" section. There, you will find the tracking information for your shipment.

### 2. In-Scope: Account Registration
* **Question:** How can I create an account?
* **Answer:** To create an account, click on the "Sign up" button on the top right corner of our website and follow the instructions to complete the registration process.

### 3. In-Scope: Joint Query (Payments & Returns)
* **Question:** Which payments do you accept and can I return stuff?
* **Answer:** We accept major credit cards, debit cards, and Paypal as payment methods for online orders. Our return policy allows you to return products within 30 days of purchase for a full refund, provided they are in their original condition and packaging.

### 4. In-Scope: Order Cancellation Intent
* **Question:** I want to cancel my order.
* **Answer:** You can cancel your order if it has not been shipped yet. Please contact our customer support team with your order details, and they will assist you with the cancellation process.

### 5. Out-of-Scope: Ambiguous International Query
* **Question:** I am currently abroad, how long would shipping take?
* **Answer:** I don't know.

### 6. Out-of-Scope: Missing Specific Context
* **Question:** How long does international shipping take?
* **Answer:** I don't know.

### 7. In-Scope: Lost Package Escalation
* **Question:** My package was lost!
* **Answer:** If your package was lost, please contact our customer support team. We will initiate an investigation and take necessary steps to resolve the issue.

### 8. In-Scope: Phone Ordering Policy
* **Question:** Can I order by phone without creating an account?
* **Answer:** Unfortunately, we do not accept orders over the phone. Please place your order through our website for a smooth and secure transaction.

### 9. Out-of-Scope: Philosophical Guardrail Test
* **Question:** To be or not to be?
* **Answer:** I don't know.

### 10. Out-of-Scope: Meta/Identity Query
* **Question:** Are you customer support?
* **Answer:** I don't know.

---

## Noted System Limitations

Through evaluating over 10+ edge cases, the following core pipeline limitations have been identified:

1. **Information Granularity & Joint Queries:** When queries combine two disparate topics (e.g., Question 3 combining payment methods and return windows), the vector database must pull multiple distinct context blocks. If $k$ is set too low (e.g., $k=1$), the system could miss one half of the answer due to context truncation.
2. **Strict Semantic Matching & Zero-Tolerance Guardrails:** The strict system instructions effectively neutralize hallucinations, as evidenced by Cases 5, 6, 9, and 10 returning a clean *"I don't know."*. However, this makes the model hyper-conservative. Slight phrasing mismatches or semantic gaps cause the system to reject the answer rather than attempt a helpful generalization.
3. **Cold-Boot Indexing Latency:** Because the database is built programmatically at startup to circumvent Hugging Face file restrictions, the API suffers from a ~2-minute cold-boot delay while vectorizing the 200 elements under the Google Free Tier rate limits.