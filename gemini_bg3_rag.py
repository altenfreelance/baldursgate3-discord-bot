import google.generativeai as genai
import os
from dotenv import load_dotenv

def main():
    """
    Main function to run the Gemini interactive script.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Configure with your API key (loaded from .env or environment)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file or environment variables.")
        print("Please create a .env file with GEMINI_API_KEY='your_key_here' or set it as an environment variable.")
        exit(1)

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error configuring Generative AI SDK: {e}")
        exit(1)

    # Choose a model
    # Use "gemini-1.5-flash-latest" as a more robust default if 2.0 isn't available or recognized by the SDK
    model_name_from_env = os.environ.get("DEFAULT_MODEL_NAME")
    model_name = model_name_from_env if model_name_from_env else "gemini-2.0-flash"


    try:
        model = genai.GenerativeModel(model_name)
        print(f"Successfully initialized model: {model_name}")
    except Exception as e:
        print(f"Error initializing model '{model_name}': {e}")
        print("Details:")
        if hasattr(e, 'args') and e.args:
            print(f"  Message: {e.args[0]}")
        if hasattr(e, '__cause__') and e.__cause__:
            print(f"  Cause: {e.__cause__}")
        print("\nMake sure you have the correct model name, your API key has access to this model,")
        print("and your google-generativeai SDK is up to date (`pip install --upgrade google-generativeai`).")
        print("Common model names: 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-pro'.")
        exit(1)

    print(f"\nInteracting with Gemini model: {model_name}. Type 'quit' or 'exit' to stop.")

    while True:
        try:
            user_prompt = input("\nYour prompt: ")
        except EOFError: # Handle Ctrl+D
            print("\nExiting due to EOF.")
            break
        except KeyboardInterrupt: # Handle Ctrl+C
            print("\nExiting due to keyboard interrupt.")
            break


        if user_prompt.lower() in ['quit', 'exit']:
            break
        if not user_prompt.strip():
            print("Prompt cannot be empty.")
            continue

        print("Generating response...")
        try:
            response = model.generate_content(user_prompt)

            print("\nGemini's Response:")
            print("-" * 20)

            # Check for blocked content first
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason
                print(f"Content generation blocked. Reason: {reason}")
                if response.prompt_feedback.safety_ratings:
                    print("Safety Ratings:")
                    for rating in response.prompt_feedback.safety_ratings:
                        print(f"  - Category: {rating.category}, Probability: {rating.probability.name}")
            # Then check for actual content
            elif response.parts:
                print(response.text)
            # Handle cases where there might be no parts but also no explicit block (unlikely but good to check)
            else:
                print("No text content in response and not explicitly blocked. Full response details:")
                # Consider how to best display 'response' if it's large or complex
                # For now, just printing its string representation.
                # You might want to use pprint for better formatting if it's a complex object:
                # from pprint import pprint
                # pprint(response)
                print(str(response))

            print("-" * 20)

        except Exception as e:
            print(f"An error occurred while generating content: {e}")
            # You might want to inspect 'response.prompt_feedback' if available in 'e' for safety issues.
            # e.g. if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
            #    if e.response.prompt_feedback.block_reason:
            #        print(f"  Block reason: {e.response.prompt_feedback.block_reason_message}")

    print("\nExiting Gemini interactive script.")

if __name__ == "__main__":
    main()