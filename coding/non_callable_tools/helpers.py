

def open_file(file_path: str) -> str:
    # opens an .md file and returns the content
    with open(file_path, 'r') as f:
        return f.read()

def load_prompt(prompt_file: str, include_general_context: bool = True) -> str:
    prompt = open_file(prompt_file)
    if include_general_context:
        general_content = open_file('coding/system_prompts/GENERAL.md')
        prompt += f"\n{general_content}"
    return prompt