import subprocess
import os
import re
from ollama import chat

def extract_python_code(response_content):
    """Extract Python code from the Ollama response."""
    code_pattern = r"```python(.*?)```"
    match = re.search(code_pattern, response_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def print_green(text):
    """Print text in green color."""
    GREEN = "\033[92m"
    RESET = "\033[0m"
    print(f"{GREEN}{text}{RESET}")

def print_pink(text):
    """Print text in pink color."""
    PINK = "\033[95m"
    RESET = "\033[0m"
    print(f"{PINK}{text}{RESET}")

def print_blue(text):
    """Print text in blue color."""
    BLUE = "\033[94m"
    RESET = "\033[0m"
    print(f"{BLUE}{text}{RESET}")

def detect_error(execution_output):
    """Check if the execution output contains an error."""
    return "Traceback" in execution_output or "Error" in execution_output or "Exception" in execution_output

def main():
    model = 'llama3.2'

    while True:
        # Step 1: Get a problem-solving prompt from the user
        user_prompt = input("\nEnter a problem for Ollama to solve (or 'exit' to quit): ")
        if user_prompt.lower() == 'exit':
            print("Exiting program.")
            break

        while True:  # Loop for endless optimization
            # Step 2: Send the prompt to the Ollama API
            try:
                response = chat(
                    model=model,
                    messages=[{'role': 'user', 'content': f'{user_prompt}. Create solution using python. Code is using Windows 11. Return the python code in a separate block.'}]
                )
                response_content = response['message']['content']
                python_code = extract_python_code(response_content)

                if not python_code:
                    print("No valid Python code found in the response.\n")
                    break  # Exit optimization loop

                print("Received code from Ollama:\n")
                print_green(python_code)
            except Exception as e:
                print(f"Error communicating with Ollama API: {e}")
                break  # Exit optimization loop

            # Step 3: Save the Python code to a file
            file_path = "exec.py"
            try:
                with open(file_path, "w") as file:
                    file.write(python_code)
                print(f"\nCode saved to {file_path}")
            except Exception as e:
                print(f"Error saving code to file: {e}")
                break  # Exit optimization loop

            # Step 4: Execute the Python code locally
            try:
                print(f"Executing the code...")
                result = subprocess.run(["python", file_path], capture_output=True, text=True)
                execution_output = result.stdout + result.stderr
                print("Execution Results:\n")
                print_pink(execution_output)
            except Exception as e:
                print(f"Error executing the code: {e}")
                break  # Exit optimization loop

             # Step 5: Evaluate the execution output for errors
            if detect_error(execution_output):  # Check for errors in the output
                print("Error detected in the execution output. Sending error details to Ollama for optimization...")
                try:
                    feedback_response = chat(
                        model=model,
                        messages=[
                            {'role': 'user', 'content': f"The executed code produced the following error:\n{execution_output}\nBased on this error, propose updates to fix the issue. Provide the updated Python code in a separate block."}
                        ]
                    )
                    print("Response from Ollama after providing error feedback:")
                    print_blue(feedback_response['message']['content'])

                    # Extract new Python code for further optimization
                    new_python_code = extract_python_code(feedback_response['message']['content'])
                    if new_python_code:
                        python_code = new_python_code  # Update with the new code
                    else:
                        print("\nNo valid Python code found in the updated response.\n")
                        break  # Exit optimization loop

                except Exception as e:
                    print(f"Error sending execution results to Ollama: {e}")
                    break  # Exit optimization loop
            else:
                print("\nNo errors detected. Optimization loop completed.\n")
                break  # Exit optimization loop


if __name__ == "__main__":
    main()
