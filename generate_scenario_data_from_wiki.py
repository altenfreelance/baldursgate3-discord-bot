import json
import httpx

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"
INPUT_PATH = "data/raw/bg3_wiki_data.jsonl"
OUTPUT_PATH = "generated/wiki_scenarios.jsonl"

def query_ollama(prompt: str) -> str:
    response = httpx.post(OLLAMA_URL, json={
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }, timeout=60)
    response.raise_for_status()
    return response.json()["response"].strip()

def build_prompt(title: str, wiki_text: str) -> str:
    return f"""
You are a Baldur's Gate 3 tactical advisor.
Based on the following wiki entry, generate a **single realistic gameplay scenario** where a player might use this information in combat, exploration, dialogue, puzzle solving, or item usage.
Make it concise and accurate. Avoid making up scenarios. Nothing is better 

=== WIKI ENTRY: {title} ===
{wiki_text}
=== END ===

I am using this to train a model so the exact output format is critical. I want a JSON object with keys: input, output
Respond ONLY using the exact format below, with no additional text or explanations: Dont explain yourself, i just need restructured output from this prompt.

{{
  "input": "A question or situation where this wiki information would be useful",
  "output": "The tactical advice or solution using this information"
}}
""".strip()

def process_jsonl():
    import datetime
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    output_path_with_date = f"{OUTPUT_PATH.split('.')[0]}_{current_date}.{OUTPUT_PATH.split('.')[1]}"
    with open(INPUT_PATH, "r", encoding="utf-8") as infile, open(output_path_with_date, "w", encoding="utf-8") as outfile:
        for line_num, line in enumerate(infile, start=1):
            try:
                data = json.loads(line)
                title = data.get("title", f"Entry {line_num}")
                wiki_text = data.get("text", "").strip()

                for i in range(3):  # Generate 3 separate scenarios
                    prompt = build_prompt(title, wiki_text)
                    response = query_ollama(prompt)
                    print(f"🦙 {response}")

                    try:
                        response_json = json.loads(response)
                        input_q = response_json.get("input", "")
                        output_a = response_json.get("output", "")
                    except json.JSONDecodeError:
                        print(f"❌ Error parsing JSON response: {response}")
                        continue

                    result = {
                        "instruction": f"'{title}'.",
                        "input":  f"'{input_q}'",
                        "output":  f"'{output_a}'",
                        "text": wiki_text[:50] + "..." if len(wiki_text) > 50 else wiki_text,
                    }

                    outfile.write(json.dumps(result, ensure_ascii=False) + "\n")
                    outfile.flush()
                    print(f"✅ Entry {line_num} scenario {i+1}/3 processed: {title}")

            except Exception as e:
                print(f"❌ Error on entry {line_num}: {e}")

    print(f"\n🎉 All scenarios saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    process_jsonl()
