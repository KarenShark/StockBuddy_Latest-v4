import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI


def _memory_disabled(config: dict) -> bool:
    if config.get("memory_enabled") is False:
        return True
    v = os.getenv("STOCKBUDDY_DISABLE_MEMORY", "")
    return v.lower() in ("1", "true", "yes")


def _embedding_api_key_and_headers(config: dict):
    """Align with trading_graph ChatOpenAI: same key + headers as main LLM."""
    provider = str(config.get("llm_provider", "")).lower()
    api_key = os.getenv("OPENAI_API_KEY")
    extra_headers = {}
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY") or api_key
        extra_headers = {
            "HTTP-Referer": "https://github.com/KarenShark/StockBuddy_Latest-v4",
            "X-Title": "StockBuddy",
        }
    return api_key, extra_headers


class FinancialSituationMemory:
    def __init__(self, name, config):
        self._disabled = _memory_disabled(config)
        self.client = None
        self.embedding = config.get("embedding_model") or (
            "nomic-embed-text"
            if config.get("backend_url") == "http://localhost:11434/v1"
            else "text-embedding-3-small"
        )

        if not self._disabled:
            api_key, extra_headers = _embedding_api_key_and_headers(config)
            kwargs = {"base_url": config["backend_url"], "api_key": api_key}
            if extra_headers:
                kwargs["default_headers"] = extra_headers
            self.client = OpenAI(**kwargs)

        # Skip ChromaDB entirely when memory is disabled — avoids parallel-init
        # race on PersistentClient (RustBindingsAPI concurrency crash).
        if self._disabled:
            self.chroma_client = None
            self.situation_collection = None
            return

        persist_directory = os.path.join(config["project_dir"], "data", "chromadb")
        os.makedirs(persist_directory, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        self.situation_collection = self.chroma_client.get_or_create_collection(name=name)

    def get_embedding(self, text):
        """Get OpenAI embedding for a text"""
        if self._disabled or self.client is None:
            raise RuntimeError("embedding disabled or client not configured")
        response = self.client.embeddings.create(
            model=self.embedding, input=text
        )
        return response.data[0].embedding

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""
        if self._disabled:
            return

        situations = []
        advice = []
        ids = []
        embeddings = []

        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        self.situation_collection.add(
            documents=situations,
            metadatas=[{"recommendation": rec} for rec in advice],
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using OpenAI embeddings"""
        if self._disabled or self.client is None:
            return []

        query_embedding = self.get_embedding(current_situation)

        results = self.situation_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_matches,
            include=["metadatas", "documents", "distances"],
        )

        matched_results = []
        for i in range(len(results["documents"][0])):
            matched_results.append(
                {
                    "matched_situation": results["documents"][0][i],
                    "recommendation": results["metadatas"][0][i]["recommendation"],
                    "similarity_score": 1 - results["distances"][0][i],
                }
            )

        return matched_results


if __name__ == "__main__":
    from stockbuddy.default_config import DEFAULT_CONFIG

    matcher = FinancialSituationMemory("demo", DEFAULT_CONFIG)

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors 
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")
