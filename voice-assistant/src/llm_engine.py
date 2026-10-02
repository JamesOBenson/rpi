#!/usr/bin/env python3
"""
LLM Engine
==========
Local language model for generating kid-friendly answers.
Uses quantized models that fit in 8GB RAM.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Common English function words - ignored when deciding whether two answer
# sentences are near-duplicates (only "content" words count toward similarity).
_STOP_WORDS = frozenset("""
    a an the is are was were be been being am do does did doing and or but if
    then else of in on at to for with by from as it its this that these those
    there here he she they we you i me him her us them my your his their our
    not no so than too very can could will would should may might must about
    into over under again once because while where when how why what who which
    all any both each few more most other some such only own same don now also
    just like let lets it's we're i'm you're they're there's that's has have
    had i've you've we've s t don't
    """.split())

# Qwen3 thinking tags. With /no_think the model emits an empty pair before
# the answer; if it does think (rare), the stream guard drops everything
# up to the closing tag so thinking text is never spoken.
THINK_START = "\u003cthink\u003e"
THINK_END = "\u003c/think\u003e"


class LocalLLM:
    """Local LLM with RAG support."""
    
    def __init__(
        self,
        model_path: str = None,
        n_ctx: int = 512,
        n_threads: int = 8
    ):
        """
        Initialize local LLM.
        
        Args:
            model_path: Path to GGUF quantized model
            n_ctx: Context window size
            n_threads: Number of CPU threads
        """
        if model_path is None:
            model_path = "gemma-3n-E2B-it-Q4_K_M.gguf"
        # Resolve: accept absolute, relative, or bare filename in models/
        p = Path(model_path)
        if not p.is_absolute() and not p.exists():
            p = PROJECT_ROOT / "models" / model_path
        self.model_path = p
        # Model family drives chat template + stop tokens (see _build_prompt)
        self._is_qwen = "qwen" in p.name.lower()
        # llama.cpp requires n_ctx >= 1024 for Gemma 3(n) (RoPE min context)
        if not self._is_qwen and n_ctx < 1024:
            n_ctx = 1024
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.llama = None
        
        # Kid-friendly system prompt (no few-shot - they cause hallucinations).
        # Keep this SHORT: measured on the 1.5B model, adding an extra
        # instruction (e.g. "guess what the child meant") made answers WORSE,
        # and quoting a fallback line verbatim made the model parrot it.
        # Garbled-input handling lives in main.py (unintelligible guard +
        # RAG distance filter) instead.
        self.system_prompt = """You are STEM Buddy, a friendly AI for 4th-5th graders.
Answer in 1-2 short sentences, simple words, under 40 words.
Start directly - no labels, no names, no "Response:".
Use the facts below when they answer the question; ignore them otherwise.
If you don't know, say "I'm not sure about that one!"""
        
    def initialize(self):
        """Initialize LLM model."""
        try:
            from llama_cpp import Llama
            
            # Check if model exists
            if not self.model_path.exists():
                print(f"⚠ Model not found: {self.model_path}")
                print("  Download Gemma 3n E2B from HuggingFace:")
                print("  https://huggingface.co/unsloth/gemma-3n-E2B-it-GGUF/resolve/main/gemma-3n-E2B-it-Q4_K_M.gguf")
                print("  (backup: Qwen3-1.7B - see download_models.sh)")
                return
                
            # Load model
            print(f"📚 Loading model: {self.model_path.name}")
            self.llama = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=0,  # Set >0 for GPU offload
                verbose=False
            )
            print("✓ LLM loaded")
            
        except ImportError:
            print("⚠ Install llama-cpp-python: pip install llama-cpp-python")
        except Exception as e:
            print(f"⚠ LLM error: {e}")
            
    def query_with_rag(
        self,
        question: str,
        knowledge_base,
        top_k: int = 3
    ) -> str:
        """
        Query LLM with RAG (Retrieval Augmented Generation).
        
        Args:
            question: User's question
            knowledge_base: KnowledgeBase instance
            top_k: Number of knowledge passages to retrieve
            
        Returns:
            Generated answer
        """
        # Retrieve relevant knowledge
        context = knowledge_base.query(question, top_k=top_k)
        
        # Build prompt with context
        prompt = self._build_prompt(question, context)
        
        # Generate answer
        if self.llama:
            answer = self._generate(prompt)
        else:
            answer = self._fallback_answer(question, context)
            
        return answer
        
    def query_with_rag_streaming(self, question: str, knowledge_base, top_k: int = 3, max_sentences: int = 2):
        """
        Generator that yields kid-friendly sentences AS the LLM streams them.
        This lets TTS start on the first sentence before the whole answer
        is generated - cutting perceived latency roughly in half.
        """
        import re
        context = knowledge_base.query(question, top_k=top_k)
        prompt = self._build_prompt(question, context)
        
        if not self.llama:
            yield self._fallback_answer(question, context)
            return
        
        buffer = ""
        yielded = 0
        started = False
        past_think_end = False  # Qwen3: skip everything until THINK_END seen
        accepted = []  # sentences already spoken (for duplicate filtering)
        try:
            for output in self.llama(
                prompt,
                max_tokens=60,
                temperature=0.3,
                stop=self._stop_tokens(),
                echo=False,
                stream=True
            ):
                token = output["choices"][0]["text"]
                if token:
                    if self._is_qwen and not past_think_end:
                        # Qwen3 emits an empty "\u003cthink\u003e"..."\u003c/think\u003e" pair (or a real
                        # think block) before answering - never speak it.
                        i = token.find(THINK_END)
                        if i < 0:
                            continue
                        token = token[i + len(THINK_END):]
                        past_think_end = True
                    buffer += token
                # Emit any complete sentence(s) now sitting in the buffer
                while True:
                    m = re.search(r'\S.*?[.!?](?=\s|$)', buffer)
                    if not m:
                        break
                    sent = m.group(0)
                    buffer = buffer[m.end():]
                    cleaned = self._clean_sentence(sent, first=not started)
                    started = True
                    if cleaned and self._is_new(cleaned, accepted):
                        accepted.append(cleaned)
                        yield cleaned
                        yielded += 1
                        if yielded >= max_sentences:
                            return
            # Flush the tail (last sentence may lack a trailing space)
            if buffer.strip() and yielded < max_sentences:
                cleaned = self._clean_sentence(buffer, first=not started)
                if cleaned and self._is_new(cleaned, accepted):
                    accepted.append(cleaned)
                    yield cleaned
            if not started:
                yield self._fallback_answer(question, context)
        except Exception as e:
            print(f"Generation error: {e}")
            yield self._fallback_answer(question, context)
        
    def _clean_sentence(self, text: str, first: bool = False) -> str:
        """Clean a single streamed sentence (prefix artifacts only on first)."""
        import re
        t = text.strip()
        # Qwen3 thinking-tag remnants (stream guard normally handles these)
        t = t.replace(THINK_START, "").replace(THINK_END, "").strip()
        if first:
            t = re.sub(r'^(response|assistant|answer|explanation|support)\s*:\s*', '', t, flags=re.IGNORECASE)
            t = re.sub(r'^[-*•]\s*', '', t)
        t = t.strip().strip('"').strip()
        return t
        
    def _is_new(self, text: str, accepted: List[str], threshold: float = 0.6) -> bool:
        """Return True if `text` is NOT a near-duplicate of any sentence in
        `accepted`. Similarity = overlap of content words (stop words ignored)
        using the overlap coefficient, so a rephrased repeat of the same idea
        is caught while genuinely new sentences pass through."""
        import re
        new_words = {w for w in re.findall(r"[a-z']+", text.lower()) if w not in _STOP_WORDS}
        if not new_words:
            return True  # no content words - keep, don't over-filter
        for acc in accepted:
            acc_words = {w for w in re.findall(r"[a-z']+", acc.lower()) if w not in _STOP_WORDS}
            if not acc_words:
                continue
            overlap = len(new_words & acc_words) / min(len(new_words), len(acc_words))
            if overlap >= threshold:
                return False
        return True

    def _build_prompt(self, question: str, context: List[Dict]) -> str:
        """Build prompt with retrieved context (per-model chat format)."""
        # Combine context passages
        context_text = "\n".join([f"- {c['text']}" for c in context[:3]])
        
        if self._is_qwen:
            # Qwen3: /no_think disables the thinking phase (measured on Pi:
            # 17.4s/138 tokens with thinking vs 2.9s/23 tokens without).
            user_msg = f"Facts:\n{context_text}\n\nQ: {question} /no_think"
            prompt = (
                f"<|im_start|>system\n{self.system_prompt}\n<|im_end|>\n"
                f"<|im_start|>user\n{user_msg}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
        else:
            # Gemma 3(n) chat format (no thinking mode - nothing to disable)
            user_msg = f"{self.system_prompt}\nFacts:\n{context_text}\n\nQ: {question}"
            prompt = (
                f"<start_of_turn>user\n{user_msg}\n<end_of_turn>\n"
                f"<start_of_turn>model\n"
            )
        return prompt
        
    def _stop_tokens(self) -> list:
        """Stop sequences differ per chat format."""
        if self._is_qwen:
            return ["\n\nQ:", "\n\nQuestion:", "Question:", "###"]
        return ["<end_of_turn>", "<start_of_turn>"]
        
    def _generate(self, prompt: str) -> str:
        """Generate response from LLM."""
        try:
            output = self.llama(
                prompt,
                max_tokens=60,
                temperature=0.3,
                stop=self._stop_tokens(),
                echo=False
            )
            
            answer = output["choices"][0]["text"].strip()
            return self._clean_answer(answer)
            
        except Exception as e:
            print(f"Generation error: {e}")
            return self._fallback_answer("error", [])
            
    def _clean_answer(self, text: str) -> str:
        """Remove LLM artifacts and enforce short kid-friendly length."""
        import re
        # Qwen3 thinking tags (empty with /no_think)
        text = text.replace(THINK_START, "").replace(THINK_END, "")
        
        # Remove common prefixes like "Response:", "Assistant:", "A:", etc.
        text = re.sub(r'^(response|assistant|answer|explanation|support)\s*:\s*', '', text, flags=re.IGNORECASE)
        
        # Remove surrounding quotes
        text = text.strip().strip('"').strip()
        
        # Remove "Explanation:" / "Example:" sections
        text = re.sub(r'\n*(Explanation|Example|Here are some other tips).*$', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Drop bullet-list lines (keep prose)
        lines = [l for l in text.split('\n') if not l.strip().startswith(('-', '*', '•'))]
        text = ' '.join(l.strip() for l in lines if l.strip())
        
        # Enforce max 2 sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 2:
            text = ' '.join(sentences[:2])
        
        return text.strip() or "I'm not sure about that one!"

    def _fallback_answer(self, question: str, context: List[Dict]) -> str:
        """Fallback answer when LLM unavailable - uses retrieved facts."""
        # If we have relevant knowledge, use it
        if context:
            best = context[0]["text"]
            # Pick a friendly intro based on topic
            topic = context[0].get("metadata", {}).get("topic", "")
            if "password" in topic:
                intro = "Here's a great tip about passwords: "
            elif "phish" in topic or "scam" in topic:
                intro = "Good question! Here's what to know: "
            elif "malware" in topic or "virus" in topic:
                intro = "Let me tell you about that: "
            else:
                intro = "Great question! Here's what I know: "
            return intro + best

        # Otherwise, simple keyword matching for STEM topics
        question_lower = question.lower()
        
        if "rocket" in question_lower or "space" in question_lower:
            return "Rockets work like a balloon! They shoot hot gas out the bottom super fast, which pushes the rocket up. It's Newton's Third Law in action!"
            
        elif "gravity" in question_lower:
            return "Gravity is like an invisible tug that pulls things together! Earth's gravity keeps your feet on the ground. Want to know why the Moon doesn't fall down?"
            
        elif "rainbow" in question_lower:
            return "Rainbows form when sunlight passes through raindrops! The light bends and splits into all the colors of the rainbow, just like a prism!"
            
        elif "dinosaur" in question_lower:
            return "Dinosaurs lived millions of years ago! The T-Rex was a huge meat-eater, while the Brachiosaurus was a gentle plant-eater that needed to eat tons of leaves every day."
            
        elif "animal" in question_lower:
            return "Animals are amazing! Did you know octopuses have three hearts and blue blood? Or that some birds can fly backwards?"
            
        else:
            return "That's a great question! Let me think... I'm still learning, but I'd love to explore that topic with you!"
            
    def simplify_for_kids(self, text: str) -> str:
        """Simplify complex text for 4th-5th graders."""
        # TODO: Implement text simplification
        # - Shorten long sentences
        # - Replace complex words
        # - Add friendly tone
        
        # Simple truncation for now
        if len(text) > 200:
            # Find last sentence break
            last_period = text.rfind('.', 0, 200)
            if last_period > 0:
                text = text[:last_period + 1]
                
        return text


# Test
if __name__ == "__main__":
    print("LLM Engine Test")
    llm = LocalLLM()
    llm.initialize()
    
    # Mock knowledge base
    class MockKB:
        def query(self, q, top_k=3):
            return [{"text": "The sky is blue because blue light scatters off air molecules more than red light."}]
            
    answer = llm.query_with_rag("What is gravity?", MockKB())
    print(f"\nQ: What is gravity?")
    print(f"A: {answer}")