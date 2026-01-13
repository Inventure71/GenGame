

class TodoItem:
    def __init__(self, task_title: str, task_description: str):
        self.task = task_title
        self.task_description = task_description
        self.completed = False

    def complete(self):
        self.completed = True

    def is_completed(self):
        return self.completed

class TodoList:
    # this needs to be good for an llm so we only return strings
    def __init__(self):
        self.todo_list = []
        self.index_of_current_task = 0

    def append_to_todo_list(self, task_title: str, task_description: str): # this will append to the end
        self.todo_list.append(TodoItem(task_title, task_description))
        if self.index_of_current_task == -1:
            self.index_of_current_task = len(self.todo_list) - 1
        self._notify_logger()

    def update_task_by_index(self, task_index: int, new_title: str = None, new_description: str = None, completed: bool = None):
        """Update a task's title and/or description by index."""
        if 0 <= task_index < len(self.todo_list):
            task = self.todo_list[task_index]
            if new_title is not None:
                task.task = new_title
            if new_description is not None:
                task.task_description = new_description
            if completed is not None:
                task.completed = completed
            self._notify_logger()
            return "Task updated successfully."
        return "Task index out of range."

    def complete_task(self):
        if 0 <= self.index_of_current_task < len(self.todo_list):
            self.todo_list[self.index_of_current_task].complete()
            self.index_of_current_task += 1
        
        if self.index_of_current_task >= len(self.todo_list):
            self.index_of_current_task = -1
            self._notify_logger()
            return "All tasks completed."
        self._notify_logger()
        return "Task marked as completed."

    def _notify_logger(self):
        """Notify logger of TODO changes."""
        try:
            from coding.non_callable_tools.action_logger import action_logger
            action_logger.log_todo_update()
        except:
            pass

    def get_current_task(self):
        if self.index_of_current_task == -1:
            return "No tasks remaining, all tasks have been completed"
        return f"Task: {self.todo_list[self.index_of_current_task].task} Description: {self.todo_list[self.index_of_current_task].task_description}"

    def get_number_of_tasks(self):
        return len(self.todo_list)

    def get_all_tasks(self):
        string_tasks = ""
        for index, task in enumerate(self.todo_list):
            string_tasks += f"{index + 1}.{'[COMPLETED]' if task.completed else '[NOT COMPLETED]'} Task: {task.task} Description:\n{task.task_description}\n"
        return string_tasks
