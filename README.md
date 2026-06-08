# The Unofficial Guide - Project 1

A retrieval-augmented question-answering system over student reviews of Computer Science professors at Arkansas State University. Ask a plain-language question and get a grounded, cited answer drawn only from the collected reviews.

---

## Domain

Student reviews of **Computer Science professors at Arkansas State University (A-State)**, collected from RateMyProfessors. This knowledge is hard to find through official channels: the catalog and registrar tell you what a class covers and when it meets, but never which professor curves heavily, whose exams track the slides instead of the textbook, who's a tough grader, or which "basic" required course is actually brutal. That signal only lives in student-to-student reviews. This system makes ten professors' worth of it searchable.

---

## Document Sources

Ten professor pages from RateMyProfessors, all in A-State's Computer Science department (department id 11, school id 13755). One `.txt` file per professor; collected manually because the site blocks automated scraping.

| #  | Source | Type | URL |
| --- | ------ | ---- | --- |
| 1  | Edward Hammerand (`hammerand.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/13047 |
| 2  | Jason Causey (`causey.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/713362 |
| 3  | Hai Jiang (`jiang.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1109121 |
| 4  | Jeanette Spencer (`spencer.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/745227 |
| 5  | Gidget Scrivner (`scrivner.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1391506 |
| 6  | Mitchel Clay (`clay.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/3079478 |
| 7  | Amber McElhaney (`mcelhaney.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1390297 |
| 8  | S.D. Ray (`ray.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1353257 |
| 9  | Xiuzhen Huang (`huang.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1109118 |
| 10 | Susan Shanlever (`shanlever.txt`) | RMP reviews | https://www.ratemyprofessors.com/professor/1404468 |

The set spans easy↔hard, loved↔hated, and intro→upper-level→applications courses, so it can answer a range of questions rather than ten variations of one. ~74 reviews total.

---

## Chunking Strategy

**Chunk size:** 300 characters
**Overlap:** 80 characters (sentence-boundary aware; fragments under 40 chars dropped)
**Final chunk count:** 119

**Why these choices fit the documents:** The reviews are short and opinion-dense - most are 1–4 sentences. I first tried 500 characters, which produced 60 chunks but tended to merge two reviews per chunk, giving muddy embeddings and weaker retrieval on the test query. Dropping to 300 puts roughly one review per chunk, so each embedding represents a single, focused opinion; this visibly improved retrieval (top distance on the test query dropped from ~0.41 to ~0.37 and the hard-professor chunks began surfacing). Each document is chunked independently, so a chunk never mixes two professors. One known cost of small chunks: the professor's name only appears in the header chunk, so mid-file chunks lose it - see the Q1 result below.

### Sample chunks (5)

1. **`hammerand.txt`** - "I took Professor Hammerand for Intro to computers and he didn't disappoint. You only show up for class on test days, and if you miss one you are able to make it up on study day. It is all completely online... Easy A."
2. **`shanlever.txt`** - "Overall quality 1.4/5 from 5 ratings. 0% would take again... Course MIS1203 (difficulty 5/5): Nightmarish doesnt even come close to describing this class and teacher no help whatsoever and the tests are difficult with 80 to 90 questions..."
3. **`clay.txt`** - "Mr. Clay described computer architecture in a way that was easy to understand. His use of analogies and examples makes the complex concepts of computer architecture more digestible and easily graspable."
4. **`hammerand.txt`** - "...the wait is always worth it. Course CS2191 (difficulty 2/5): This guy is amazing he can explain anything to anyone and they will get it. He is a very rare teacher and i have learned more in this class than i have learned in any other class."
5. **`jiang.txt`** - "Course CS682 (difficulty 5/5): He is a geek of GPU computing. If you're not a geek then there is a compatibility problem and you can guess what happens. I've been a programming geek since years so he's always an inspiration."

---

## Embedding Model

**Model used:** `all-MiniLM-L6-v2` (sentence-transformers), stored in ChromaDB with cosine distance, top-k = 5. Runs locally - no API key, no rate limits, 384-dimensional, fast, and adequate for short English text.

**Production tradeoff reflection:** For a real deployment where cost wasn't a constraint, I'd weigh a larger hosted model (e.g. OpenAI `text-embedding-3-large` or a Voyage model) for better accuracy on domain jargon and longer context, plus stronger multilingual handling - several reviews are written by ESL students with non-standard phrasing that a bigger model embeds more robustly. The tradeoffs against MiniLM are latency, per-query cost, and the privacy/operational overhead of sending text to an external API instead of embedding locally.

---

## Grounded Generation

Generation uses Groq's `llama-3.3-70b-versatile`.

**System prompt grounding instruction (verbatim):**
> You answer questions using ONLY the numbered context below. If the context does not contain the answer, reply exactly: "I don't have enough information on that." Do not use outside knowledge. Do not guess. When you do answer, mention which source the information came from.

**How source attribution is surfaced:** Two layers. (1) The retrieved chunks are passed to the model numbered and labeled with each chunk's source filename, and the model cites them inline (e.g. "(source: hammerand.txt)"). (2) Independently of what the model writes, the app appends a deduplicated list of the retrieved source files - built directly from chunk metadata - under "Retrieved from." So attribution is guaranteed programmatically, not left to the model to remember.

This grounding held up in testing: asked "who teaches the database systems course?" (not covered by any document), the system retrieved four files but returned "I don't have enough information on that" rather than inventing an answer.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
| --- | -------- | --------------- | ---------------------------- | ----------------- | ----------------- |
| 1 | Which CS professors do students recommend for an easy A? | Hammerand, Clay, McElhaney, and Causey's intro courses. | Recommended Causey's intro/CSM1013 and an *unnamed* professor from hammerand.txt (CSM2113, difficulty 1/5); hedged; missed Clay and McElhaney. Could not name Hammerand because the retrieved chunk lacked his name. | Partially relevant (causey, hammerand, jiang; missed clay & mcelhaney) | Partially accurate |
| 2 | How many exams does Xiuzhen Huang's Analysis of Algorithms (CS4713) course have, and what are they? | Two - a midterm and a final. | "I don't have enough information on that." | Partially relevant - huang.txt was retrieved, but not the chunk holding the answer | **Inaccurate (failure case)** |
| 3 | Is Jason Causey's class hard? | Depends on the course: upper-level programming (CS2114/CS2124) is tough (4–5/5); intro courses are easy (1/5). | "Hard; tough grader; difficulty 3–4/5." Did not mention his easy intro courses. | Relevant but one-sided - all chunks from causey.txt, but only the tough-course chunks | Partially accurate |
| 4 | Is Jeanette Spencer's class easy or hard? | Students disagree - easy/cushion workload but tests reportedly hard, with big curves. | Captured the conflict: "varying difficulty… described as easy yet tests really difficult and precise." | Relevant - used spencer.txt chunks, correctly ignored other professors' chunks that were also retrieved | Accurate |
| 5 | Is Hai Jiang a harder professor than Edward Hammerand? | Yes - Jiang 3.0/5, difficulty 4 vs. Hammerand 5.0/5, difficulty 2.2. | Correctly compared difficulty ratings from both files and concluded Jiang is harder. | Relevant - retrieved from both hammerand.txt and jiang.txt | Accurate |

**Summary:** 2 accurate, 2 partially accurate, 1 inaccurate (failure).

---

## Failure Case Analysis

**Question that failed:** "How many exams does Xiuzhen Huang's Analysis of Algorithms (CS4713) course have, and what are they?"

**What the system returned:** "I don't have enough information on that."

**Root cause (retrieval, not generation):** The answer - "There are only 2 test, the midterm and the final" - exists verbatim in `huang.txt`, and `huang.txt` even appears in the retrieved-sources list. But with `top_k = 5` spread across 119 chunks, only *one* huang.txt chunk was retrieved, and it was not the chunk containing the exam detail. The query embeds toward "Analysis of Algorithms / exams," and chunks from other files (plus huang's other, more negative chunks) out-ranked the specific exam-count sentence. The grounding instruction then did exactly its job: with no exam information in the retrieved context, the model declined rather than fabricating. So generation behaved correctly - the failure is that retrieval never surfaced the relevant chunk.

**What I would change:** (a) raise `top_k` (e.g. to 8) so more of each file's chunks are eligible; (b) retrieve a minimum number of chunks per matched source; or (c) add hybrid keyword + semantic retrieval (BM25) - "midterm" and "final" are exact terms in the source, and a keyword signal would pull that chunk even when the embedding similarity is borderline.

---

## Spec Reflection

**One way the spec helped:** The milestone ordering - especially "test retrieval before adding generation" - caught a real bug. Inspecting the raw retrieval output revealed a duplicated document (`jiang.txt` had been populated with Hammerand's reviews, so identical chunks were returned from both files at the same distance) *before* generation could paper over it. The chunk-count guidance ("under ~50 is too coarse") also prompted me to test 500 vs. 300 characters, and 300 clearly retrieved better.

**One way the implementation diverged:** I wrote the pipeline code before fully finalizing `planning.md`, and I changed the chunk size from the planned 500 to 300 after seeing that 500 produced muddy multi-review chunks and weaker retrieval on the test query. `planning.md` was updated to reflect the 300 decision and the 119 final count.

---

## AI Usage

**Instance 1 - Document preparation**
- *What I gave the AI:* the raw RateMyProfessors page text for each professor (collected by hand, since the site blocks scraping) plus a target format.
- *What it produced:* a cleaned `.txt` per professor - boilerplate stripped (navigation, rating widgets, the "Similar Professors" sidebar, vote counts), each review tagged with its course code and difficulty.
- *What I changed/overrode:* reviewed every file, kept the review text verbatim (typos included), dropped the tag chips for consistency, and removed sidebar professors (e.g. Clay, Moeeni, Moody-Qualls appearing on others' pages) that didn't belong in a given file.

**Instance 2 - Pipeline code**
- *What I gave the AI:* `planning.md` and the architecture (ingest → chunk → embed → ChromaDB → retrieve → generate).
- *What it produced:* `rag.py` (loading, cleaning, sentence-aware chunking, MiniLM embedding, ChromaDB storage with source metadata, top-k retrieval, grounded Groq generation with programmatic citation) and `app.py` (Gradio UI).
- *What I changed/overrode:* re-pointed the loader from `docs/` to the starter's `documents/` folder, changed `CHUNK_SIZE` from 500 to 300 after testing, and verified that the grounding instruction was enforced and that source attribution came from metadata rather than the model.