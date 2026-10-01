#!/usr/bin/env python3
"""
Knowledge Base
==============
Offline RAG knowledge base with:
- 1033 cybersecurity facts (grades 5 through college)
- STEM demo facts
Uses ChromaDB for vector search.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

try:
    from chromadb import PersistentClient
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent


# STEM demo facts (always available)
STEM_FACTS = [
    {"id": "stem_001", "text": "A rocket works by expelling gas out of a nozzle at high speed. This creates thrust that pushes the rocket forward, following Newton's Third Law: for every action, there is an equal and opposite reaction.", "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_002", "text": "The International Space Station orbits Earth about every 90 minutes. Astronauts aboard experience weightlessness because they are in constant free fall around the planet.", "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_003", "text": "Octopuses have three hearts and blue blood. Two hearts pump blood to the gills, while the third pumps it to the rest of the body. Their blue blood comes from a copper-based protein called hemocyanin.", "metadata": {"topic": "animals", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_004", "text": "Honey bees communicate through a waggle dance. When a bee finds a good source of nectar, she returns to the hive and performs a dance that tells other bees the direction and distance to the flowers.", "metadata": {"topic": "animals", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_005", "text": "A rainbow forms when sunlight passes through water droplets in the air. The light bends (refracts) and splits into different colors because each color bends at a slightly different angle.", "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_006", "text": "Sound travels as waves through air. When you speak, your vocal cords vibrate and create pressure waves that travel to someone's ear, where they are converted back into sound.", "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_007", "text": "The light bulb was improved by Thomas Edison in 1879, but many inventors contributed to its development. Edison's key innovation was using a carbon filament that could glow for many hours.", "metadata": {"topic": "inventions", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_008", "text": "The telephone was invented by Alexander Graham Bell in 1876. His first words over the phone were: 'Mr. Watson, come here, I want to see you!'", "metadata": {"topic": "inventions", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_009", "text": "Photosynthesis is how plants make their own food. They use sunlight, carbon dioxide from the air, and water to create sugar and release oxygen as a byproduct.", "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"}},
    {"id": "stem_010", "text": "The water cycle moves water around Earth. Water evaporates from oceans, forms clouds, falls as rain or snow, and flows back to the oceans, repeating endlessly.", "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"}},
]


class KnowledgeBase:
    """Offline knowledge base with vector search (RAG)."""
    
    def __init__(
        self,
        collection_name: str = "knowledge",
        persist_path: str = None,
        cybersec_path: str = None
    ):
        """
        Initialize knowledge base.
        
        Args:
            collection_name: ChromaDB collection name
            persist_path: Path to persistent storage
            cybersec_path: Path to cybersecurity facts JSON
        """
        self.collection_name = collection_name
        self.persist_path = Path(persist_path) if persist_path else PROJECT_ROOT / "data" / "chroma"
        self.cybersec_path = Path(cybersec_path) if cybersec_path else PROJECT_ROOT / "data" / "cybersecurity_facts.json"
        self.client = None
        self.collection = None
        self.total_facts = 0
        
    def initialize(self):
        """Initialize ChromaDB and load knowledge."""
        if not CHROMA_AVAILABLE:
            print("⚠ ChromaDB not installed - using fallback search")
            print("  Install with: pip install chromadb")
            self._fallback_mode = True
            return
        
        try:
            self.client = PersistentClient(path=str(self.persist_path))
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            print(f"✓ Knowledge base initialized")
            print(f"  Documents: {self.collection.count()}")
            
            # Load knowledge if empty
            if self.collection.count() == 0:
                print("  Building knowledge index (first run, ~30 sec)...")
                self._load_all_knowledge()
                
        except Exception as e:
            print(f"⚠ Knowledge base error: {e}")
            self.collection = None
            self._fallback_mode = True
            
    def _load_all_knowledge(self):
        """Load all knowledge sources into ChromaDB."""
        all_facts = []
        
        # 1. STEM facts
        all_facts.extend(STEM_FACTS)
        print(f"  ✓ STEM facts: {len(STEM_FACTS)}")
        
        # 2. Cybersecurity facts (1000+)
        cybersec = self._load_cybersec_facts()
        all_facts.extend(cybersec)
        print(f"  ✓ Cybersecurity facts: {len(cybersec)}")
        
        # Add everything to collection
        self.collection.add(
            documents=[f["text"] for f in all_facts],
            metadatas=[f["metadata"] for f in all_facts],
            ids=[f["id"] for f in all_facts]
        )
        
        self.total_facts = len(all_facts)
        print(f"  ✓ Total indexed: {self.total_facts} facts")
        
    def _load_cybersec_facts(self) -> List[Dict[str, Any]]:
        """Load cybersecurity facts from JSON file."""
        facts = []
        
        if not self.cybersec_path.exists():
            print(f"  ⚠ Cybersecurity file not found: {self.cybersec_path}")
            return facts
        
        try:
            with open(self.cybersec_path) as f:
                data = json.load(f)
            
            for level, categories in data.items():
                if level == "metadata":
                    continue
                for category, items in categories.items():
                    for item in items:
                        if isinstance(item, dict):
                            facts.append({
                                "id": item["id"],
                                "text": item["fact"],
                                "metadata": {
                                    "topic": category,
                                    "grade_level": level,
                                    "difficulty": item.get("difficulty", "unknown"),
                                    "source": "cybersecurity",
                                    "keywords": ",".join(item.get("keywords", []))
                                }
                            })
        except Exception as e:
            print(f"  ⚠ Error loading cybersecurity facts: {e}")
            
        return facts
        
    def query(
        self,
        question: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Query knowledge base for relevant information.
        
        Args:
            question: User's question
            top_k: Number of results to return
            
        Returns:
            List of relevant knowledge entries
        """
        if not self.collection:
            return self._fallback_query(question, top_k)
            
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=top_k
            )
            
            formatted = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted.append({
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0
                    })
                    
            return formatted
            
        except Exception as e:
            print(f"Query error: {e}")
            return []
            
    def _fallback_query(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Keyword-based search when ChromaDB unavailable."""
        import re

        # Stop words to ignore (common words that create noise)
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "to", "of", "in", "on", "at", "for", "with", "and", "or", "but",
            "how", "what", "why", "when", "where", "who", "whom", "whose",
            "do", "does", "did", "can", "could", "will", "would", "should",
            "i", "you", "he", "she", "it", "we", "they", "me", "my", "your",
            "tell", "about", "me", "please", "give", "show", "explain", "make",
            "is", "it", "that", "this", "these", "those", "have", "has", "had"
        }

        def content_words(text):
            words = set(re.findall(r'\w+', text.lower()))
            return words - stop_words

        question_words = content_words(question)

        if not question_words:
            return []

        all_facts = list(STEM_FACTS) + self._load_cybersec_facts()

        scored = []
        for fact in all_facts:
            fact_words = content_words(fact["text"])
            overlap = question_words & fact_words
            if overlap:
                # Score higher for more overlap, especially rare words
                score = len(overlap)
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {"text": f["text"], "metadata": f["metadata"], "distance": 0}
            for _, f in scored[:top_k]
        ]
        
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = {
            "chroma_available": CHROMA_AVAILABLE,
            "document_count": self.collection.count() if self.collection else 0,
            "cybersec_file_exists": self.cybersec_path.exists()
        }
        return stats


# Test
if __name__ == "__main__":
    print("Knowledge Base Test")
    kb = KnowledgeBase()
    kb.initialize()
    
    for q in ["How do I make a strong password?", "What is phishing?", 
              "How do rockets work?", "Tell me about ransomware"]:
        results = kb.query(q)
        print(f"\nQ: {q}")
        for r in results:
            print(f"  [{r['metadata'].get('topic')}] {r['text'][:80]}...")