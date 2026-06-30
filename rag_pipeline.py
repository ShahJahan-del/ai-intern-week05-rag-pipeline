import os
import time
import chromadb
from chromadb.utils.embedding_functions import GoogleGeminiEmbeddingFunction
from google import genai
from google.genai import types
from datasets import load_dataset
from dotenv import load_dotenv

# Load .env file if present (local).
load_dotenv()

# Get key
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is missing!")


class RAGPipeline:
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "customer_faq"):
        """
        Initializes connection to ChromaDB and Gemini Client.
        Loads existing collection if available, otherwise creates and populates it.
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")

        self.genai_client = genai.Client(api_key=self.api_key)
        self.chroma_client = chromadb.PersistentClient(path=db_path)

        # Embedding function configuration for search queries
        self.query_ef = GoogleGeminiEmbeddingFunction(
            model_name="models/gemini-embedding-001",
            task_type="RETRIEVAL_QUERY"
        )

        # Check if the collection already exists to prevent redundant indexing
        existing_collections = [c.name for c in self.chroma_client.list_collections()]

        if collection_name not in existing_collections:
            print(f"Collection '{collection_name}' not found. Initializing indexing process...")
            self._initialize_and_populate_db(collection_name)
        else:
            print(f"Loading existing collection '{collection_name}' from disk...")
            self.collection = self.chroma_client.get_collection(
                name=collection_name,
                embedding_function=self.query_ef
            )

    def _initialize_and_populate_db(self, collection_name: str):
        """
        Downloads the dataset and populates ChromaDB in batches with a safety delay.
        """
        # Embedding function configuration for document storage
        storage_ef = GoogleGeminiEmbeddingFunction(
            model_name="models/gemini-embedding-001",
            task_type="RETRIEVAL_DOCUMENT"
        )

        self.collection = self.chroma_client.create_collection(
            name=collection_name,
            embedding_function=storage_ef
        )

        print("Downloading dataset from Hugging Face...")
        ds = load_dataset("MakTek/Customer_support_faqs_dataset")
        records = ds['train']

        ids = []
        documents = []
        metadatas = []

        print(f"Preparing data for {len(records)} FAQ entries...")
        for i, row in enumerate(records):
            faq_text = f"Question: {row['question']}\nAnswer: {row['answer']}"
            ids.append(f"faq_{i}")
            documents.append(faq_text)
            metadatas.append({"source": f"HuggingFace_FAQ_Line_{i}"})

        # Batching configuration to comply with Free Tier Rate Limits (100 requests/min)
        batch_size = 25
        total_records = len(ids)
        print(f"Inserting records in batches of {batch_size} with safety delays...")

        for i in range(0, total_records, batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]

            self.collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            print(f"  -> Records {i} to {min(i + batch_size, total_records)} indexed.")

            # Apply delay between batches to prevent Rate Limit exhaustion
            if i + batch_size < total_records:
                print("     Sleeping for 15 seconds to respect Google API quotas...")
                time.sleep(15)

        print("Indexing completed successfully!")

    def _retrieve_context(self, question: str, k: int = 2) -> tuple[str, list[str]]:
        """
        RAG Step 1: Fetches the top k most relevant text chunks from ChromaDB.
        """
        results = self.collection.query(
            query_texts=[question],
            n_results=k
        )

        if not results or not results["documents"][0]:
            return "No relevant context found.", []

        retrieved_docs = results["documents"][0]
        retrieved_metas = results["metadatas"][0]

        context_blocks = []
        sources = []

        for doc, meta in zip(retrieved_docs, retrieved_metas):
            source_name = meta.get("source", "Unknown Source")
            context_blocks.append(f"--- Excerpt from: {source_name} ---\n{doc}")
            if source_name not in sources:
                sources.append(source_name)

        context_str = "\n\n".join(context_blocks)
        return context_str, sources

    def ask(self, question: str) -> dict:
        """
        RAG Step 2: Combines context and question, then prompts Gemini for the answer.
        """
        context, sources = self._retrieve_context(question, k=2)

        # System instructions to enforce grounding and prevent hallucinations
        system_prompt = (
            "You are a helpful customer support AI assistant. You must answer the user's question "
            "based ONLY on the provided FAQ context below.\n"
            "If the context does not contain the answer or is completely irrelevant, "
            "respond exactly with: 'I don't know.'\n"
            "Keep your tone polite, professional, and factual. Always reply in English."
        )

        user_input = f"FAQ CONTEXT:\n{context}\n\nCUSTOMER QUESTION: {question}"

        response = self.genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,  # Zero temperature for deterministic responses
            )
        )

        return {
            "answer": response.text,
            "sources": sources
        }