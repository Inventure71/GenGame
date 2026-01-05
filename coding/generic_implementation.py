from coding.non_callable_tools.helpers import load_prompt
from coding.handlers.gemini_handler import GeminiHandler
from coding.handlers.openai_handler import OpenAIHandler
from coding.non_callable_tools.todo_list import TodoList

class GenericHandler:
    def __init__(self, thinking_model, model_name: str = "models/gemini-3-flash-preview", provider: str = "GEMINI"):
        if provider == "GEMINI":
            self.client = GeminiHandler(thinking_model=thinking_model, model_name=model_name)
        elif provider == "OPENAI":
            self.client = OpenAIHandler(thinking_model=thinking_model, model_name=model_name)
        elif provider == "OLLAMA":
            self.client = OpenAIHandler(thinking_model=thinking_model, model_name=model_name, force_url="http://localhost:11434/v1")
        else:
            raise ValueError(f"Invalid provider: {provider}")

        self.thinking_model = thinking_model
        self.model_name = model_name

        # Both the chat_history and full_history are stored by deafult in the starting client schema
        self.chat_history = []       # Main history (tool calls + text, NO thoughts, NO tool outputs)
        self.full_history = []       # Debug history (everything if needed)
    
        self.summary_history = []          # List of all task summaries in chronological order
        self.last_summary_index = 0       # Index in chat_history where last summary was added 

        self.available_tools = [] # list of functions that needs to be converted to the client schema, using the fixed explanations

        self.setup_config()

    def convert_chat_history_to_client_schema(self, chat_history: list, from_client, to_client): # es from_clinet = geminihandler reference
        new_history = []
        #TODO: Implement this, It should get the entire chat_history and convert from one type to the other
        for item in chat_history:
            role, decomposed_block_list = from_client.convert_from_client_schema_to_text(item)
            new_history.append(to_client.convert_to_client_schema(role, decomposed_block_list))

        return new_history

    def set_tools(self, tools: list):
        self.client.set_tools(tools)
        self.available_tools = tools

    def setup_config(self, thinking_level: str = "MEDIUM", system_instruction: str = None, tools: list = None):
        self.client.setup_config(thinking_level=thinking_level, system_instruction=system_instruction, tools=tools)
    
    def clean_chat_history(self):
        # complete cleanup of all histories
        self.chat_history = []
        self.summary_history = []
        self.full_history = []
        self.last_summary_index = 0
    
    def filter_chat_history(self, most_recent_chat: list):
        return self.client.filter_chat_history(most_recent_chat)

    def summarize_chat_history(self, autocleanup: bool = False):
        """
        Progressively summarizes only the work done since the last summary.
        Maintains a chain of summaries for better context preservation.
        """
        # We ignore the first item in the chat_history because it is the first user prompt that normally is really big
        # Also we want to summarize the things done by the agent not the user instructions
        # We summarize based on the chat_history which now contains:
        # User prompts, Model Text, Tool Calls (sans outputs, sans thoughts).
        
        start_index = self.last_summary_index + 1
        most_recent_chat = self.chat_history[start_index:]
        most_recent_chat = self.filter_chat_history(most_recent_chat) # this will already be in the correct client format

        if not most_recent_chat:
            # No new content to summarize
            print(f"DEBUG: No new work to summarize, REALLY REALLY STRANGE!!!")
            return "No new work to summarize."

        #summarize_system = "You are a helpful assistant that summarizes technical work done in previous conversations."
        #self.client.setup_config(thinking_level="LOW", system_instruction=summarize_system, tools=None)
        
        prompt = load_prompt("coding/prompts/summarize_history.md", include_general_context=False)
        response = self.generate_response(prompt, use_tools=False, use_history=True, chat_history_to_update=most_recent_chat)

        summary_entry = f"TASK SUMMARY ({len(self.summary_history) + 1}):\n{response}"
        self.summary_history.append(summary_entry)

        if autocleanup:
            # we just clean the memory and then add the summaries to the empty chat
            self.chat_history = []
            self.chat_history.append(self.client.convert_to_client_schema(role="user", content="Summarize what has been accomplished so far."))
            combined_summary = "\n\n".join(self.summary_history)
            self.chat_history.append(self.client.convert_to_client_schema(role="assistant", content=combined_summary))
            
            #for summary in self.summary_history:
            #    self.chat_history.append(self.client.convert_to_client_schema(role="user", content="Summarize what has been accomplished so far."))
            #    # Use "assistant" role for OpenAI compatibility (Gemini accepts "model" too)
            #    self.chat_history.append(self.client.convert_to_client_schema(role="assistant", content=summary))
            
        self.last_summary_index = len(self.chat_history) - 1
        return response

    def generate_response(self, prompt: str, use_tools: bool = False, use_history: bool = False, chat_history_to_update: list = None) -> str:
        # 1. Create a TEMPORARY history for this specific turn
        # check if the prompt is already an history item, if so, use it as is
        user_content = self.client.convert_to_client_schema(role="user", content=prompt)
        
        # Determine which history to use and update
        if use_history:
            if chat_history_to_update is None:
                chat_history_to_update = self.chat_history
            # Append to permanent history immediately
            chat_history_to_update.append(user_content)
            # Use chat_history as the base context
            turn_history = list(chat_history_to_update) 
        else:
            turn_history = [user_content]

        if use_tools:
            active_config = self.client.get_config()
        else:
            active_config = self.client.temporary_no_tools_config()
            
        # 2. Get the answer        
        final_text = self.client.ask_model(turn_history, active_config, history_to_update=chat_history_to_update)
        
        return final_text
    
    def ask_until_task_completed(self, todo_list: TodoList, current_index: int, full_prompt: str, summarize_at_completion: bool) -> str:
        iteration_count = 0
        while True:
            if iteration_count > 0:
                full_prompt = "Continue the task until it is completed. Ensure you have addressed all requirements of the current task step."
            iteration_count += 1
            print("Iteration: ", iteration_count)

            # We use use_history=True to maintain context across the session
            response = self.generate_response(
                prompt=full_prompt, 
                use_tools=True, 
                use_history=True
            )

            temp_index = todo_list.index_of_current_task
            if temp_index == -1:
                print("Agent has completed all tasks")
                return -1
            elif temp_index != current_index:
                print("Agent has completed a task")
                if summarize_at_completion:
                    print("Summarizing chat history...")
                    self.summarize_chat_history(autocleanup=True)
                else:
                    print("Not summarizing chat history, flag set to False")
                return temp_index
            else:
                print("Agent has not completed the task yet")

    