import json
import re
import traceback
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from tqdm import tqdm

# === CONFIG ===
INPUT_FILE = "bg3_wiki_data.jsonl"
OUTPUT_FILE = "bg3_lora_dataset.jsonl"
NUM_EXAMPLES = 100  # Set to None to process full file
MODEL_NAME = "llama3"
DEBUG = False  # Set True to print each raw model output

# === Load model ===
llm = Ollama(model=MODEL_NAME)

# === Prompt Template ===
prompt_template = PromptTemplate.from_template(
    """You are a Baldur's Gate 3 lore master.

You will be given a lore entry. Create a natural-sounding question a player might ask (instruction), a short context if helpful (input), and a clear, lore-based answer (output). Respond ONLY with a valid JSON object using keys: instruction, input, and output.

Example:
{{
  "instruction": "Who is the leader of the Goblin Camp?",
  "input": "Goblin Camp entry",
  "output": "The leader of the Goblin Camp is..."
}}

--- ENTRY START ---
Title: {title}

{text}
--- ENTRY END ---
"""
)

# === Load data ===
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    entries = [
        json.loads(line)
        for line in f
        if "text" in line and "title" in line and len(json.loads(line)["text"].strip()) > 30
    ]

# === JSON extraction helper ===
def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*?\}", text)
        if match:
            return json.loads(match.group(0))
        raise

# === Process entries ===
results = []
entry_slice = entries[:NUM_EXAMPLES] if NUM_EXAMPLES else entries

for i, entry in enumerate(tqdm(entry_slice, desc="Processing entries")):
    print(f"\n🔄 Processing entry {i+1}: {entry['title']}")
    try:
        prompt = prompt_template.format(title=entry["title"], text=entry["text"])
        raw_response = llm.invoke(prompt)

        if DEBUG:
            print("🔍 Raw response:\n", raw_response)

        parsed = extract_json(raw_response)

        if not {"instruction", "input", "output"}.issubset(parsed.keys()):
            print(f"⚠️ Skipping due to missing keys: {parsed}")
            continue

        results.append(parsed)

    except Exception as e:
        print(f"⚠️ Error processing '{entry['title']}': {e}")
        traceback.print_exc()

# === Save results ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"\n✅ {len(results)} Q&A pairs saved to {OUTPUT_FILE}")
