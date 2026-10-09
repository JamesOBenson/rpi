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
    {
        "id": "stem_001",
        "text": "A rocket works by expelling gas out of a nozzle at high speed. This creates thrust that pushes the rocket forward, following Newton's Third Law: for every action, there is an equal and opposite reaction.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_002",
        "text": "The International Space Station orbits Earth about every 90 minutes. Astronauts aboard experience weightlessness because they are in constant free fall around the planet.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_003",
        "text": "Octopuses have three hearts and blue blood. Two hearts pump blood to the gills, while the third pumps it to the rest of the body. Their blue blood comes from a copper-based protein called hemocyanin.",
        "metadata": {"topic": "animals", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_004",
        "text": "Honey bees communicate through a waggle dance. When a bee finds a good source of nectar, she returns to the hive and performs a dance that tells other bees the direction and distance to the flowers.",
        "metadata": {"topic": "animals", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_005",
        "text": "A rainbow forms when sunlight passes through water droplets in the air. The light bends (refracts) and splits into different colors because each color bends at a slightly different angle.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_006",
        "text": "Sound travels as waves through air. When you speak, your vocal cords vibrate and create pressure waves that travel to someone's ear, where they are converted back into sound.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_007",
        "text": "The light bulb was improved by Thomas Edison in 1879, but many inventors contributed to its development. Edison's key innovation was using a carbon filament that could glow for many hours.",
        "metadata": {"topic": "inventions", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_008",
        "text": "The telephone was invented by Alexander Graham Bell in 1876. His first words over the phone were: 'Mr. Watson, come here, I want to see you!'",
        "metadata": {"topic": "inventions", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_009",
        "text": "Photosynthesis is how plants make their own food. They use sunlight, carbon dioxide from the air, and water to create sugar and release oxygen as a byproduct.",
        "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_010",
        "text": "The water cycle moves water around Earth. Water evaporates from oceans, forms clouds, falls as rain or snow, and flows back to the oceans, repeating endlessly.",
        "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_011",
        "text": "The sky is blue because of the way sunlight scatters in the air. Sunlight looks white, but it is made of all the colors of the rainbow. When it hits the tiny gas particles in the atmosphere, blue light scatters in every direction much more than red light does, so we see blue all around us when we look up. At sunset, the light travels through much more air, and the blue scatters away before it reaches us, so the sky turns red and orange.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_012",
        "text": "We have day and night because the Earth spins around. The Earth rotates once every 24 hours, so while it is light on your side, the other side of the planet is in darkness. The Sun does not go to sleep or sink into the ocean - the Earth is simply turning your town away from it.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_013",
        "text": "The seasons happen because the Earth is tilted as it orbits the Sun. When your side of Earth leans toward the Sun, you get more direct sunlight and longer days, which is summer. Six months later, Earth's orbit has brought your side to lean away, the sunlight spreads out thinner, and it is winter. Seasons are NOT caused by Earth getting closer to or farther from the Sun.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_014",
        "text": "The Moon changes shape over about 29.5 days because of where it is in its orbit around Earth. The Sun always lights half of the Moon, but from Earth we see different amounts of the lit half. When we see all of the lit half it is a full moon, and when the lit side faces away from us we see nothing at all, a new moon. The Moon does not make its own light - it reflects the Sun's.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_015",
        "text": "A volcano erupts because of heat from deep inside the Earth. Some rock down there melts into magma, and because magma is lighter than solid rock, it pushes upward. When it finds a crack in the crust, it erupts, and the molten rock is then called lava. Bubbles of gas trapped in the magma are what make some eruptions explosive.",
        "metadata": {"topic": "earth", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_016",
        "text": "The ocean is salty because rain has slowly weathered rocks on land for hundreds of millions of years, carrying dissolved minerals into the sea. Rivers still deliver salt to the ocean every day, and when ocean water evaporates to form clouds, the salt stays behind. So the ocean has kept getting saltier, little by little, for billions of years.",
        "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_017",
        "text": "Lightning and thunder are the same event. Inside a storm cloud, ice and water bump together and build up static electricity. When the charge jumps to the ground as lightning, the air around it heats up so fast it explodes outward as a shock wave - that is thunder. You see the flash before you hear the boom because light travels much faster than sound.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_018",
        "text": "A black hole is a place where a very massive star has collapsed, squeezing all of its mass into an incredibly tiny point. Its gravity is so strong that nothing can escape, not even light, which is why it appears black. Astronomers cannot see a black hole directly, but they can see the hot, glowing gas swirling around it.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_019",
        "text": "Gravity is the invisible force that pulls things toward each other. The bigger an object is, the stronger its gravity. Earth is huge, so its gravity pulls everything toward its center, which is why you stay on the ground and rain falls down. Isaac Newton figured this out around 1666, famously inspired by a falling apple.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_020",
        "text": "Ice floats because water is one of the few things that is LIGHTER when it freezes. When water freezes, its molecules lock into a roomy crystal structure full of tiny gaps, so ice is less dense than liquid water. That is lucky for nature: ice forms on top of lakes, insulates the water below, and fish can survive the winter.",
        "metadata": {"topic": "physics", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_021",
        "text": "Airplanes fly because of lift. As the plane moves forward, air flows faster over the curved top of the wing than under it, creating lower pressure above the wing. The higher pressure below then pushes the wing up. When lift is greater than the plane's weight, it climbs. The engines pull the plane forward and the wings do the lifting.",
        "metadata": {"topic": "engineering", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_022",
        "text": "DNA is the instruction manual inside almost every cell of your body. It is a molecule shaped like a twisted ladder, and the order of its four chemical letters - A, T, C, and G - spells out the instructions for building and running you. You inherit half your DNA from your mother and half from your father, which is why you look like a mix of both.",
        "metadata": {"topic": "biology", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_023",
        "text": "Stars twinkle because of Earth's atmosphere. Starlight has to travel through many layers of moving air on its way to your eyes, and the air bends the light slightly as it goes. The bending changes from moment to moment, so the star's light flickers and shimmers. In space, with no air at all, stars do not twinkle - that is why they look steady in photos taken from orbit.",
        "metadata": {"topic": "space", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_024",
        "text": "An earthquake happens because Earth's crust is made of giant slabs of rock called tectonic plates, and they slowly creep along, a few centimeters a year. When two plates get stuck and then suddenly slip, the ground shakes. The shaking travels through the ground as waves, and scientists called seismologists measure them with instruments called seismographs.",
        "metadata": {"topic": "earth", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_025",
        "text": "Leaves are green in summer because of a molecule called chlorophyll, which plants use to turn sunlight into food. In autumn the days get shorter and the plant stops making chlorophyll, so other pigments that were hidden all along, like yellows and oranges, show through. Some trees, like maples, make brand-new red pigments in the fall.",
        "metadata": {"topic": "nature", "grade_level": "4-5", "source": "stem"},
    },
    {
        "id": "stem_026",
        "text": "Sharks are fish, and they eat other fish, squid, and small sea animals - they do NOT eat cake! Sharks have no hard bones; their skeletons are made of cartilage, the same flexible material as your ear. Some sharks, like the great white, grow as long as a school bus, and they use a super-strong sense of smell to find their food.",
        "metadata": {"topic": "animals", "grade_level": "4-5", "source": "stem"},
    },
]


class KnowledgeBase:
    """Offline knowledge base with vector search (RAG)."""

    def __init__(
        self,
        collection_name: str = "knowledge",
        persist_path: str = None,
        cybersec_path: str = None,
        max_distance: float = 0.80,
    ):
        """
        Initialize knowledge base.

        Args:
            collection_name: ChromaDB collection name
            persist_path: Path to persistent storage
            cybersec_path: Path to cybersecurity facts JSON
            max_distance: Drop RAG hits farther than this (cosine distance)
        """
        self.collection_name = collection_name
        self.persist_path = (
            Path(persist_path) if persist_path else PROJECT_ROOT / "data" / "chroma"
        )
        self.cybersec_path = (
            Path(cybersec_path)
            if cybersec_path
            else PROJECT_ROOT / "data" / "cybersecurity_facts.json"
        )
        self.max_distance = max_distance
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
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            # Build (or rebuild) the index when the fact set has changed -
            # e.g. after editing STEM_FACTS or the cybersecurity JSON.
            expected = len(STEM_FACTS) + len(self._load_cybersec_facts())
            current = self.collection.count()
            if current == 0:
                print("  Building knowledge index (first run, ~30 sec)...")
                self._load_all_knowledge()
            elif current != expected:
                print(
                    f"  Fact set changed ({current} -> {expected} docs) - rebuilding index..."
                )
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name, metadata={"hnsw:space": "cosine"}
                )
                self._load_all_knowledge()

            print("✓ Knowledge base initialized")
            print(f"  Documents: {self.collection.count()}")

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
            ids=[f["id"] for f in all_facts],
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
                            facts.append(
                                {
                                    "id": item["id"],
                                    "text": item["fact"],
                                    "metadata": {
                                        "topic": category,
                                        "grade_level": level,
                                        "difficulty": item.get("difficulty", "unknown"),
                                        "source": "cybersecurity",
                                        "keywords": ",".join(item.get("keywords", [])),
                                    },
                                }
                            )
        except Exception as e:
            print(f"  ⚠ Error loading cybersecurity facts: {e}")

        return facts

    def query(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
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
            results = self.collection.query(query_texts=[question], n_results=top_k)

            formatted = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    dist = results["distances"][0][i] if results["distances"] else 0
                    # Drop unrelated facts: a weakly-matching fact actively
                    # confuses the 1.5B model (it answers the fact instead of
                    # the question). 0.80 keeps real matches, including
                    # garbled ones ("black horse" -> black hole: 0.72).
                    if dist > self.max_distance:
                        continue
                    formatted.append(
                        {
                            "text": doc,
                            "metadata": (
                                results["metadatas"][0][i]
                                if results["metadatas"]
                                else {}
                            ),
                            "distance": dist,
                        }
                    )

            return formatted

        except Exception as e:
            print(f"Query error: {e}")
            return []

    def _fallback_query(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Keyword-based search when ChromaDB unavailable."""
        import re

        # Stop words to ignore (common words that create noise)
        stop_words = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "to",
            "of",
            "in",
            "on",
            "at",
            "for",
            "with",
            "and",
            "or",
            "but",
            "how",
            "what",
            "why",
            "when",
            "where",
            "who",
            "whom",
            "whose",
            "do",
            "does",
            "did",
            "can",
            "could",
            "will",
            "would",
            "should",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "my",
            "your",
            "tell",
            "about",
            "me",
            "please",
            "give",
            "show",
            "explain",
            "make",
            "is",
            "it",
            "that",
            "this",
            "these",
            "those",
            "have",
            "has",
            "had",
        }

        def content_words(text):
            words = set(re.findall(r"\w+", text.lower()))
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
            "cybersec_file_exists": self.cybersec_path.exists(),
        }
        return stats


# Test
if __name__ == "__main__":
    print("Knowledge Base Test")
    kb = KnowledgeBase()
    kb.initialize()

    for q in [
        "How do I make a strong password?",
        "What is phishing?",
        "How do rockets work?",
        "Tell me about ransomware",
    ]:
        results = kb.query(q)
        print(f"\nQ: {q}")
        for r in results:
            print(f"  [{r['metadata'].get('topic')}] {r['text'][:80]}...")
